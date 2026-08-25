from flask import Flask, render_template, request, redirect, url_for, session
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
from questions import questions

app = Flask(__name__)

app.secret_key = "ai-interview-secret-key"


def get_db_connection():
    connection = sqlite3.connect("database/database.db")
    connection.row_factory = sqlite3.Row
    return connection


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        email = request.form["email"]
        password = request.form["password"]

        connection = get_db_connection()

        user = connection.execute(
            "SELECT * FROM users WHERE email = ?",
            (email,)
        ).fetchone()

        connection.close()

        if user and check_password_hash(user["password"], password):

            session["user_id"] = user["id"]
            session["user_name"] = user["name"]

            return redirect(url_for("dashboard"))

        return "Invalid email or password!"

    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        name = request.form["name"]
        email = request.form["email"]
        password = request.form["password"]

        hashed_password = generate_password_hash(password)

        connection = get_db_connection()

        try:

            connection.execute(
                "INSERT INTO users (name, email, password) VALUES (?, ?, ?)",
                (name, email, hashed_password)
            )

            connection.commit()

        except sqlite3.IntegrityError:

            connection.close()
            return "Email already registered!"

        connection.close()

        return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/dashboard")
def dashboard():

    if "user_id" not in session:
        return redirect(url_for("login"))

    connection = get_db_connection()

    recent_interviews = connection.execute(
        """
        SELECT subject, difficulty, score,
               total_questions, percentage
        FROM interview_results
        WHERE user_id = ?
        ORDER BY id DESC
        LIMIT 5
        """,
        (session["user_id"],)
    ).fetchall()

    connection.close()

    return render_template(
        "dashboard.html",
        name=session["user_name"],
        recent_interviews=recent_interviews
    )


@app.route("/interview-setup")
def interview_setup():

    if "user_id" not in session:
        return redirect(url_for("login"))

    return render_template("interview_setup.html")


@app.route("/start-interview", methods=["POST"])
def start_interview():

    if "user_id" not in session:
        return redirect(url_for("login"))

    subject = request.form["subject"]
    difficulty = request.form["difficulty"]
    number_of_questions = int(request.form["questions"])

    session["subject"] = subject
    session["difficulty"] = difficulty

    available_questions = questions.get(subject, {}).get(difficulty, [])

    if not available_questions:
        return "No questions available for this subject and difficulty."

    selected_questions = available_questions[:number_of_questions]

    session["interview_questions"] = selected_questions
    session["current_question"] = 0
    session["score"] = 0

    return redirect(url_for("interview"))


@app.route("/interview")
def interview():

    if "user_id" not in session:
        return redirect(url_for("login"))

    question_index = session.get("current_question", 0)
    interview_questions = session.get("interview_questions", [])

    if question_index >= len(interview_questions):
        return redirect(url_for("result"))

    question = interview_questions[question_index]

    return render_template(
        "interview.html",
        question=question,
        question_number=question_index + 1,
        total_questions=len(interview_questions)
    )


@app.route("/submit-answer", methods=["POST"])
def submit_answer():

    if "user_id" not in session:
        return redirect(url_for("login"))

    interview_questions = session.get("interview_questions", [])
    question_index = session.get("current_question", 0)

    if question_index >= len(interview_questions):
        return redirect(url_for("result"))

    selected_answer = request.form["answer"]

    correct_answer = interview_questions[question_index]["answer"]

    if selected_answer == correct_answer:
        session["score"] = session.get("score", 0) + 1

    session["current_question"] = question_index + 1

    if session["current_question"] >= len(interview_questions):
        return redirect(url_for("result"))

    return redirect(url_for("interview"))


@app.route("/result")
def result():

    if "user_id" not in session:
        return redirect(url_for("login"))

    score = session.get("score", 0)
    interview_questions = session.get("interview_questions", [])

    total = len(interview_questions)

    if total == 0:
        return redirect(url_for("interview_setup"))

    percentage = int((score / total) * 100)

    subject = session.get("subject", "Unknown")
    difficulty = session.get("difficulty", "Unknown")

    connection = get_db_connection()

    connection.execute(
        """
        INSERT INTO interview_results
        (user_id, subject, difficulty, score, total_questions, percentage)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            session["user_id"],
            subject,
            difficulty,
            score,
            total,
            percentage
        )
    )

    connection.commit()
    connection.close()

    return render_template(
        "result.html",
        score=score,
        total=total,
        percentage=percentage
    )


@app.route("/logout")
def logout():

    session.clear()

    return redirect(url_for("login"))


@app.route("/history")
def history():

    if "user_id" not in session:
        return redirect(url_for("login"))

    connection = get_db_connection()

    results = connection.execute(
        """
        SELECT subject, difficulty, score,
               total_questions, percentage
        FROM interview_results
        WHERE user_id = ?
        ORDER BY id DESC
        """,
        (session["user_id"],)
    ).fetchall()

    statistics = connection.execute(
        """
        SELECT
            COUNT(*) AS total_interviews,
            COALESCE(AVG(percentage), 0) AS average_percentage,
            COALESCE(MAX(percentage), 0) AS best_percentage
        FROM interview_results
        WHERE user_id = ?
        """,
        (session["user_id"],)
    ).fetchone()

    connection.close()

    return render_template(
        "history.html",
        results=results,
        statistics=statistics
    )


if __name__ == "__main__":
    app.run(debug=True)