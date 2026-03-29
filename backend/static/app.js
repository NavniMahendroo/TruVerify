const form = document.getElementById("verify-form");
const resultEl = document.getElementById("result");
const dropzone = document.getElementById("dropzone");
const fileInput = document.getElementById("cv_file");
const fileNameEl = document.getElementById("file-name");
const submitButton = document.getElementById("submit-btn");
const demoButton = document.getElementById("demo-btn");
const statusText = document.getElementById("status-text");
const scoreValueEl = document.getElementById("score-value");
const meterFill = document.getElementById("meter-fill");
const detailCard = document.getElementById("detail-card");

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function row(key, value) {
  return `
    <div class="row">
      <div class="key">${key}</div>
      <div class="value">${value}</div>
    </div>
  `;
}

function renderAuthenticity(payload) {
  const auth = payload.content_authenticity;
  if (!auth) {
    return "";
  }

  let html = "";
  html += row("Content Authenticity", `${escapeHtml(auth.score_percent)}%`);
  html += row("Risk Level", escapeHtml(String(auth.risk_level).toUpperCase()));
  html += row("Credibility Summary", escapeHtml(auth.summary));

  if (Array.isArray(auth.checks) && auth.checks.length > 0) {
    const checksHtml = auth.checks
      .map((check) => `• ${escapeHtml(check.name)}: ${escapeHtml(check.status)} - ${escapeHtml(check.details)}`)
      .join("<br>");
    html += row("Credential Checks", checksHtml);
  }

  return html;
}

function syncSelectedFileLabel() {
  const file = fileInput.files && fileInput.files[0];
  fileNameEl.textContent = file ? `${file.name} (${Math.ceil(file.size / 1024)} KB)` : "No file selected";
}

function resetResultState() {
  scoreValueEl.textContent = "--";
  meterFill.style.width = "0%";
  detailCard.innerHTML = "";
}

fileInput.addEventListener("change", () => {
  syncSelectedFileLabel();
});

["dragenter", "dragover"].forEach((eventName) => {
  dropzone.addEventListener(eventName, (event) => {
    event.preventDefault();
    dropzone.classList.add("dragover");
  });
});

["dragleave", "drop"].forEach((eventName) => {
  dropzone.addEventListener(eventName, (event) => {
    event.preventDefault();
    dropzone.classList.remove("dragover");
  });
});

