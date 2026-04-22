window.addEventListener("DOMContentLoaded", async () => {
  if (!initTopbar("upload")) return;

  const form = document.getElementById("upload-form");
  const bookSelect = document.getElementById("book-select");
  const filesInput = document.getElementById("image-files");
  const startOrderInput = document.getElementById("start-order");

  async function initBooks() {
    const books = await loadBooks();
    fillBookSelect(bookSelect, books);
    bindBookSelectPersist(bookSelect);
  }

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const bookId = bookSelect.value;
    const files = filesInput.files;
    const startOrder = startOrderInput.value || "1";
    if (!bookId) {
      showToast("请先选择绘本");
      return;
    }
    if (!files.length) {
      showToast("请先上传图片");
      return;
    }

    const formData = new FormData();
    for (const file of files) {
      formData.append("files", file);
    }
    formData.append("start_order", startOrder);

    try {
      await apiRequest(`/api/books/${bookId}/images/upload`, {
        method: "POST",
        body: formData,
      });
      showToast("图片上传成功");
      filesInput.value = "";
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
