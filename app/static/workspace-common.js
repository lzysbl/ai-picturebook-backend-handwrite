const SELECTED_BOOK_KEY = "selected_book_id";

function getSelectedBookId() {
  return localStorage.getItem(SELECTED_BOOK_KEY) || "";
}

function setSelectedBookId(bookId) {
  if (!bookId) {
    localStorage.removeItem(SELECTED_BOOK_KEY);
    return;
  }
  localStorage.setItem(SELECTED_BOOK_KEY, String(bookId));
}

function markActiveNav(page) {
  document.querySelectorAll("[data-nav]").forEach((node) => {
    node.classList.toggle("active", node.dataset.nav === page);
  });
}

function initTopbar(page) {
  if (!requireLogin()) return false;
  const user = getCurrentUser();
  const userLabel = document.getElementById("user-label");
  if (userLabel) {
    userLabel.textContent = user ? `当前用户：${user.username}` : "未登录";
  }
  const logoutBtn = document.getElementById("logout-btn");
  if (logoutBtn) {
    logoutBtn.addEventListener("click", () => {
      clearAuth();
      window.location.href = "/ui/login";
    });
  }
  markActiveNav(page);
  return true;
}

async function loadBooks() {
  const books = await apiRequest("/api/books");
  return books || [];
}

function fillBookSelect(select, books) {
  select.innerHTML = "";
  books.forEach((book) => {
    const option = document.createElement("option");
    option.value = String(book.id);
    option.textContent = `${book.id} - ${book.title}`;
    select.appendChild(option);
  });

  const saved = getSelectedBookId();
  if (saved && books.some((book) => String(book.id) === saved)) {
    select.value = saved;
  }
  if (!select.value && books.length) {
    select.value = String(books[0].id);
  }
  if (select.value) {
    setSelectedBookId(select.value);
  }
}

function bindBookSelectPersist(select) {
  select.addEventListener("change", () => {
    setSelectedBookId(select.value);
  });
}