dropzone.addEventListener("drop", (event) => {
  const file = event.dataTransfer.files && event.dataTransfer.files[0];
  if (!file) {
    return;
  }
  if (file.type !== "application/pdf") {
    statusText.textContent = "Please drop a valid PDF file.";
    return;
  }

  const dt = new DataTransfer();
  dt.items.add(file);
  fileInput.files = dt.files;
  syncSelectedFileLabel();
  statusText.textContent = "PDF loaded. Ready to verify.";
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  resetResultState();

  submitButton.disabled = true;
  submitButton.textContent = "Verifying...";
  statusText.textContent = "Checking eSeal and preparing AI match...";

  const formData = new FormData(form);

  try {
    const response = await fetch("/api/verify-and-match", {
      method: "POST",
      body: formData,
    });

    const payload = await response.json();

    if (!response.ok) {
      resultEl.classList.remove("hidden");
      detailCard.innerHTML = row("Error", escapeHtml(payload.detail || "Unknown error"));
      scoreValueEl.textContent = "--";
      statusText.textContent = "Request failed.";
      return;
    }

    const statusMarkup = payload.is_verified
      ? '<strong class="good">Verified On-Chain</strong>'
      : '<strong class="bad">No Matching eSeal Found</strong>';

    let detailHtml = "";
    detailHtml += row("Certificate SHA-256", `<span class=\"hash\">${escapeHtml(payload.certificate_hash)}</span>`);
    detailHtml += row("Status", statusMarkup);

    if (payload.is_verified && typeof payload.match_score_percent === "number") {
      const score = Math.max(0, Math.min(100, Number(payload.match_score_percent)));
      scoreValueEl.textContent = `${score.toFixed(2)}%`;
      meterFill.style.width = `${score}%`;
    } else {
      scoreValueEl.textContent = "N/A";
      meterFill.style.width = "0%";
    }

    if (payload.is_verified) {
      detailHtml += row("Issuer", escapeHtml(payload.issuer));
      detailHtml += row("Student Wallet", escapeHtml(payload.student_wallet));
      detailHtml += row("Issued (UTC)", escapeHtml(payload.issued_at_utc));
      detailHtml += row("AI Match Score", `${escapeHtml(payload.match_score_percent)}%`);
      detailHtml += renderAuthenticity(payload);
      statusText.textContent = "Verified and matched successfully.";
    } else {
      statusText.textContent = "No eSeal found for this file hash.";
    }

    resultEl.classList.remove("hidden");
    detailCard.innerHTML = detailHtml;
    resultEl.scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (error) {
    resultEl.classList.remove("hidden");
    detailCard.innerHTML = row("Error", escapeHtml(error.message));
    statusText.textContent = "Network error while verifying.";
  } finally {
    submitButton.disabled = false;
    submitButton.textContent = "Verify & Match";
  }
});

demoButton.addEventListener("click", async (event) => {
  event.preventDefault();
  resetResultState();

  demoButton.disabled = true;
  demoButton.textContent = "Loading Demo...";
  statusText.textContent = "Running interactive demo with pre-sealed resume...";

  const demoJD = `AI/ML Software Engineering Intern (Backend + LLM Applications)

Key Responsibilities:
1. Build backend services using Python and FastAPI for AI-driven applications.
2. Develop LLM workflows using RAG, prompt engineering, and LangChain.
3. Integrate model-serving pipelines (local or API-based) and optimize response quality.
4. Design conversational experiences that adapt to user behavior and context.
5. Work with SQL/NoSQL databases to store user interactions and analytics.

Required Skills:
1. Strong coding in Python and at least one of C++ or JavaScript.
2. Foundation in Machine Learning and practical understanding of LLM applications.
3. Hands-on experience with RAG, prompt engineering, and LangChain.
4. Experience building APIs using FastAPI or similar backend frameworks.
5. Comfort with data tooling such as Pandas and NumPy.
6. Good understanding of SQL and software engineering fundamentals.`;

  try {
    const response = await fetch("/api/demo", {
      method: "GET",
    });

    const payload = await response.json();

    if (!response.ok) {
      detailCard.innerHTML = row("Error", "Demo not available");
      statusText.textContent = "Demo loading failed.";
      return;
    }

    const statusMarkup = payload.is_verified
      ? '<strong class="good">Verified On-Chain</strong>'
      : '<strong class="bad">No Matching eSeal Found</strong>';

    let detailHtml = "";
    detailHtml += row("Certificate SHA-256", `<span class="hash">${escapeHtml(payload.certificate_hash.substring(0, 20))}...</span>`);
    detailHtml += row("Status", statusMarkup);

    if (payload.is_verified && typeof payload.match_score_percent === "number") {
      const score = Math.max(0, Math.min(100, Number(payload.match_score_percent)));
      scoreValueEl.textContent = `${score.toFixed(2)}%`;
      meterFill.style.width = `${score}%`;
    }

    if (payload.is_verified) {
      detailHtml += row("Issuer", escapeHtml(payload.issuer.substring(0, 16)) + "...");
      detailHtml += row("Student Wallet", escapeHtml(payload.student_wallet.substring(0, 16)) + "...");
      detailHtml += row("Issued (UTC)", "2026-03-29T12:23:25+00:00");
      detailHtml += row("AI Match Score", `${escapeHtml(payload.match_score_percent)}%`);
      detailHtml += renderAuthenticity(payload);
      statusText.textContent = "Demo verified and matched successfully.";
    }

    resultEl.classList.remove("hidden");
    detailCard.innerHTML = detailHtml;
    resultEl.scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (error) {
    resultEl.classList.remove("hidden");
    detailCard.innerHTML = row("Error", escapeHtml(error.message));
    statusText.textContent = "Demo error.";
  } finally {
    demoButton.disabled = false;
    demoButton.textContent = "Try Demo";
  }
});
