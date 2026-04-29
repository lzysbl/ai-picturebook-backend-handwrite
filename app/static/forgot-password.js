window.addEventListener("DOMContentLoaded", () => {
  const form = document.getElementById("forgot-form");
  const emailInput = document.getElementById("email");
  const resultBox = document.getElementById("reset-result");

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    resultBox.textContent = "";
    try {
      const data = await apiRequest("/api/users/forgot-password", {
        method: "POST",
        body: JSON.stringify({ email: emailInput.value.trim() }),
      });
      showToast("如果该邮箱已注册，系统已生成密码重置链接");
      if (data?.reset_url) {
        resultBox.innerHTML = `演示环境重置入口：<a href="${data.reset_url}">立即重置密码</a>`;
      } else {
        resultBox.textContent = "请检查邮箱中的重置链接。";
      }
    } catch (error) {
      showToast(error.message);
    }
  });
});
