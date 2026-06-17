# Interview Coach

Practise competency-based interview answers **out loud** and get STAR-method feedback from Claude.

Works for anyone: upload a CV and paste a job spec, and the questions are tailored to that
candidate and that role.

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

## Setup

```powershell
cd C:\Liam\Projects\InterviewCoach
py -m pip install -r requirements.txt
copy .env.example .env
# edit .env and add your ANTHROPIC_API_KEY
```

## Run

```powershell
py app.py
```

Then open http://localhost:5050 in **Chrome or Edge** (speech recognition uses the browser's
Web Speech API, which isn't available in Firefox — in unsupported browsers you can type
answers instead).

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
