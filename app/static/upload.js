window.addEventListener("DOMContentLoaded", async () => {
  if (!initTopbar("upload")) return;

  const form = document.getElementById("upload-form");
  const bookSelect = document.getElementById("book-select");
  const filesInput = document.getElementById("image-files");
  const startOrderInput = document.getElementById("start-order");
  const coverPreview = document.getElementById("book-cover-preview");
  const coverImg = document.getElementById("book-cover-preview-img");
  const coverText = document.getElementById("book-cover-preview-text");
  if (!form || !bookSelect || !filesInput || !startOrderInput) return;

  let booksCache = [];

  function updateCoverPreview() {
    if (!coverPreview || !coverImg || !coverText) return;
    const book = findBookById(booksCache, bookSelect.value);
    if (!book) {
      coverPreview.classList.add("hidden");
      return;
    }
    const coverUrl = toPublicImageUrl(book.cover_image);
    coverText.textContent = `当前绘本：${book.title}`;
    if (coverUrl) {
      coverImg.src = coverUrl;
      coverImg.classList.remove("hidden");
    } else {
      coverImg.removeAttribute("src");
      coverImg.classList.add("hidden");
    }
    coverPreview.classList.remove("hidden");
  }

  async function initBooks() {
    booksCache = await loadBooks();
    fillBookSelect(bookSelect, booksCache);
    bindBookSelectPersist(bookSelect);
    updateCoverPreview();
  }

  bookSelect.addEventListener("change", updateCoverPreview);

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
      showToast("请先选择图片文件");
      return;
    }

    showToast("正在上传，请稍候...");
    const formData = new FormData();
    for (const file of files) formData.append("files", file);
    formData.append("start_order", startOrder);

    try {
      await apiRequest(`/api/books/${bookId}/images/upload`, {
        method: "POST",
        body: formData,
      });
      filesInput.value = "";
      setSelectedBookId(bookId);
      showToast("图片上传成功");
      booksCache = await loadBooks();
      updateCoverPreview();
    } catch (error) {
      showToast(error.message);
    }
  });

  try {
    await apiRequest("/api/users/me");
  } catch (error) {
    clearAuth();
    showToast("登录状态失效，请重新登录");
    setTimeout(() => (window.location.href = "/ui/login"), 800);
    return;
  }

  try {
    await initBooks();
  } catch (error) {
    console.error("upload init error:", error);
    showToast(`页面初始化异常：${error.message || "未知错误"}`);
  }
});
