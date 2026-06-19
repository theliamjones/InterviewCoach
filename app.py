"""Interview Coach - practise competency-based interview answers with STAR feedback.

Multi-user model: a shared password gate (APP_PASSWORD) protects the app, and each
visitor supplies their own Claude API key, held in memory for their session only
(keyed by a per-browser id in the signed session cookie - the key itself is never
put in the cookie, and is never shared between users). So each user pays for their
own usage and no key is persisted to disk.
"""

import hmac
import os
import secrets
import uuid
from datetime import date

from dotenv import load_dotenv

# Load .env from THIS file's directory, not the current working directory, so
# config is found however the app is launched (start.bat, terminal, gunicorn).
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"), override=True)

import anthropic
from flask import Flask, Response, jsonify, render_template, request, session

import coach

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16 MB upload cap

# The session cookie holds only a random per-browser id + an "authed" flag -
# never the API key. Signed with SECRET_KEY; set a fixed one in production to
# keep logins valid across restarts, otherwise a random one is used per boot.
app.secret_key = os.environ.get("SECRET_KEY") or secrets.token_hex(32)
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    # Secure cookies over HTTPS. Auto-on when any Railway marker is present
    # (names vary), or force with SECURE_COOKIES=1. Left off locally for http.
    SESSION_COOKIE_SECURE=bool(
        os.environ.get("SECURE_COOKIES")
        or os.environ.get("RAILWAY_ENVIRONMENT")
        or os.environ.get("RAILWAY_ENVIRONMENT_NAME")
        or os.environ.get("RAILWAY_PUBLIC_DOMAIN")
    ),
)

# Shared password gate. If APP_PASSWORD is unset the gate is OPEN (handy for
# local dev) - you MUST set APP_PASSWORD on any shared/Railway deployment.
APP_PASSWORD = os.environ.get("APP_PASSWORD", "")
if not APP_PASSWORD:
    app.logger.warning("APP_PASSWORD is not set - the app is OPEN (no password gate).")

# In-memory stores keyed by the per-browser session id (uid). A single gunicorn
# worker (see Procfile) keeps these consistent; both are cleared on restart.
SESSIONS: dict[str, dict] = {}   # practice sessions: session_id -> {uid, ...}
USER_KEYS: dict[str, str] = {}   # uid -> that user's Claude API key (memory only)

ALLOWED_CV_EXTENSIONS = (".pdf", ".docx", ".txt")


@app.before_request
def ensure_uid():
    if "uid" not in session:
        session["uid"] = secrets.token_hex(16)


def is_authed() -> bool:
    return not APP_PASSWORD or session.get("authed") is True


def current_key() -> str:
    return USER_KEYS.get(session.get("uid", ""), "")


def not_ready():
    """Return an (json, status) error tuple if not authed / no key, else None."""
    if not is_authed():
        return jsonify(error="Please enter the access password.", needs_auth=True), 401
    if not current_key():
        return jsonify(error="Please enter your Claude API key.", needs_key=True), 401
    return None


@app.route("/")
def index():
    return render_template("index.html")


@app.get("/api/status")
def status():
    """Tell the front end what gate to show: password, key, or the app itself."""
    return jsonify(gated=bool(APP_PASSWORD), authed=is_authed(), has_key=bool(current_key()))


@app.post("/api/login")
def login():
    password = (request.get_json(silent=True) or {}).get("password", "")
    if not APP_PASSWORD or hmac.compare_digest(password, APP_PASSWORD):
        session["authed"] = True
        return jsonify(ok=True)
    return jsonify(error="Incorrect password."), 401


@app.post("/api/logout")
def logout():
    USER_KEYS.pop(session.get("uid", ""), None)
    session.clear()
    return jsonify(ok=True)


@app.post("/api/key")
def set_key():
    """Validate a user's key and hold it in memory for their session only."""
    if not is_authed():
        return jsonify(error="Please enter the access password.", needs_auth=True), 401
    key = ((request.get_json(silent=True) or {}).get("key") or "").strip()
    try:
        coach.validate_key(key)
    except ValueError as e:
        return jsonify(error=str(e)), 400
    except anthropic.AuthenticationError:
        return jsonify(error="That key was rejected by Anthropic - check it and try again."), 400
    except (anthropic.APITimeoutError, anthropic.APIConnectionError):
        return jsonify(error="Couldn't reach Anthropic to check the key (timed out). Please try again."), 504
    except anthropic.APIError as e:
        return jsonify(error=f"Couldn't validate the key: {e.message}"), 502
    USER_KEYS[session["uid"]] = key
    return jsonify(ok=True)


