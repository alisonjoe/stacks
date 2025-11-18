const form = document.getElementById("loginForm");
const errorDiv = document.getElementById("error");
const loginBtn = document.getElementById("loginBtn");

form.addEventListener("submit", async (e) => {
  e.preventDefault();

  const username = document.getElementById("username").value;
  const password = document.getElementById("password").value;

  errorDiv.classList.remove("show");
  loginBtn.disabled = true;
  loginBtn.textContent = "Logging in...";

  try {
    const response = await fetch("/login", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      credentials: "same-origin",
      body: JSON.stringify({ username, password }),
    });

    const data = await response.json();

    if (response.ok && data.success) {
      window.location.href = "/";
    } else {
      errorDiv.textContent = data.error || "Login failed";
      errorDiv.classList.add("show");
      loginBtn.disabled = false;
      loginBtn.textContent = "Login";
    }
  } catch (err) {
    errorDiv.textContent = "Connection error. Please try again.";
    errorDiv.classList.add("show");
    loginBtn.disabled = false;
    loginBtn.textContent = "Login";
  }
});
