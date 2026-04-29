window.addEventListener("DOMContentLoaded", () => {
  const form = document.getElementById("reset-form");
  const tokenInput = document.getElementById("token");
  const passwordInput = document.getElementById("password");
  const confirmPasswordInput = document.getElementById("confirm-password");

  const params = new URLSearchParams(window.location.search);
  const token = params.get("token");
  if (token) {
    tokenInput.value = token;
  }

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const resetToken = tokenInput.value.trim();
    const password = passwordInput.value;
    const confirmPassword = confirmPasswordInput.value;

    if (password !== confirmPassword) {
      showToast("两次输入的密码不一致");
      return;
    }

    try {
      await apiRequest("/api/users/reset-password", {
        method: "POST",
        body: JSON.stringify({ token: resetToken, password, confirm_password: confirmPassword }),
      });
      showToast("密码重置成功，正在跳转登录页");
      setTimeout(() => {
        window.location.href = "/ui/login";
      }, 700);
    } catch (error) {
      showToast(error.message);
    }
  });
});
