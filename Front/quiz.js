const API = "";

async function getJSON(url) {
  const r = await fetch(API + url, { credentials: "include" });
  return r.json();
}
async function postJSON(url, body) {
  const r = await fetch(API + url, {
    method: "POST",
    headers: {"Content-Type":"application/json"},
    credentials: "include",
    body: JSON.stringify(body || {})
  });
  return r.json();
}

let current = null;

(async function init() {
  const cached = sessionStorage.getItem("current_question");
  if (cached) {
    current = JSON.parse(cached);
    renderQuestion(current);
    sessionStorage.removeItem("current_question");
  } else {
    const q = await getJSON("/api/question");
    if (q.error) {
      alert(q.error);
      location.href = "dashboard.html";
      return;
    }
    current = q;
    renderQuestion(current);
  }
})();

function renderQuestion(q) {
  document.getElementById("q-meta").innerHTML = `
    <span class="badge">Tema(s): ${q.tema}</span>
    <span class="badge">Dif: ${q.dif}</span>
    <span class="badge">Semana: ${q.week}</span>
  `;
  document.getElementById("q-box").innerHTML = q.html;
  if (window.MathJax) window.MathJax.typeset();
  document.getElementById("feedback").textContent = "";
  document.getElementById("continue-row").style.display = "none";
  document.getElementById("inp-answer").value = "";
}

document.getElementById("btn-send").addEventListener("click", async () => {
  const answer = document.getElementById("inp-answer").value.trim();
  if (!answer) return alert("Escribe tu respuesta (letra).");
  const res = await postJSON("/api/answer", { answer });
  const fb = document.getElementById("feedback");
  fb.innerHTML = res.correct
    ? `<b class="ok">¡Correcto!</b> ¿Deseas continuar?`
    : `<b class="bad">Incorrecta.</b> ¿Deseas continuar?`;
  document.getElementById("continue-row").style.display = "flex";
});

document.getElementById("btn-yes").addEventListener("click", async () => {
  const r = await postJSON("/api/next_question", { continue: true });
  if (r.end) {
    showBye();
  } else {
    renderQuestion(r);
  }
});

document.getElementById("btn-no").addEventListener("click", async () => {
  const r = await postJSON("/api/next_question", { continue: false });
  showBye();
});

function showBye() {
  document.getElementById("bye-overlay").style.display = "flex";
}
