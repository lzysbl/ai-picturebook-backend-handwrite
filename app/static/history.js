window.addEventListener("DOMContentLoaded", async () => {
  if (!initTopbar("history")) return;

  const list = document.getElementById("stories-list");
  const refreshBtn = document.getElementById("refresh-stories");
  const filterSelect = document.getElementById("history-book-filter");
  const detail = document.getElementById("story-detail");
  const meta = document.getElementById("story-meta");

  let storiesCache = [];
  let booksCache = [];

  function renderStoryDetail(story) {
    meta.textContent = `故事 #${story.id} | 绘本 ${story.book_id} | 创建时间 ${story.created_at}`;
    detail.textContent = story.story_content || "";
  }

  async function loadStoryDetail(storyId) {
    const story = await apiRequest(`/api/stories/${storyId}`);
    renderStoryDetail(story);
  }

  function renderBookFilter() {
    filterSelect.innerHTML = '<option value="">全部绘本</option>';
    booksCache.forEach((book) => {
      const option = document.createElement("option");
      option.value = String(book.id);
      option.textContent = `${book.id} - ${book.title}`;
      filterSelect.appendChild(option);
    });
  }

  function getFilteredStories() {
    const selectedBookId = filterSelect.value;
    if (!selectedBookId) return storiesCache;
    return storiesCache.filter((story) => String(story.book_id) === selectedBookId);
  }

  function renderStories(stories) {
    list.innerHTML = "";
    if (!stories.length) {
      list.innerHTML = '<div class="item"><div class="item-sub">暂无故事记录。</div></div>';
      meta.textContent = "请先生成故事后再查看。";
      detail.textContent = "";
      return;
    }

    stories.forEach((story, index) => {
      const previewLimit = 140;
      const content = story.story_content || "";
      const preview = content.length > previewLimit ? `${content.slice(0, previewLimit)}...` : content;
      const needExpand = content.length > previewLimit;

      const item = document.createElement("div");
      item.className = "item";
      item.innerHTML = `
        <div class="item-title">故事 #${story.id}（绘本 ${story.book_id}）</div>
        <div class="item-sub" data-role="preview">${preview}</div>
        <div class="item-actions">
          ${
            needExpand
              ? `<button class="btn btn-soft" data-role="toggle" type="button">展开全文</button>`
              : ""
          }
          <button class="btn btn-soft" data-story-id="${story.id}" type="button">查看详情</button>
        </div>
      `;
      list.appendChild(item);

      if (index === 0) renderStoryDetail(story);

      const toggleBtn = item.querySelector('button[data-role="toggle"]');
      const previewNode = item.querySelector('[data-role="preview"]');
      if (toggleBtn && previewNode) {
        let expanded = false;
        toggleBtn.addEventListener("click", () => {
          expanded = !expanded;
          previewNode.textContent = expanded ? content : preview;
          toggleBtn.textContent = expanded ? "收起" : "展开全文";
        });
      }
    });

    list.querySelectorAll("button[data-story-id]").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const storyId = btn.getAttribute("data-story-id");
        if (!storyId) return;
        btn.disabled = true;
        const oldText = btn.textContent;
        btn.textContent = "加载中...";
        try {
          await loadStoryDetail(storyId);
        } catch (error) {
          showToast(error.message);
        } finally {
          btn.disabled = false;
          btn.textContent = oldText;
        }
      });
    });
  }

  function renderStoriesByFilter() {
    const filtered = getFilteredStories();
    renderStories(filtered);
  }

  async function refreshStories() {
    storiesCache = await apiRequest("/api/stories");
    renderStoriesByFilter();
  }

  filterSelect.addEventListener("change", renderStoriesByFilter);

  refreshBtn.addEventListener("click", async () => {
    showToast("正在刷新...");
    try {
      await refreshStories();
      showToast("历史记录已刷新");
    } catch (error) {
      showToast(error.message);
    }
  });

  try {
    await apiRequest("/api/users/me");
    booksCache = await loadBooks();
    renderBookFilter();
    await refreshStories();
  } catch (error) {
    clearAuth();
    showToast("登录状态失效，请重新登录");
    setTimeout(() => (window.location.href = "/ui/login"), 800);
  }
});
