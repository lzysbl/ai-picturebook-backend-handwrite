const TOKEN_KEY = "access_token";
const USER_KEY = "current_user";

function getToken() {
  return localStorage.getItem(TOKEN_KEY) || "";
}

function getCurrentUser() {
  try {
    return JSON.parse(localStorage.getItem(USER_KEY) || "null");
  } catch {
    return null;
  }
}

function setAuth(token, user) {
  localStorage.setItem(TOKEN_KEY, token);
  localStorage.setItem(USER_KEY, JSON.stringify(user));
}

function clearAuth() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
}

function parseErrorMessage(raw) {
  if (!raw) return "请求失败";
  if (typeof raw === "string") return raw;
  if (Array.isArray(raw)) {
    const first = raw[0];
    if (!first) return "请求失败";
    if (typeof first.msg === "string") return first.msg;
    return JSON.stringify(first);
  }
  if (typeof raw.detail === "string") return raw.detail;
  if (Array.isArray(raw.detail)) return parseErrorMessage(raw.detail);
  if (typeof raw.message === "string") return raw.message;
  return "请求失败";
}

async function apiRequest(url, options = {}) {
  const token = getToken();
  const headers = { ...(options.headers || {}) };
  const isForm = options.body instanceof FormData;
  if (!isForm) {
    headers["Content-Type"] = "application/json";
  }
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }

  const response = await fetch(url, { ...options, headers });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(parseErrorMessage(payload));
  }
  if (payload && payload.success === false) {
    throw new Error(parseErrorMessage(payload));
  }
  return payload.data;
}

function showToast(message) {
  const toast = document.getElementById("toast");
  if (!toast) {
    alert(message);
    return;
  }
  toast.textContent = message;
  toast.classList.add("show");
  setTimeout(() => toast.classList.remove("show"), 2200);
}

function requireLogin() {
  if (!getToken()) {
    window.location.href = "/ui/login";
    return false;
  }
  return true;
}
