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

(async function init() {
  const me = await getJSON("/api/me");
  if (!me.logged) location.href = "index.html";
  loadThemesDifs(); // por si ya había semana guardada
  renderStats();    // muestra estadísticas
})();

document.getElementById("btn-logout").addEventListener("click", async () => {
  await postJSON("/api/logout");
  location.href = "index.html";
});

document.getElementById("btn-save-week").addEventListener("click", async () => {
  const w = parseInt(document.getElementById("inp-week").value, 10);
  if (!w || w < 1) return alert("Semana inválida");
  const res = await postJSON("/api/set_week", { week: w });
  if (res.ok) {
    document.getElementById("week-status").textContent = `Semana guardada: ${w}`;
    loadThemesDifs();
  } else {
    alert(res.error || "Error al guardar semana");
  }
});

async function loadThemesDifs() {
  const data = await getJSON("/api/themes_difs");
  if (data.error) {
    document.getElementById("topics-hint").textContent = data.error;
    return;
  }
  // Temas
  const cont = document.getElementById("temas-list");
  cont.innerHTML = "";
  data.temas.forEach(t => {
    const b = document.createElement("span");
    b.className = "badge";
    b.textContent = t;
    cont.appendChild(b);
  });
  // Difs
  const sel = document.getElementById("sel-dif");
  sel.innerHTML = "";
  data.difs.forEach(d => {
    const o = document.createElement("option");
    o.value = d; o.textContent = d;
    sel.appendChild(o);
  });
  document.getElementById("topics-hint").textContent = "Escribe uno o más temas, separados por coma, tal como aparecen en las etiquetas.";
}

document.getElementById("btn-start").addEventListener("click", async () => {
  const theme = document.getElementById("inp-theme").value.trim();
  const difficulty = parseInt(document.getElementById("sel-dif").value, 10);
  if (!theme) return alert("Ingresa al menos un tema");
  const res = await postJSON("/api/start_quiz", { theme, difficulty });
  if (res.error) return alert(res.error);
  // Ir a quiz
  sessionStorage.setItem("current_question", JSON.stringify(res));
  location.href = "quiz.html";
});

async function renderStats() {
  const h = await getJSON("/api/history");
  if (h.error) return;

  const items = h.items || [];
  const attempts = items.length;
  const correct = items.filter(x => x.success).length;
  const accuracy = attempts ? Math.round((correct / attempts) * 100) : 0;

  // racha actual de aciertos
  let streak = 0;
  for (const it of items) {
    if (it.success) streak++;
    else break;
  }

  // diversidad de temas (aprox por question_id distintos)
  const uniqueQ = new Set(items.map(x => x.question_id)).size;

  document.getElementById("stats").innerHTML = `
    <div class="stat"><div class="hint">Intentos</div><div class="value">${attempts}</div></div>
    <div class="stat"><div class="hint">Aciertos</div><div class="value ok">${correct}</div></div>
    <div class="stat"><div class="hint">Tasa de acierto</div><div class="value">${accuracy}%</div></div>
    <div class="stat"><div class="hint">Racha actual</div><div class="value">${streak}</div></div>
    <div class="stat"><div class="hint">Preguntas únicas</div><div class="value">${uniqueQ}</div></div>
  `;
}
