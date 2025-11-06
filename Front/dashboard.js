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

const selectedTopics = new Set();   // <- aquí guardamos los temas elegidos

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
    document.getElementById("week-status").textContent = `Semana guardada: ${res.week}`;
    // Al cambiar semana, reseteamos selección
    selectedTopics.clear();
    updateTopicsInput();
    loadThemesDifs();
  } else {
    alert(res.error || "Error al guardar semana");
  }
});

function updateTopicsInput() {
  const inp = document.getElementById("inp-theme");
  const arr = Array.from(selectedTopics);
  inp.value = arr.join(", ");
}

async function loadThemesDifs() {
  const data = await getJSON("/api/themes_difs");
  const cont = document.getElementById("temas-list");
  cont.innerHTML = "";

  if (data.error) {
    document.getElementById("topics-hint").textContent = data.error;
    return;
  }

  // Render de chips seleccionables
  (data.temas || []).forEach(t => {
    const chip = document.createElement("span");
    chip.className = "badge tag";
    chip.textContent = t;
    chip.dataset.topic = t;

    // estado visual
    if (selectedTopics.has(t)) chip.classList.add("selected");

    chip.addEventListener("click", () => {
      if (selectedTopics.has(t)) {
        selectedTopics.delete(t);
        chip.classList.remove("selected");
      } else {
        selectedTopics.add(t);
        chip.classList.add("selected");
      }
      updateTopicsInput();
    });

    cont.appendChild(chip);
  });

  // Dificultades
  const sel = document.getElementById("sel-dif");
  sel.innerHTML = "";
  (data.difs || []).forEach(d => {
    const o = document.createElement("option");
    o.value = d; o.textContent = d;
    sel.appendChild(o);
  });

  document.getElementById("topics-hint").textContent =
    "Haz clic en las etiquetas para agregarlas o quitarlas.";
}

document.getElementById("btn-start").addEventListener("click", async () => {
  // Usamos la selección (no el texto escrito)
  const themes = Array.from(selectedTopics).join(", ");
  if (!themes) return alert("Selecciona al menos un tema.");
  const difficulty = parseInt(document.getElementById("sel-dif").value, 10);
  const res = await postJSON("/api/start_quiz", { theme: themes, difficulty });
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

  const uniqueQ = new Set(items.map(x => x.question_id)).size;

  document.getElementById("stats").innerHTML = `
    <div class="stat"><div class="hint">Intentos</div><div class="value">${attempts}</div></div>
    <div class="stat"><div class="hint">Aciertos</div><div class="value ok">${correct}</div></div>
    <div class="stat"><div class="hint">Tasa de acierto</div><div class="value">${accuracy}%</div></div>
    <div class="stat"><div class="hint">Racha actual</div><div class="value">${streak}</div></div>
    <div class="stat"><div class="hint">Preguntas únicas</div><div class="value">${uniqueQ}</div></div>
  `;
}
