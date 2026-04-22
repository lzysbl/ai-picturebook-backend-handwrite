const dashboardState = {
  books: [],
};

function renderTopUser() {
  const user = getCurrentUser();
  const userLabel = document.getElementById("user-label");
  userLabel.textContent = user ? `当前用户：${user.username}` : "未登录";
}

function renderBooks() {
  const list = document.getElementById("books-list");
  const select = document.getElementById("book-select");
  list.innerHTML = "";
  select.innerHTML = "";

  if (!dashboardState.books.length) {
    list.innerHTML = '<div class="item"><div class="item-sub">暂无绘本，请先创建。</div></div>';
    return;
  }

  dashboardState.books.forEach((book) => {
    const item = document.createElement("div");
    item.className = "item";
    item.innerHTML = `
      <div class="item-title">${book.title}</div>
      <div class="item-sub">ID: ${book.id} | 创建时间: ${book.created_at}</div>
    `;
    list.appendChild(item);

    const option = document.createElement("option");
    option.value = String(book.id);
    option.textContent = `${book.id} - ${book.title}`;
    select.appendChild(option);
  });
}

function renderStories(stories) {
  const list = document.getElementById("stories-list");
  list.innerHTML = "";
  if (!stories.length) {
    list.innerHTML = '<div class="item"><div class="item-sub">暂无故事记录。</div></div>';
    return;
  }
  stories.forEach((story) => {
    const item = document.createElement("div");
    item.className = "item";
    item.innerHTML = `
      <div class="item-title">故事 #${story.id}（绘本 ${story.book_id}）</div>
      <div class="item-sub">${story.story_content.slice(0, 110)}...</div>
    `;
    list.appendChild(item);
  });
}

async function loadBooks() {
  const books = await apiRequest("/api/books");
  dashboardState.books = books || [];
  renderBooks();
}

async function loadStories() {
  const stories = await apiRequest("/api/stories");
  renderStories(stories || []);
}

function bindCreateBook() {
  const form = document.getElementById("book-form");
  const titleInput = document.getElementById("book-title");
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const title = titleInput.value.trim();
    try {
      await apiRequest("/api/books", {
        method: "POST",
        body: JSON.stringify({ title }),
      });
      titleInput.value = "";
      showToast("绘本创建成功");
      await loadBooks();
    } catch (error) {
      showToast(error.message);
    }
  });
}

function bindUploadImages() {
  const form = document.getElementById("upload-form");
  const select = document.getElementById("book-select");
  const filesInput = document.getElementById("image-files");
  const startOrderInput = document.getElementById("start-order");
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const bookId = select.value;
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
    } catch (error) {
      showToast(error.message);
    }
  });
}

function bindGenerateStory() {
  const form = document.getElementById("generate-form");
  const select = document.getElementById("book-select");
  const promptInput = document.getElementById("prompt");
  const output = document.getElementById("generated-story");
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const bookId = select.value;
    const prompt = promptInput.value.trim();
    if (!bookId) {
      showToast("请先选择绘本");
      return;
    }

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
      await loadStories();
    } catch (error) {
      showToast(error.message);
    }
  });
}

function bindRefreshStories() {
  const button = document.getElementById("refresh-stories");
  button.addEventListener("click", async () => {
    try {
      await loadStories();
      showToast("历史记录已刷新");
    } catch (error) {
      showToast(error.message);
    }
  });
}

function bindLogout() {
  const button = document.getElementById("logout-btn");
  button.addEventListener("click", () => {
    clearAuth();
    window.location.href = "/ui/login";
  });
}

async function bootstrapDashboard() {
  if (!requireLogin()) return;
  renderTopUser();
  bindLogout();
  bindCreateBook();
  bindUploadImages();
  bindGenerateStory();
  bindRefreshStories();

  try {
    await apiRequest("/api/users/me");
    await loadBooks();
    await loadStories();
  } catch (error) {
    clearAuth();
    showToast("登录状态失效，请重新登录");
    setTimeout(() => {
      window.location.href = "/ui/login";
    }, 800);
  }
}

window.addEventListener("DOMContentLoaded", bootstrapDashboard);
