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
            <div class="item-sub">ID: ${book.id} | 创建时间: ${book.created_at}</div>
          </div>
        </div>
      `;
      list.appendChild(item);
    });
  }

  async function refreshBooks() {
    const books = await loadBooks();
    renderBooks(books);
  }

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
