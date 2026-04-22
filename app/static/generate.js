window.addEventListener("DOMContentLoaded", async () => {
  if (!initTopbar("generate")) return;

  const form = document.getElementById("generate-form");
  const bookSelect = document.getElementById("book-select");
  const promptInput = document.getElementById("prompt");
  const output = document.getElementById("generated-story");

  async function initBooks() {
    const books = await loadBooks();
    fillBookSelect(bookSelect, books);
    bindBookSelectPersist(bookSelect);
  }

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const bookId = bookSelect.value;
    if (!bookId) {
      showToast("请先选择绘本");
      return;
    }
    const prompt = promptInput.value.trim();
    try {
      const data = await apiRequest("/api/stories/generate", {
        method: "POST",
        body: JSON.stringify({
          book_id: Number(bookId),
          prompt: prompt || null,
        }),
      });
      output.textContent = data.story_content || "";
      showToast("故事生成成功");
      setSelectedBookId(bookId);
    } catch (error) {
      showToast(error.message);
    }
  });

  try {
    await apiRequest("/api/users/me");
    await initBooks();
  } catch (error) {
    clearAuth();
    showToast("登录状态失效，请重新登录");
    setTimeout(() => (window.location.href = "/ui/login"), 800);
  }
});
