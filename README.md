# Interview Coach

Practise competency-based interview answers **out loud** and get STAR-method feedback from Claude.

Built for anyone going through the recruitment process: paste in a job spec (and optionally your
CV), answer the questions by speaking, and get scored on how well-structured and detailed your
answers are.

> **Everyone uses their own Anthropic (Claude) API key.** It's free to create and pay-as-you-go,
> and a practice session costs only a few pence. Get one at <https://console.anthropic.com>. You
> paste your key into the app when you start; it's held **in memory for your session only** —
> never written to disk, never shared between users, and not stored in this repo.

## How it works

1. **Setup** — paste the job spec, and optionally upload your CV (PDF, Word .docx or .txt).
   Claude generates competency-based questions from the job spec; with a CV they're also
   tailored to your experience, and feedback can flag CV experience you forgot to mention.
2. **Practice** — each question appears on screen. Press **Record** and answer verbally; the
   browser's speech recognition transcribes in the background (you only see a word count
   while speaking, so it feels like a real interview — your transcript first appears
   alongside the feedback).
3. **Feedback** — Claude scores the answer against the **STAR method** (Situation, Task,
   Action, Result — each scored /5), rates depth of detail, colour-codes your transcript
   (green = answered well, amber = should be expanded, red = could be clearer), and lists
   what you missed — including experience on your CV that you didn't bring up.
4. **Report** — download the whole session as a standalone HTML file, with your transcribed
   answers and all feedback, to review and work on.

## Requirements

- [Python 3.10+](https://www.python.org/downloads/)
- An Anthropic API key (see above)
- **Chrome or Edge** to use it (the voice transcription uses the browser's built-in Web Speech
  API, which Firefox doesn't support — there you can type answers instead)

## Run it locally

```powershell
git clone https://github.com/theliamjones/InterviewCoach.git
cd InterviewCoach
py -m pip install -r requirements.txt
copy .env.example .env
# open .env and set APP_PASSWORD (and optionally SECRET_KEY)
```

(On macOS/Linux, use `python3` instead of `py` and `cp` instead of `copy`.)

On Windows, just **double-click `start.bat`** — it launches the app and opens your browser
automatically. Or from a terminal:

```powershell
py app.py
```

Then open <http://localhost:5050> in Chrome or Edge. You'll be asked for the access password
(`APP_PASSWORD`), then for your own Claude API key.

> Leaving `APP_PASSWORD` unset runs the app with **no** password gate — fine for quick local
> testing, but never do that on a shared deployment.

## Deploy to Railway (shared, multi-user)

The app is production-ready behind [gunicorn](https://gunicorn.org/) (see `Procfile`) and is
safe to share: it sits behind a password, and **each visitor supplies their own Claude key**, so
you never pay for anyone else's usage.

1. On [Railway](https://railway.app), create a project from the GitHub repo
   (`theliamjones/InterviewCoach`). Railway auto-detects Python and uses the `Procfile`.
2. Add these service **Variables**:

   | Variable        | Value                                              |
   | --------------- | -------------------------------------------------- |
   | `APP_PASSWORD`  | the shared password you give to people you invite  |
   | `SECRET_KEY`    | a long random string (`python -c "import secrets; print(secrets.token_hex(32))"`) |

3. Deploy, then open the generated URL. Visitors enter the password, then their own API key.

Notes for the shared deployment:
- The single gunicorn worker (in `Procfile`) keeps the in-memory sessions consistent.
- No API keys are stored server-side beyond each user's live session (cleared on restart).
- Secure cookies switch on automatically on Railway.

## Notes

- The CV never leaves your machine except to the Claude API for analysis.
- Sessions are held in memory only — download the report before stopping the server.
- Question generation and scoring use `claude-opus-4-8`; each scoring call costs a few cents
  depending on CV length (the CV is prompt-cached to keep repeat calls cheap).
- Speech recognition quality depends on your microphone. The scoring is told it is judging an
  automatic transcript of speech, so minor mis-transcriptions and filler aren't penalised.

## Configuration (.env / environment variables)

| Variable          | Required | Description                                                                 |
| ----------------- | -------- | --------------------------------------------------------------------------- |
| `APP_PASSWORD`    | shared deploys | Password visitors must enter. If unset, the app is **open** (no gate). |
| `SECRET_KEY`      | recommended | Signs the session cookie. Fixed value keeps logins valid across restarts; random if unset. |
| `SECURE_COOKIES`  | no       | Set to `1` to force HTTPS-only cookies (auto-enabled on Railway).           |
| `PORT`            | no       | Port to serve on (Railway sets this; defaults to `5050` locally).           |

There is no `ANTHROPIC_API_KEY` setting — each user enters their own key in the browser.
