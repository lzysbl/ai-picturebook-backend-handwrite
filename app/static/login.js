window.addEventListener("DOMContentLoaded", () => {
  if (getToken()) {
    window.location.href = "/ui/dashboard";
    return;
  }

  const form = document.getElementById("login-form");
  const usernameInput = document.getElementById("username");
  const passwordInput = document.getElementById("password");

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const username = usernameInput.value.trim();
    const password = passwordInput.value;
    try {
      const data = await apiRequest("/api/users/login", {
        method: "POST",
        body: JSON.stringify({ username, password }),
      });
      setAuth(data.access_token, data.user);
      showToast("登录成功，正在进入工作台");
      setTimeout(() => {
        window.location.href = "/ui/dashboard";
      }, 600);
    } catch (error) {
      showToast(error.message);
    }
  });
});
