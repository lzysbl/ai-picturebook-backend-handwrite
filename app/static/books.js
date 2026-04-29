function toPublicImageUrl(path) {
  if (!path) return "";
  const normalized = String(path).replace(/\\/g, "/");
  if (normalized.startsWith("/uploads/")) return normalized;
  if (normalized.startsWith("uploads/")) return `/${normalized}`;
  const marker = "/uploads/";
  const idx = normalized.lastIndexOf(marker);
  if (idx >= 0) return normalized.slice(idx);
  return normalized;
}

window.addEventListener("DOMContentLoaded", async () => {
  if (!initTopbar("books")) return;

  const form = document.getElementById("book-form");
  const titleInput = document.getElementById("book-title");
  const list = document.getElementById("books-list");
  const detailSection = document.getElementById("book-detail-section");
  const detail = document.getElementById("book-detail");
  const closeDetailBtn = document.getElementById("close-book-detail");
  const imagePreviewModal = document.getElementById("image-preview-modal");
  const imagePreviewLarge = document.getElementById("image-preview-large");
  const imagePreviewCaption = document.getElementById("image-preview-caption");
  const closeImagePreviewBtn = document.getElementById("close-image-preview");
  const prevImagePreviewBtn = document.getElementById("prev-image-preview");
  const nextImagePreviewBtn = document.getElementById("next-image-preview");

  let booksCache = [];
  let currentDetailBookId = "";
  let previewImages = [];
  let previewIndex = 0;
  const bookImagesCache = new Map();

  async function loadBookImages(bookId) {
    const key = String(bookId || "");
    if (!key) return [];
    if (bookImagesCache.has(key)) return bookImagesCache.get(key);

    const images = await apiRequest(`/api/books/${bookId}/images`);
    const sortedImages = Array.isArray(images)
      ? [...images].sort((a, b) => Number(a.image_order || 0) - Number(b.image_order || 0))
      : [];
    bookImagesCache.set(key, sortedImages);
    return sortedImages;
  }

  function openStoriesForBook(bookId) {
    setSelectedBookId(bookId);
    window.location.href = `/ui/history?book_id=${encodeURIComponent(bookId)}`;
  }

  function renderImagePreview() {
    if (!imagePreviewModal || !imagePreviewLarge || !imagePreviewCaption) return;
    const current = previewImages[previewIndex];
    if (!current) return;

    imagePreviewLarge.src = current.url;
    imagePreviewCaption.textContent = `${current.caption}（${previewIndex + 1}/${previewImages.length}）`;
    if (prevImagePreviewBtn) prevImagePreviewBtn.disabled = previewIndex <= 0;
    if (nextImagePreviewBtn) nextImagePreviewBtn.disabled = previewIndex >= previewImages.length - 1;
  }

  function openImagePreview(images, startIndex) {
    if (!imagePreviewModal || !imagePreviewLarge || !imagePreviewCaption) return;
    previewImages = images;
    previewIndex = Math.max(0, Math.min(Number(startIndex || 0), previewImages.length - 1));
    renderImagePreview();
    imagePreviewModal.classList.remove("hidden");
    imagePreviewModal.setAttribute("aria-hidden", "false");
    document.body.classList.add("modal-open");
  }

  function moveImagePreview(step) {
    if (!previewImages.length) return;
    const nextIndex = previewIndex + step;
    if (nextIndex < 0 || nextIndex >= previewImages.length) return;
    previewIndex = nextIndex;
    renderImagePreview();
  }

  function closeImagePreview() {
    if (!imagePreviewModal || !imagePreviewLarge) return;
    imagePreviewModal.classList.add("hidden");
    imagePreviewModal.setAttribute("aria-hidden", "true");
    imagePreviewLarge.removeAttribute("src");
    previewImages = [];
    previewIndex = 0;
    document.body.classList.remove("modal-open");
  }

  async function deleteBook(bookId, button) {
    const book = booksCache.find((item) => String(item.id) === String(bookId));
    if (!book) {
      showToast("没有找到该绘本");
      return;
    }

    const ok = window.confirm(`确认删除绘本《${book.title}》吗？相关图片和故事记录也会一并删除。`);
    if (!ok) return;

    const oldText = button?.textContent;
    if (button) {
      button.disabled = true;
      button.textContent = "删除中...";
    }

    try {
      await apiRequest(`/api/books/${bookId}`, { method: "DELETE" });
      bookImagesCache.delete(String(bookId));
      if (getSelectedBookId() === String(bookId)) {
        setSelectedBookId("");
      }
      if (currentDetailBookId === String(bookId)) {
        currentDetailBookId = "";
        detailSection?.classList.add("hidden");
        if (detail) detail.innerHTML = "";
      }
      showToast("删除成功");
      await refreshBooks();
    } catch (error) {
      showToast(error.message || "删除失败");
    } finally {
      if (button) {
        button.disabled = false;
        button.textContent = oldText;
      }
    }
  }

  function renderBookDetail(book, images) {
    if (!detail || !detailSection) return;
    currentDetailBookId = String(book.id);

    const coverUrl = toPublicImageUrl(book.cover_image || images[0]?.image_path);
    const coverHtml = coverUrl
      ? `<img class="book-detail-cover" src="${coverUrl}" alt="${book.title}封面" loading="lazy" />`
      : '<div class="book-detail-cover book-cover-empty">无封面</div>';

    const previewData = images.map((image) => ({
      url: toPublicImageUrl(image.image_path),
      caption: `第 ${image.image_order} 页`,
    }));

    const imagesHtml = images.length
      ? images
          .map((image, index) => {
            const currentPreview = previewData[index];
            return `
              <button class="book-detail-image" type="button" data-preview-index="${index}">
                <img src="${currentPreview.url}" alt="${currentPreview.caption}" loading="lazy" />
                <span>${currentPreview.caption}</span>
              </button>
            `;
          })
          .join("")
      : '<div class="item-sub">该绘本还没有上传图片。</div>';

    detail.innerHTML = `
      <div class="book-detail-header">
        ${coverHtml}
        <div class="book-detail-meta">
          <div class="item-title">${book.title}</div>
          <div class="item-sub">创建时间：${book.created_at}</div>
          <div class="item-sub">图片数量：${images.length} 张</div>
          <div class="item-actions book-detail-actions">
            <a class="btn btn-soft" href="/ui/upload" data-action="upload">继续上传图片</a>
            <a class="btn btn-soft" href="/ui/generate" data-action="generate">生成故事</a>
            <button class="btn btn-primary" type="button" data-action="stories">查看绘本故事</button>
            <button class="btn btn-soft btn-danger-soft" type="button" data-action="delete">删除绘本</button>
          </div>
        </div>
      </div>
      <div class="book-detail-images">
        ${imagesHtml}
      </div>
    `;

    detail.querySelector('[data-action="stories"]')?.addEventListener("click", () => openStoriesForBook(book.id));
    detail.querySelector('[data-action="upload"]')?.addEventListener("click", () => setSelectedBookId(book.id));
    detail.querySelector('[data-action="generate"]')?.addEventListener("click", () => setSelectedBookId(book.id));
    detail.querySelector('[data-action="delete"]')?.addEventListener("click", async (event) => {
      await deleteBook(book.id, event.currentTarget);
    });
    detail.querySelectorAll("[data-preview-index]").forEach((button) => {
      button.addEventListener("click", () => {
        openImagePreview(previewData, Number(button.getAttribute("data-preview-index") || 0));
      });
    });
    detailSection.classList.remove("hidden");
    detailSection.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  async function showBookDetail(bookId, button) {
    const book = booksCache.find((item) => String(item.id) === String(bookId));
    if (!book) {
      showToast("没有找到该绘本");
      return;
    }

    const oldText = button?.textContent;
    if (button) {
      button.disabled = true;
      button.textContent = "加载中...";
    }

    try {
      const images = await loadBookImages(book.id);
      renderBookDetail(book, images);
    } catch (error) {
      showToast(error.message || "绘本详情加载失败");
    } finally {
      if (button) {
        button.disabled = false;
        button.textContent = oldText;
      }
    }
  }

  function renderBooks(books) {
    list.innerHTML = "";
    if (!books.length) {
      list.innerHTML = '<div class="item"><div class="item-sub">暂无绘本，请先创建。</div></div>';
      return;
    }

    books.forEach((book) => {
      const coverUrl = toPublicImageUrl(book.cover_image);
      const coverHtml = coverUrl
        ? `<img class="book-cover" src="${coverUrl}" alt="${book.title}封面" loading="lazy" />`
        : '<div class="book-cover book-cover-empty">无封面</div>';

      const item = document.createElement("div");
      item.className = "item";
      item.innerHTML = `
        <div class="book-item-row">
          ${coverHtml}
          <div class="book-meta">
            <div class="item-title">${book.title}</div>
            <div class="item-sub">创建时间：${book.created_at}</div>
          </div>
        </div>
        <div class="item-actions">
          <button class="btn btn-soft" type="button" data-detail-id="${book.id}">查看绘本详情</button>
          <button class="btn btn-primary" type="button" data-stories-id="${book.id}">查看绘本故事</button>
          <button class="btn btn-soft btn-danger-soft" type="button" data-delete-id="${book.id}">删除绘本</button>
        </div>
      `;
      list.appendChild(item);
    });

    list.querySelectorAll("[data-detail-id]").forEach((button) => {
      button.addEventListener("click", async () => {
        await showBookDetail(button.getAttribute("data-detail-id"), button);
      });
    });

    list.querySelectorAll("[data-stories-id]").forEach((button) => {
      button.addEventListener("click", () => {
        openStoriesForBook(button.getAttribute("data-stories-id"));
      });
    });

    list.querySelectorAll("[data-delete-id]").forEach((button) => {
      button.addEventListener("click", async () => {
        await deleteBook(button.getAttribute("data-delete-id"), button);
      });
    });
  }

  async function refreshBooks() {
    booksCache = await loadBooks();
    renderBooks(booksCache);
  }

  closeDetailBtn?.addEventListener("click", () => {
    currentDetailBookId = "";
    detailSection?.classList.add("hidden");
  });

  closeImagePreviewBtn?.addEventListener("click", closeImagePreview);
  prevImagePreviewBtn?.addEventListener("click", () => moveImagePreview(-1));
  nextImagePreviewBtn?.addEventListener("click", () => moveImagePreview(1));
  imagePreviewModal?.querySelector("[data-close-preview]")?.addEventListener("click", closeImagePreview);
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && imagePreviewModal && !imagePreviewModal.classList.contains("hidden")) {
      closeImagePreview();
    }
    if (imagePreviewModal && !imagePreviewModal.classList.contains("hidden")) {
      if (event.key === "ArrowLeft") moveImagePreview(-1);
      if (event.key === "ArrowRight") moveImagePreview(1);
    }
  });

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const title = titleInput.value.trim();
    if (!title) {
      showToast("请输入绘本标题");
      return;
    }
    try {
      await apiRequest("/api/books", {
        method: "POST",
        body: JSON.stringify({ title }),
      });
      titleInput.value = "";
      showToast("绘本创建成功");
      await refreshBooks();
    } catch (error) {
      showToast(error.message);
    }
  });

  try {
    await apiRequest("/api/users/me");
    await refreshBooks();
  } catch (error) {
    clearAuth();
    showToast("登录状态失效，请重新登录");
    setTimeout(() => (window.location.href = "/ui/login"), 800);
  }
});
