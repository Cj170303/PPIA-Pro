const API = "";

async function postJSON(url, body) {
  const r = await fetch(API + url, {
    method: "POST",
    headers: {"Content-Type":"application/json"},
    credentials: "include",
    body: JSON.stringify(body || {})
  });
  return r.json();
}

document.getElementById("btn-login").addEventListener("click", async () => {
  const email = document.getElementById("login-email").value.trim();
  const pass  = document.getElementById("login-pass").value.trim();
  if (!email || !pass) return alert("Completa correo y contraseña.");
  const res = await postJSON("/api/login", { email, password: pass });
  if (res.ok) {
    location.href = "dashboard.html";
  } else {
    alert(res.error || "No fue posible iniciar sesión");
  }
});
