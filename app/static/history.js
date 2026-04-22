window.addEventListener("DOMContentLoaded", async () => {
  if (!initTopbar("history")) return;

  const list = document.getElementById("stories-list");
  const refreshBtn = document.getElementById("refresh-stories");

  function renderStories(stories) {
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
        <div class="item-sub">${story.story_content.slice(0, 180)}...</div>
      `;
      list.appendChild(item);
    });
  }

  async function refreshStories() {
    const stories = await apiRequest("/api/stories");
    renderStories(stories || []);
  }

  refreshBtn.addEventListener("click", async () => {
    try {
      await refreshStories();
      showToast("历史记录已刷新");
    } catch (error) {
      showToast(error.message);
    }
  });

  try {
    await apiRequest("/api/users/me");
    await refreshStories();
  } catch (error) {
    clearAuth();
    showToast("登录状态失效，请重新登录");
    setTimeout(() => (window.location.href = "/ui/login"), 800);
  }
});
