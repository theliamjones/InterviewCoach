// Interview Coach front end: setup -> record -> feedback -> summary

const state = {
  sessionId: null,
  questions: [],
  current: 0,        // index into questions
  results: [],       // {question, transcript, feedback} for answered questions
};

const $ = (id) => document.getElementById(id);
const steps = ["step-setup", "step-interview", "step-feedback", "step-summary"];

function showStep(id) {
  steps.forEach((s) => $(s).classList.toggle("hidden", s !== id));
  window.scrollTo(0, 0);
}

function setStatus(el, message, kind) {
  el.textContent = message;
  el.className = "status " + (kind || "");
  el.classList.toggle("hidden", !message);
}

function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}

// ---------------------------------------------------------------------------
// Processing overlay (dims the screen + live elapsed timer)
// ---------------------------------------------------------------------------

let overlayTimer = null;

function showOverlay(message) {
  $("overlay-message").textContent = message;
  $("overlay-timer").textContent = "0s";
  $("overlay").classList.remove("hidden");
  const start = Date.now();
  clearInterval(overlayTimer);
  overlayTimer = setInterval(() => {
    $("overlay-timer").textContent = Math.floor((Date.now() - start) / 1000) + "s";
  }, 250);
}

function hideOverlay() {
  clearInterval(overlayTimer);
  overlayTimer = null;
  $("overlay").classList.add("hidden");
}

// ---------------------------------------------------------------------------
// Speech recognition (Web Speech API - Chrome/Edge)
// ---------------------------------------------------------------------------

const SpeechRec = window.SpeechRecognition || window.webkitSpeechRecognition;
const speechSupported = !!SpeechRec;
let recognition = null;
let recording = false;
let finalTranscript = "";

if (!speechSupported) {
  // Fallback mode: no mic, show the typing box instead
  $("no-speech-note").classList.remove("hidden");
  $("record-btn").classList.add("hidden");
} else {
  // The transcript stays hidden until feedback - answering should feel like a real interview
  $("transcript-wrap").classList.add("hidden");
}

function wordCount(text) {
  return text.trim() ? text.trim().split(/\s+/).length : 0;
}

function updateClearButton() {
  $("clear-answer").classList.toggle("hidden", !speechSupported || wordCount(finalTranscript) === 0);
}

function startRecording() {
  recognition = new SpeechRec();
  recognition.lang = $("speech-lang").value;
  recognition.continuous = true;
  recognition.interimResults = true;

  recognition.onresult = (event) => {
    let interim = "";
    for (let i = event.resultIndex; i < event.results.length; i++) {
      const text = event.results[i][0].transcript;
      if (event.results[i].isFinal) {
        finalTranscript += text + " ";
      } else {
        interim += text;
      }
    }
    // Don't show the words - just reassure the user the mic is capturing
    $("record-status").textContent = `Listening... ${wordCount(finalTranscript + interim)} words captured`;
  };

  recognition.onerror = (event) => {
    if (event.error === "not-allowed") {
      $("record-status").textContent = "Microphone access was blocked - allow it and try again.";
    } else if (event.error !== "no-speech") {
      $("record-status").textContent = "Speech error: " + event.error;
    }
  };

  // Chrome stops recognition after silence; restart while the user is still recording.
  recognition.onend = () => {
    if (recording) recognition.start();
  };

  recognition.start();
  recording = true;
  $("record-btn").innerHTML = "&#9632; Stop recording";
  $("record-btn").classList.add("recording");
  $("record-status").textContent = "Listening... speak your answer.";
}

function stopRecording() {
  recording = false;
  if (recognition) recognition.stop();
  $("record-btn").innerHTML = "&#9679; Record answer";
  $("record-btn").classList.remove("recording");
  const n = wordCount(finalTranscript);
  $("record-status").textContent = n
    ? `Answer captured - ${n} words. Record again to add more, or submit for feedback.`
    : "";
  updateClearButton();
}

$("record-btn").addEventListener("click", () => {
  recording ? stopRecording() : startRecording();
});

$("clear-answer").addEventListener("click", () => {
  stopRecording();
  finalTranscript = "";
  $("record-status").textContent = "Answer cleared - press Record to start again.";
  updateClearButton();
});

// ---------------------------------------------------------------------------
// API key gate
// ---------------------------------------------------------------------------

