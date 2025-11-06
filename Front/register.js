const API = "";

/** 🔧 EDITA AQUÍ TUS LISTAS OFICIALES */
const MAGISTRALES = [
  "Fernando Castrillón",
  "Paula Jaramillo",
  "Sebastián Montaño",
  "Tomás Rodríguez",
  "Sara Serrano"
];

const COMPLEMENTARIOS = [
  "Juan Sebastián Arévalo",
  "Nicolás Bello",
  "Sergio Vásquez",
  "Gustavo Castillo",
  "Mariana Crane",
  "Sergio Díaz",
  "María Juliana Otálora",
  "Sofía Ochoa"
];
/** 🔧 FIN DE LA EDICIÓN */

function fillSelect(id, values) {
  const sel = document.getElementById(id);
  sel.innerHTML = "";
  values.forEach(v => {
    const o = document.createElement("option");
    o.value = v; o.textContent = v;
    sel.appendChild(o);
  });
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

document.addEventListener("DOMContentLoaded", () => {
  fillSelect("reg-magistral", MAGISTRALES);
  fillSelect("reg-complementarios", COMPLEMENTARIOS);
});

document.getElementById("btn-register").addEventListener("click", async () => {
  const payload = {
    full_name: document.getElementById("reg-name").value.trim(),
    email: document.getElementById("reg-email").value.trim(),
    uniandes_code: document.getElementById("reg-code").value.trim(),
    magistral: document.getElementById("reg-magistral").value,
    complementarios: document.getElementById("reg-complementarios").value,
    password: document.getElementById("reg-pass").value.trim()
  };
  const res = await postJSON("/api/register", payload);
  if (res.ok) {
    alert("Cuenta creada. Ahora inicia sesión.");
    location.href = "index.html";
  } else {
    alert(res.error || "No fue posible registrar");
  }
});
