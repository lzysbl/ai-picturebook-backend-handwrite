window.addEventListener("DOMContentLoaded", () => {
  if (getToken()) {
    window.location.href = "/ui/dashboard";
    return;
  }

  const form = document.getElementById("register-form");
  const usernameInput = document.getElementById("username");
  const emailInput = document.getElementById("email");
  const passwordInput = document.getElementById("password");
  const confirmPasswordInput = document.getElementById("confirm-password");
  const hint = document.getElementById("byte-hint");

  passwordInput.addEventListener("input", () => {
    const bytes = new TextEncoder().encode(passwordInput.value).length;
    hint.textContent = `当前密码字节数：${bytes} / 72`;
  });

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const username = usernameInput.value.trim();
    const email = emailInput.value.trim();
    const password = passwordInput.value;
    const confirmPassword = confirmPasswordInput.value;

    if (password !== confirmPassword) {
      showToast("两次输入的密码不一致");
      return;
    }

    try {
      await apiRequest("/api/users/register", {
        method: "POST",
        body: JSON.stringify({ username, email, password, confirm_password: confirmPassword }),
      });
      showToast("注册成功，跳转到登录页");
      setTimeout(() => {
        window.location.href = "/ui/login";
      }, 700);
    } catch (error) {
      showToast(error.message);
    }
  });
});