// Show exactly one of the three setup sub-states: password gate, key gate, or
// the setup form itself.
function showGate(which) {
  $("password-panel").classList.toggle("hidden", which !== "password");
  $("key-panel").classList.toggle("hidden", which !== "key");
  $("setup-main").classList.toggle("hidden", which !== "setup");
  showStep("step-setup");
  if (which === "password") $("app-password").focus();
  if (which === "key") $("api-key").focus();
}

function showPasswordPanel(message) {
  showGate("password");
  if (message) setStatus($("password-status"), message, "error");
}

function showKeyPanel(message) {
  showGate("key");
  if (message) setStatus($("key-status"), message, "error");
}

function showSetupMain() {
  showGate("setup");
}

// Decide which gate to show based on server state (password / key / ready).
async function routeToGate() {
  try {
    const s = await (await fetch("/api/status")).json();
    if (s.gated && !s.authed) showPasswordPanel("");
    else if (!s.has_key) showKeyPanel("");
    else showSetupMain();
  } catch {
    showSetupMain(); // if status fails, fall through; calls will re-prompt if needed
  }
}

async function savePassword() {
  const password = $("app-password").value;
  if (!password) {
    setStatus($("password-status"), "Please enter the password.", "error");
    return;
  }
  $("save-password").disabled = true;
  setStatus($("password-status"), "Checking…", "working");
  try {
    const res = await fetch("/api/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ password }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Incorrect password.");
    $("app-password").value = "";
    setStatus($("password-status"), "", "");
    await routeToGate(); // proceed to the key gate or the setup form
  } catch (err) {
    setStatus($("password-status"), err.message, "error");
  } finally {
    $("save-password").disabled = false;
  }
}

async function saveKey() {
  const key = $("api-key").value.trim();
  if (!key) {
    setStatus($("key-status"), "Please paste your API key.", "error");
    return;
  }
  $("save-key").disabled = true;
  setStatus($("key-status"), "Checking your key with Anthropic...", "working");
  try {
    const res = await fetch("/api/key", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ key }),
    });
    const data = await res.json();
    if (!res.ok) {
      if (data.needs_auth) { showPasswordPanel(data.error || "Please enter the password."); return; }
      throw new Error(data.error || "Couldn't validate the key.");
    }
    $("api-key").value = "";
    setStatus($("key-status"), "", "");
    showSetupMain();
  } catch (err) {
    setStatus($("key-status"), err.message, "error");
  } finally {
    $("save-key").disabled = false;
  }
}

$("save-password").addEventListener("click", savePassword);
$("app-password").addEventListener("keydown", (e) => {
  if (e.key === "Enter") { e.preventDefault(); savePassword(); }
});
$("save-key").addEventListener("click", saveKey);
$("api-key").addEventListener("keydown", (e) => {
  if (e.key === "Enter") { e.preventDefault(); saveKey(); }
});

routeToGate();

// ---------------------------------------------------------------------------
// Step 1: setup
// ---------------------------------------------------------------------------

$("setup-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const btn = $("start-btn");
  btn.disabled = true;
  setStatus($("setup-status"), "", "");
  showOverlay("Reading your job spec and drafting tailored questions…");

  try {
    const formData = new FormData($("setup-form"));
    const res = await fetch("/api/start", { method: "POST", body: formData });
    const data = await res.json();
    if (!res.ok) {
      if (data.needs_auth) { showPasswordPanel(data.error || "Please enter the password."); return; }
      if (data.needs_key) { showKeyPanel(data.error || "Please enter your API key."); return; }
      throw new Error(data.error || "Something went wrong.");
    }

    state.sessionId = data.session_id;
    state.questions = data.questions;
    state.current = 0;
    state.results = [];
    showQuestion();
  } catch (err) {
    setStatus($("setup-status"), err.message, "error");
  } finally {
    hideOverlay();
    btn.disabled = false;
  }
});

// ---------------------------------------------------------------------------
// Step 2: interview
// ---------------------------------------------------------------------------

function showQuestion() {
  const q = state.questions[state.current];
  $("progress").textContent = `Question ${state.current + 1} of ${state.questions.length}`;
  $("competency").textContent = q.competency;
  $("question-text").textContent = q.question;
  $("why-asked").textContent = q.why_asked;
  finalTranscript = "";
  $("transcript").value = "";
  $("record-status").textContent = "";
  updateClearButton();
  setStatus($("score-status"), "", "");
  showStep("step-interview");
}