@app.post("/api/start")
def start_session():
    blocked = not_ready()
    if blocked:
        return blocked

    cv_file = request.files.get("cv")
    job_spec = (request.form.get("job_spec") or "").strip()
    try:
        num_questions = max(1, min(10, int(request.form.get("num_questions", 6))))
    except ValueError:
        num_questions = 6

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
        question_set = coach.generate_questions(current_key(), cv_block, job_spec, num_questions)
    except anthropic.AuthenticationError:
        USER_KEYS.pop(session["uid"], None)  # key went bad - make them re-enter
        return jsonify(error="Your API key was rejected - please re-enter it.", needs_key=True), 401
    except anthropic.APIError as e:
        return jsonify(error=f"Claude API error: {e.message}"), 502

    session_id = uuid.uuid4().hex
    SESSIONS[session_id] = {
        "uid": session["uid"],
        "cv_block": cv_block,
        "job_spec": job_spec,
        "questions": [q.model_dump() for q in question_set.questions],
        "answers": {},  # question id -> {transcript, feedback}
    }
    return jsonify(session_id=session_id, questions=SESSIONS[session_id]["questions"])


def _owned_session(session_id):
    """Look up a practice session, but only if it belongs to this browser."""
    sess = SESSIONS.get(session_id or "")
    if sess and sess.get("uid") == session.get("uid"):
        return sess
    return None


@app.post("/api/score")
def score_answer():
    blocked = not_ready()
    if blocked:
        return blocked

    data = request.get_json(silent=True) or {}
    sess = _owned_session(data.get("session_id"))
    transcript = (data.get("transcript") or "").strip()
    question_id = data.get("question_id")

    if not sess:
        return jsonify(error="Session not found - please start again."), 404
    question = next((q for q in sess["questions"] if q["id"] == question_id), None)
    if not question:
        return jsonify(error="Unknown question."), 400
    if len(transcript) < 20:
        return jsonify(error="The answer is too short to score - try recording again."), 400

    try:
        feedback = coach.score_answer(current_key(), sess["cv_block"], sess["job_spec"], question, transcript)
    except anthropic.AuthenticationError:
        USER_KEYS.pop(session["uid"], None)
        return jsonify(error="Your API key was rejected - please re-enter it.", needs_key=True), 401
    except anthropic.APIError as e:
        return jsonify(error=f"Claude API error: {e.message}"), 502

    sess["answers"][str(question_id)] = {
        "transcript": transcript,
        "feedback": feedback.model_dump(),
    }
    return jsonify(feedback.model_dump())


@app.post("/api/rescore")
def rescore_answer():
    """Re-score an already-answered question, applying a transcript clarification."""
    blocked = not_ready()
    if blocked:
        return blocked

    data = request.get_json(silent=True) or {}
    sess = _owned_session(data.get("session_id"))
    question_id = data.get("question_id")
    clarification = (data.get("clarification") or "").strip()

    if not sess:
        return jsonify(error="Session not found - please start again."), 404
    answer = sess["answers"].get(str(question_id))
    question = next((q for q in sess["questions"] if q["id"] == question_id), None)
    if not answer or not question:
        return jsonify(error="That answer hasn't been scored yet."), 400
    if len(clarification) < 3:
        return jsonify(error="Add a short clarification of what was mis-heard, then re-evaluate."), 400

    try:
        feedback = coach.score_answer(
            current_key(), sess["cv_block"], sess["job_spec"], question,
            answer["transcript"], clarification=clarification
        )
    except anthropic.AuthenticationError:
        USER_KEYS.pop(session["uid"], None)
        return jsonify(error="Your API key was rejected - please re-enter it.", needs_key=True), 401
    except anthropic.APIError as e:
        return jsonify(error=f"Claude API error: {e.message}"), 502

    answer["feedback"] = feedback.model_dump()
    answer["clarification"] = clarification
    return jsonify(feedback.model_dump())


@app.post("/api/report")
def download_report():
    if not is_authed():
        return jsonify(error="Please enter the access password.", needs_auth=True), 401

    data = request.get_json(silent=True) or {}
    sess = _owned_session(data.get("session_id"))
    if not sess:
        return jsonify(error="Session not found."), 404

    answered = [
        {"question": q, **sess["answers"][str(q["id"])]}
        for q in sess["questions"]
        if str(q["id"]) in sess["answers"]
    ]
    if not answered:
        return jsonify(error="No answered questions to report on yet."), 400

    scores = [a["feedback"]["overall_score"] for a in answered]
    html = render_template(
        "report.html",
        items=answered,
        report_date=date.today().strftime("%d %B %Y"),
        average_score=round(sum(scores) / len(scores)),
        total_questions=len(sess["questions"]),
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
