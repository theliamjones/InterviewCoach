# Interview Coach

Practise competency-based interview answers **out loud** and get STAR-method feedback from Claude.

Built for anyone going through the recruitment process: paste in a job spec (and optionally your
CV), answer the questions by speaking, and get scored on how well-structured and detailed your
answers are.

> **You'll need your own Anthropic (Claude) API key** — it's free to create and pay-as-you-go, and
> a practice session costs only a few pence. Get one at <https://console.anthropic.com>. The
> author's key is **not** included (and isn't in this repo).

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

## Setup

```powershell
git clone https://github.com/theliamjones/InterviewCoach.git
cd InterviewCoach
py -m pip install -r requirements.txt
copy .env.example .env
# then open .env and paste in your ANTHROPIC_API_KEY
```

(On macOS/Linux, use `python3` instead of `py` and `cp` instead of `copy`.)

> **No `.env`? No problem.** If a key isn't found when you start the app, it'll ask you to
> paste one in the browser. That key is kept in memory for that run only — never written to
> disk — so it's handy for a quick try without editing files.

## Run

On Windows, just **double-click `start.bat`** — it launches the app and opens your browser
automatically. Or from a terminal:

```powershell
py app.py
```

Then open <http://localhost:5050> in Chrome or Edge.

## Notes

- The CV never leaves your machine except to the Claude API for analysis.
- Sessions are held in memory only — download the report before stopping the server.
- Question generation and scoring use `claude-opus-4-8`; each scoring call costs a few cents
  depending on CV length (the CV is prompt-cached to keep repeat calls cheap).
- Speech recognition quality depends on your microphone. The scoring is told it is judging an
  automatic transcript of speech, so minor mis-transcriptions and filler aren't penalised.

## Configuration (.env)

| Variable            | Required | Description                       |
| ------------------- | -------- | --------------------------------- |
| `ANTHROPIC_API_KEY` | yes      | Your Anthropic API key            |
| `FLASK_PORT`        | no       | Port to serve on (default `5050`) |
