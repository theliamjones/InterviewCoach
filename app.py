"""Interview Coach - practise competency-based interview answers with STAR feedback."""

import os
import uuid
from datetime import date

from dotenv import load_dotenv

# override=True: .env is authoritative for this app (a stale/empty ANTHROPIC_API_KEY
# in the Windows environment would otherwise silently win over .env)
load_dotenv(override=True)  # must run before coach creates the Anthropic client

import anthropic
from flask import Flask, Response, jsonify, render_template, request

import coach

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16 MB upload cap

# In-memory session store: fine for a local single-user practice tool.
SESSIONS: dict[str, dict] = {}

ALLOWED_CV_EXTENSIONS = (".pdf", ".docx", ".txt")


@app.route("/")
def index():
    return render_template("index.html")


@app.get("/api/key-status")
def key_status():
    """Tell the front end whether a usable API key is already configured."""
    return jsonify(has_key=coach.has_key())


@app.post("/api/key")
def set_key():
    """Accept an API key entered in the browser; validate and hold it in memory."""
    data = request.get_json(silent=True) or {}
    try:
        coach.set_runtime_key(data.get("key", ""))
    except ValueError as e:
        return jsonify(error=str(e)), 400
    except anthropic.AuthenticationError:
        return jsonify(error="That key was rejected by Anthropic - check it and try again."), 400
    except anthropic.APIError as e:
        return jsonify(error=f"Couldn't validate the key: {e.message}"), 502
    return jsonify(ok=True)


@app.post("/api/start")
def start_session():
    cv_file = request.files.get("cv")
    job_spec = (request.form.get("job_spec") or "").strip()
    try:
        num_questions = max(1, min(10, int(request.form.get("num_questions", 6))))
    except ValueError:
        num_questions = 6

    if not coach.has_key():
        return jsonify(error="No API key set - please enter your Claude API key.", needs_key=True), 401
    if len(job_spec) < 50:
        return jsonify(error="Please paste the job spec (at least a few sentences)."), 400

    # CV is optional - without it, questions are based on the job spec alone
    cv_block = None
    if cv_file and cv_file.filename:
        if cv_file.filename.lower().endswith(".doc"):
            return jsonify(error="Old-format .doc files aren't supported - in Word, use Save As and choose .docx."), 400
        if not cv_file.filename.lower().endswith(ALLOWED_CV_EXTENSIONS):
            return jsonify(error="CV must be a PDF, Word (.docx) or plain-text (.txt) file."), 400
        cv_block = coach.build_cv_block(cv_file.filename, cv_file.read())

    try:
        question_set = coach.generate_questions(cv_block, job_spec, num_questions)
    except anthropic.AuthenticationError:
        return jsonify(error="Your API key was rejected - please re-enter it.", needs_key=True), 401
    except anthropic.APIError as e:
        return jsonify(error=f"Claude API error: {e.message}"), 502

    session_id = uuid.uuid4().hex
    SESSIONS[session_id] = {
        "cv_block": cv_block,
        "job_spec": job_spec,
        "questions": [q.model_dump() for q in question_set.questions],
        "answers": {},  # question id -> {transcript, feedback}
    }
    return jsonify(session_id=session_id, questions=SESSIONS[session_id]["questions"])


@app.post("/api/score")
def score_answer():
    data = request.get_json(silent=True) or {}
    session = SESSIONS.get(data.get("session_id", ""))
    transcript = (data.get("transcript") or "").strip()
    question_id = data.get("question_id")

    if not session:
        return jsonify(error="Session not found - please start again."), 404
    question = next((q for q in session["questions"] if q["id"] == question_id), None)
    if not question:
        return jsonify(error="Unknown question."), 400
    if len(transcript) < 20:
        return jsonify(error="The answer is too short to score - try recording again."), 400

    if not coach.has_key():
        return jsonify(error="No API key set - please enter your Claude API key.", needs_key=True), 401

    try:
        feedback = coach.score_answer(
            session["cv_block"], session["job_spec"], question, transcript
        )
    except anthropic.AuthenticationError:
        return jsonify(error="Your API key was rejected - please re-enter it.", needs_key=True), 401
    except anthropic.APIError as e:
        return jsonify(error=f"Claude API error: {e.message}"), 502

    session["answers"][str(question_id)] = {
        "transcript": transcript,
        "feedback": feedback.model_dump(),
    }
    return jsonify(feedback.model_dump())


@app.post("/api/report")
def download_report():
    data = request.get_json(silent=True) or {}
    session = SESSIONS.get(data.get("session_id", ""))
    if not session:
        return jsonify(error="Session not found."), 404

    answered = [
        {"question": q, **session["answers"][str(q["id"])]}
        for q in session["questions"]
        if str(q["id"]) in session["answers"]
    ]
    if not answered:
        return jsonify(error="No answered questions to report on yet."), 400

    scores = [a["feedback"]["overall_score"] for a in answered]
    html = render_template(
        "report.html",
        items=answered,
        report_date=date.today().strftime("%d %B %Y"),
        average_score=round(sum(scores) / len(scores)),
        total_questions=len(session["questions"]),
    )
    return Response(
        html,
        mimetype="text/html",
        headers={
            "Content-Disposition": f"attachment; filename=interview-practice-{date.today().isoformat()}.html"
        },
    )


if __name__ == "__main__":
    port = int(os.environ.get("PORT") or os.environ.get("FLASK_PORT") or 5050)
    app.run(debug=True, port=port)