$("submit-answer").addEventListener("click", async () => {
  stopRecording();
  const transcript = (speechSupported ? finalTranscript : $("transcript").value).trim();
  if (transcript.length < 20) {
    setStatus($("score-status"), "Your answer is too short to score - record or type a fuller answer.", "error");
    return;
  }

  $("submit-answer").disabled = true;
  setStatus($("score-status"), "", "");
  showOverlay("Scoring your answer against the STAR method…");

  try {
    const res = await fetch("/api/score", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        session_id: state.sessionId,
        question_id: state.questions[state.current].id,
        transcript,
      }),
    });
    const data = await res.json();
    if (!res.ok) {
      if (data.needs_auth) { showPasswordPanel(data.error || "Please enter the password."); return; }
      if (data.needs_key) { showKeyPanel(data.error || "Please re-enter your API key."); return; }
      throw new Error(data.error || "Something went wrong.");
    }

    state.results.push({ question: state.questions[state.current], transcript, feedback: data });
    renderFeedback(data);
  } catch (err) {
    setStatus($("score-status"), err.message, "error");
  } finally {
    hideOverlay();
    $("submit-answer").disabled = false;
  }
});

$("skip-question").addEventListener("click", () => {
  stopRecording();
  advance();
});

function advance() {
  state.current++;
  if (state.current < state.questions.length) {
    showQuestion();
  } else {
    renderSummary();
  }
}

// ---------------------------------------------------------------------------
// Step 3: feedback
// ---------------------------------------------------------------------------

function renderFeedback(fb) {
  $("overall-score").textContent = fb.overall_score;
  $("depth-score").textContent = fb.depth_score;

  const starGrid = $("star-grid");
  starGrid.innerHTML = "";
  for (const [label, key] of [["Situation", "situation"], ["Task", "task"], ["Action", "action"], ["Result", "result"]]) {
    const c = fb[key];
    starGrid.insertAdjacentHTML("beforeend", `
      <div class="star-card ${c.present ? "" : "missing"}">
        <h4>${label} <span class="star-score">${c.score}/5</span></h4>
        ${c.present ? "" : '<span class="missing-tag">not covered</span>'}
        <p>${escapeHtml(c.feedback)}</p>
      </div>`);
  }

  // Colour-coded answer with numbered notes
  const coded = $("coded-answer");
  const notes = $("seg-notes");
  coded.innerHTML = "";
  notes.innerHTML = "";
  let noteNum = 0;
  for (const seg of fb.segments) {
    let sup = "";
    if (seg.comment && seg.comment.trim()) {
      noteNum++;
      sup = `<sup>${noteNum}</sup>`;
      notes.insertAdjacentHTML("beforeend",
        `<li class="note-${seg.category}">${escapeHtml(seg.comment)}</li>`);
    }
    coded.insertAdjacentHTML("beforeend",
      `<span class="seg-${seg.category}">${escapeHtml(seg.text)}${sup}</span> `);
  }

  $("missed-points").innerHTML = fb.missed_points.map((p) => `<li>${escapeHtml(p)}</li>`).join("");
  $("suggestions").innerHTML = fb.suggestions.map((s) => `<li>${escapeHtml(s)}</li>`).join("");
  $("feedback-summary").textContent = fb.summary;

  const last = state.current === state.questions.length - 1;
  $("next-question").textContent = last ? "Finish session" : "Next question";
  showStep("step-feedback");
}

$("next-question").addEventListener("click", advance);

// ---------------------------------------------------------------------------
// Step 4: summary + report download
// ---------------------------------------------------------------------------

function renderSummary() {
  if (state.results.length === 0) {
    // Everything was skipped - go back to setup
    showStep("step-setup");
    setStatus($("setup-status"), "No questions were answered. Start again when you're ready.", "");
    return;
  }
  const avg = Math.round(state.results.reduce((s, r) => s + r.feedback.overall_score, 0) / state.results.length);
  $("avg-score").textContent = avg;
  $("results-list").innerHTML = state.results.map((r) => `
    <li><span class="result-score">${r.feedback.overall_score}</span>
        <span><strong>${escapeHtml(r.question.competency)}</strong><br>${escapeHtml(r.question.question)}</span>
    </li>`).join("");
  showStep("step-summary");
}

$("download-report").addEventListener("click", async () => {
  const res = await fetch("/api/report", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: state.sessionId }),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    alert(data.error || "Could not build the report.");
    return;
  }
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `interview-practice-${new Date().toISOString().slice(0, 10)}.html`;
  a.click();
  URL.revokeObjectURL(url);
});

$("restart").addEventListener("click", () => {
  state.sessionId = null;
  $("setup-form").reset();
  showStep("step-setup");
});
