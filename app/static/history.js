window.addEventListener("DOMContentLoaded", async () => {
  if (!initTopbar("history")) return;

  const HISTORY_QUALITY_MODE_KEY = "history_quality_mode";
  const HISTORY_JUDGE_SAMPLES_KEY = "history_judge_samples";

  const list = document.getElementById("stories-list");
  const refreshBtn = document.getElementById("refresh-stories");
  const filterSelect = document.getElementById("history-book-filter");
  const detail = document.getElementById("story-detail");
  const meta = document.getElementById("story-meta");
  const detailTabs = document.querySelectorAll("[data-detail-tab]");
  const storyTabPanel = document.getElementById("story-tab-panel");
  const qualityTabPanel = document.getElementById("quality-tab-panel");
  const exportTxtBtn = document.getElementById("export-story-txt");
  const exportMdBtn = document.getElementById("export-story-md");
  const imageCount = document.getElementById("book-images-count");
  const imageViewer = document.getElementById("book-image-viewer");
  const imageLarge = document.getElementById("book-image-large");
  const imageCaption = document.getElementById("book-image-caption");
  const imageThumbs = document.getElementById("book-image-thumbs");

  const qualityModeSelect = document.getElementById("history-quality-mode");
  const judgeSamplesSelect = document.getElementById("history-judge-samples");
  const refreshQualityBtn = document.getElementById("refresh-quality");
  const qualitySummary = document.getElementById("quality-summary");
  const qualityChecks = document.getElementById("quality-checks");
  const qualityLlmScores = document.getElementById("quality-llm-scores");
  const qualityMetrics = document.getElementById("quality-metrics");
  const qualityJudge = document.getElementById("quality-judge");

  let storiesCache = [];
  let booksCache = [];
  let currentStoryId = null;
  let currentStory = null;
  let scoreLoadToken = 0;
  const baseScoreCache = new Map();
  const bookImagesCache = new Map();

  function safeFilePart(text) {
    return String(text || "story")
      .replace(/[\\/:*?"<>|]+/g, "_")
      .replace(/\s+/g, "_")
      .slice(0, 80);
  }

  function getBookTitle(bookId) {
    const book = findBookById(booksCache, bookId);
    return book?.title || `绘本${bookId}`;
  }

  function downloadTextFile(filename, content, type = "text/plain;charset=utf-8") {
    const blob = new Blob([content], { type });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  }

  function buildStoryExport(format) {
    if (!currentStory) return null;
    const bookTitle = getBookTitle(currentStory.book_id);
    const createdAt = currentStory.created_at || "";
    const storyText = currentStory.story_content || "";

    if (format === "md") {
      return {
        filename: `${safeFilePart(bookTitle)}_故事_${currentStory.id}.md`,
        content: `# ${bookTitle}\n\n- 故事ID：${currentStory.id}\n- 绘本ID：${currentStory.book_id}\n- 创建时间：${createdAt}\n\n---\n\n${storyText}\n`,
        type: "text/markdown;charset=utf-8",
      };
    }

    return {
      filename: `${safeFilePart(bookTitle)}_故事_${currentStory.id}.txt`,
      content: `绘本：${bookTitle}\n故事ID：${currentStory.id}\n绘本ID：${currentStory.book_id}\n创建时间：${createdAt}\n\n${storyText}\n`,
      type: "text/plain;charset=utf-8",
    };
  }

  function updateExportButtons() {
    const disabled = !currentStory;
    if (exportTxtBtn) exportTxtBtn.disabled = disabled;
    if (exportMdBtn) exportMdBtn.disabled = disabled;
  }

  function switchDetailTab(tabName) {
    const isQuality = tabName === "quality";
    detailTabs.forEach((tab) => {
      tab.classList.toggle("active", tab.dataset.detailTab === tabName);
    });
    storyTabPanel?.classList.toggle("active", !isQuality);
    qualityTabPanel?.classList.toggle("active", isQuality);
  }

  function isDeepMode() {
    return qualityModeSelect && qualityModeSelect.value === "deep";
  }

  function loadQualityPreferences() {
    if (!qualityModeSelect || !judgeSamplesSelect) return;
    const savedMode = localStorage.getItem(HISTORY_QUALITY_MODE_KEY);
    if (savedMode === "basic" || savedMode === "deep") {
      qualityModeSelect.value = savedMode;
    }
    const savedSamples = localStorage.getItem(HISTORY_JUDGE_SAMPLES_KEY);
    if (savedSamples && ["1", "2", "3"].includes(savedSamples)) {
      judgeSamplesSelect.value = savedSamples;
    }
  }

  function saveQualityPreferences() {
    if (!qualityModeSelect || !judgeSamplesSelect) return;
    localStorage.setItem(HISTORY_QUALITY_MODE_KEY, qualityModeSelect.value);
    localStorage.setItem(HISTORY_JUDGE_SAMPLES_KEY, judgeSamplesSelect.value);
  }

  function updateModeUI() {
    if (!judgeSamplesSelect) return;
    judgeSamplesSelect.disabled = !isDeepMode();
  }

  function normalizeScoreFromQuality(quality) {
    const scores = quality?.automatic?.scores || {};
    return {
      overall: typeof scores.overall === "number" ? scores.overall : null,
      coherence: typeof scores.coherence === "number" ? scores.coherence : null,
      age: typeof scores.age_appropriateness === "number" ? scores.age_appropriateness : null,
    };
  }

  function renderScoreLine(score) {
    if (!score) return "评分：总分 -- | 连贯性 -- | 年龄适配 --";
    return `评分：总分 ${score.overall ?? "--"} | 连贯性 ${score.coherence ?? "--"} | 年龄适配 ${score.age ?? "--"}`;
  }

  function setCardScore(storyId, score, loading = false) {
    const badgeNode = list.querySelector(`[data-overall-score="${storyId}"]`);
    const lineNode = list.querySelector(`[data-score-line="${storyId}"]`);
    if (loading) {
      if (badgeNode) badgeNode.textContent = "评分中...";
      if (lineNode) lineNode.textContent = "评分加载中...";
      return;
    }
    if (badgeNode) badgeNode.textContent = score?.overall != null ? `总分 ${score.overall}` : "总分 --";
    if (lineNode) lineNode.textContent = renderScoreLine(score);
  }

  function renderStoryDetail(story) {
    currentStory = story;
    updateExportButtons();
    meta.textContent = `故事 #${story.id} | 绘本 ${story.book_id} | 创建时间 ${story.created_at}`;
    detail.textContent = story.story_content || "";
  }

  function renderBookImages(images) {
    if (!imageCount || !imageViewer || !imageLarge || !imageCaption || !imageThumbs) return;

    imageThumbs.innerHTML = "";
    if (!images.length) {
      imageViewer.classList.add("hidden");
      imageLarge.removeAttribute("src");
      imageCaption.textContent = "";
      imageCount.textContent = "该绘本暂无原图";
      imageThumbs.innerHTML = '<div class="item-sub">暂无图片。</div>';
      return;
    }

    imageCount.textContent = `共 ${images.length} 张`;

    function selectImage(image, thumbNode) {
      const url = toPublicImageUrl(image.image_path);
      imageLarge.src = url;
      imageCaption.textContent = `第 ${image.image_order} 页`;
      imageViewer.classList.remove("hidden");
      imageThumbs.querySelectorAll(".book-image-thumb").forEach((node) => node.classList.remove("active"));
      if (thumbNode) thumbNode.classList.add("active");
    }

    images.forEach((image, index) => {
      const thumb = document.createElement("button");
      thumb.className = "book-image-thumb";
      thumb.type = "button";
      thumb.innerHTML = `
        <img src="${toPublicImageUrl(image.image_path)}" alt="第 ${image.image_order} 页" />
        <span>第 ${image.image_order} 页</span>
      `;
      thumb.addEventListener("click", () => selectImage(image, thumb));
      imageThumbs.appendChild(thumb);
      if (index === 0) selectImage(image, thumb);
    });
  }

  async function loadBookImages(bookId) {
    const key = String(bookId || "");
    if (!key) return [];
    if (bookImagesCache.has(key)) return bookImagesCache.get(key);
    const images = await apiRequest(`/api/books/${bookId}/images`);
    const normalized = Array.isArray(images)
      ? images.slice().sort((a, b) => Number(a.image_order || 0) - Number(b.image_order || 0))
      : [];
    bookImagesCache.set(key, normalized);
    return normalized;
  }

  async function loadAndRenderBookImages(bookId) {
    if (imageCount) imageCount.textContent = "原图加载中...";
    if (imageThumbs) imageThumbs.innerHTML = "";
    if (imageViewer) imageViewer.classList.add("hidden");
    try {
      const images = await loadBookImages(bookId);
      renderBookImages(images);
    } catch (error) {
      if (imageCount) imageCount.textContent = "原图加载失败";
      if (imageThumbs) imageThumbs.innerHTML = `<div class="item-sub">${error.message || "请稍后重试"}</div>`;
    }
  }

  function renderQualityEmpty(message = "暂无评分结果。") {
    if (qualityChecks) qualityChecks.innerHTML = "";
    if (qualityLlmScores) {
      qualityLlmScores.innerHTML = "";
      qualityLlmScores.classList.add("hidden");
    }
    if (qualityMetrics) qualityMetrics.innerHTML = "";
    if (qualityJudge) qualityJudge.textContent = "LLM评估：未启用";
    if (qualitySummary) qualitySummary.textContent = message;
  }

  function metricValue(value, fallback = "--") {
    return value === null || value === undefined || value === "" ? fallback : value;
  }

  function renderQuality(quality) {
    if (!quality) {
      renderQualityEmpty();
      return;
    }

    const evidence = quality?.automatic?.evidence || {};
    const metrics = quality?.metrics || {};
    const judge = quality?.judge || {};

    const pageCount = evidence.page_count ?? "--";
    const expectedPages = Array.isArray(evidence.expected_pages) ? evidence.expected_pages.length : "--";
    const missingPages = Array.isArray(evidence.missing_pages) ? evidence.missing_pages : [];
    const hallCount = metrics.hallucination_count ?? 0;
    const hallList = Array.isArray(metrics.hallucinated_entities) ? metrics.hallucinated_entities : [];
    const repeat = metricValue(metrics.repeat_3gram_ratio);
    const distinct2 = metricValue(metrics.distinct_2);

    if (qualityChecks) {
      const pageStatus = missingPages.length === 0 ? "通过" : `缺少 ${missingPages.join("、")}`;
      const hallStatus = Number(hallCount) === 0 ? "通过" : `${hallCount} 个`;
      qualityChecks.innerHTML = `
        <div class="check-card">
          <span class="check-label">页码完整</span>
          <strong>${pageStatus}</strong>
          <small>${pageCount}/${expectedPages} 页</small>
        </div>
        <div class="check-card">
          <span class="check-label">疑似幻觉</span>
          <strong>${hallStatus}</strong>
          <small>${hallList.length ? hallList.join("、") : "未发现明显新增角色"}</small>
        </div>
        <div class="check-card">
          <span class="check-label">文本重复率</span>
          <strong>${repeat}</strong>
          <small>distinct-2 ${distinct2}</small>
        </div>
      `;
    }

    if (qualityMetrics) {
      qualityMetrics.innerHTML = `
        <span class="metric-chip">基础检查：${missingPages.length === 0 && Number(hallCount) === 0 ? "通过" : "需复核"}</span>
        <span class="metric-chip">页码 ${pageCount}/${expectedPages}</span>
        <span class="metric-chip">重复率 ${repeat}</span>
      `;
    }

    if (qualityLlmScores) {
      if (judge.enabled && judge.average_scores) {
        const avg = judge.average_scores;
        qualityLlmScores.classList.remove("hidden");
        qualityLlmScores.innerHTML = `
          <div class="llm-score-card"><span>图文贴合</span><strong>${avg.grounding ?? "-"}</strong></div>
          <div class="llm-score-card"><span>情节连贯</span><strong>${avg.coherence ?? "-"}</strong></div>
          <div class="llm-score-card"><span>儿童可读</span><strong>${avg.readability ?? "-"}</strong></div>
          <div class="llm-score-card"><span>年龄适配</span><strong>${avg.age_appropriateness ?? "-"}</strong></div>
          <div class="llm-score-card"><span>趣味性</span><strong>${avg.interestingness ?? "-"}</strong></div>
        `;
      } else {
        qualityLlmScores.innerHTML = "";
        qualityLlmScores.classList.add("hidden");
      }
    }

    if (qualityJudge) {
      if (judge.enabled && judge.average_scores) {
        qualityJudge.textContent = `LLM深度评估：已完成，模型 ${judge.model || "-"}`;
      } else if (judge.enabled && judge.error) {
        qualityJudge.textContent = `LLM评估失败：${judge.error}`;
      } else {
        qualityJudge.textContent = `LLM评估：${judge.reason || "未启用"}`;
      }
    }

    if (qualitySummary) {
      qualitySummary.textContent = "基础检查用于发现缺页、重复和疑似幻觉；故事质量请优先参考 LLM 深度评估。";
    }
  }

  async function loadStoryQuality(storyId, options = {}) {
    if (!storyId) return null;
    const { refresh = false, cachedOnly = true } = options;
    const includeJudge = isDeepMode();
    const judgeSamples = includeJudge ? Number(judgeSamplesSelect?.value || 1) : null;

    if (qualitySummary) {
      qualitySummary.textContent = refresh ? "评分刷新中..." : "正在读取已保存评分...";
    }

    const query = new URLSearchParams();
    if (includeJudge) {
      query.set("include_judge", "true");
      if (judgeSamples) query.set("judge_samples", String(judgeSamples));
    }
    if (refresh) query.set("refresh", "true");
    if (cachedOnly) query.set("cached_only", "true");

    const suffix = query.toString() ? `?${query.toString()}` : "";
    const quality = await apiRequest(`/api/stories/${storyId}/quality${suffix}`);
    if (!quality) {
      renderQualityEmpty("当前模式暂无已保存评分，请点击“刷新评分”后再查看。");
      return null;
    }

    renderQuality(quality);
    const baseScore = normalizeScoreFromQuality(quality);
    baseScoreCache.set(String(storyId), baseScore);
    setCardScore(storyId, baseScore, false);
    return quality;
  }

  async function fetchCardBaseScore(storyId) {
    const key = String(storyId);
    if (baseScoreCache.has(key)) return baseScoreCache.get(key);
    const quality = await apiRequest(`/api/stories/${storyId}/quality?cached_only=true`);
    if (!quality) return null;
    const score = normalizeScoreFromQuality(quality);
    baseScoreCache.set(key, score);
    return score;
  }

  async function preloadCardScores(stories) {
    const token = ++scoreLoadToken;
    const maxConcurrency = 4;
    let cursor = 0;

    async function worker() {
      while (cursor < stories.length) {
        const index = cursor++;
        const story = stories[index];
        if (!story) continue;

        const storyId = String(story.id);
        if (baseScoreCache.has(storyId)) {
          setCardScore(storyId, baseScoreCache.get(storyId), false);
          continue;
        }

        setCardScore(storyId, null, true);
        try {
          const score = await fetchCardBaseScore(storyId);
          if (token !== scoreLoadToken) return;
          setCardScore(storyId, score, false);
        } catch {
          if (token !== scoreLoadToken) return;
          setCardScore(storyId, null, false);
        }
      }
    }

    const workers = Array.from({ length: Math.min(maxConcurrency, stories.length) }, () => worker());
    await Promise.all(workers);
  }

  async function loadStoryDetail(storyId) {
    const story = await apiRequest(`/api/stories/${storyId}`);
    currentStoryId = story.id;
    renderStoryDetail(story);
    await loadAndRenderBookImages(story.book_id);
    await loadStoryQuality(story.id, { refresh: false, cachedOnly: true });
  }

  function renderBookFilter() {
    filterSelect.innerHTML = '<option value="">全部绘本</option>';
    booksCache.forEach((book) => {
      const option = document.createElement("option");
      option.value = String(book.id);
      option.textContent = `${book.id} - ${book.title}`;
      filterSelect.appendChild(option);
    });

    const queryBookId = new URLSearchParams(window.location.search).get("book_id");
    if (queryBookId && booksCache.some((book) => String(book.id) === String(queryBookId))) {
      filterSelect.value = String(queryBookId);
      setSelectedBookId(queryBookId);
    }
  }

  function getFilteredStories() {
    const selectedBookId = filterSelect.value;
    if (!selectedBookId) return storiesCache;
    return storiesCache.filter((story) => String(story.book_id) === selectedBookId);
  }

  async function handleDeleteStory(storyId, btn) {
    const ok = window.confirm("确认删除这条故事记录吗？删除后不可恢复。");
    if (!ok) return;

    btn.disabled = true;
    const oldText = btn.textContent;
    btn.textContent = "删除中...";
    try {
      await apiRequest(`/api/stories/${storyId}`, { method: "DELETE" });
      baseScoreCache.delete(String(storyId));

      if (String(currentStoryId) === String(storyId)) {
        currentStoryId = null;
        currentStory = null;
        updateExportButtons();
        meta.textContent = "请先在左侧点击“查看详情”。";
        detail.textContent = "";
        if (imageCount) imageCount.textContent = "请选择故事记录";
        if (imageViewer) imageViewer.classList.add("hidden");
        if (imageThumbs) imageThumbs.innerHTML = "";
        renderQualityEmpty();
      }

      await refreshStories();
      showToast("删除成功");
    } catch (error) {
      showToast(error.message);
    } finally {
      btn.disabled = false;
      btn.textContent = oldText;
    }
  }

  function renderStories(stories) {
    list.innerHTML = "";
    if (!stories.length) {
      list.innerHTML = '<div class="item"><div class="item-sub">暂无故事记录。</div></div>';
      meta.textContent = "请先生成故事后再查看。";
      detail.textContent = "";
      currentStory = null;
      updateExportButtons();
      if (imageCount) imageCount.textContent = "请选择故事记录";
      if (imageViewer) imageViewer.classList.add("hidden");
      if (imageThumbs) imageThumbs.innerHTML = "";
      renderQualityEmpty();
      currentStoryId = null;
      return;
    }

    stories.forEach((story) => {
      const fullText = story.story_content || "";
      const previewLimit = 140;
      const previewText = fullText.length > previewLimit ? `${fullText.slice(0, previewLimit)}...` : fullText;
      const score = baseScoreCache.get(String(story.id)) || null;

      const item = document.createElement("div");
      item.className = "item";
      item.innerHTML = `
        <div class="item-title-row">
          <div class="item-title">故事 #${story.id}（绘本 ${story.book_id}）</div>
          <span class="item-score-badge" data-overall-score="${story.id}">
            ${score?.overall != null ? `总分 ${score.overall}` : "总分 --"}
          </span>
        </div>
        <div class="item-score-line" data-score-line="${story.id}">${renderScoreLine(score)}</div>
        <div class="item-sub" data-role="preview">${previewText}</div>
        <div class="item-actions">
          <button class="btn btn-soft btn-danger-soft" data-delete-id="${story.id}" type="button">删除</button>
          <button class="btn btn-soft" data-story-id="${story.id}" type="button">查看详情</button>
        </div>
      `;
      list.appendChild(item);
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

    list.querySelectorAll("button[data-delete-id]").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const storyId = btn.getAttribute("data-delete-id");
        if (!storyId) return;
        await handleDeleteStory(storyId, btn);
      });
    });

    void preloadCardScores(stories);
    void loadStoryDetail(stories[0].id).catch((error) => showToast(error.message));
  }

  function renderStoriesByFilter() {
    renderStories(getFilteredStories());
  }

  async function refreshStories() {
    storiesCache = await apiRequest("/api/stories");
    renderStoriesByFilter();
  }

  filterSelect.addEventListener("change", () => {
    setSelectedBookId(filterSelect.value);
    renderStoriesByFilter();
  });

  detailTabs.forEach((tab) => {
    tab.addEventListener("click", () => {
      switchDetailTab(tab.dataset.detailTab || "story");
    });
  });

  if (qualityModeSelect) {
    qualityModeSelect.addEventListener("change", () => {
      saveQualityPreferences();
      updateModeUI();
      if (currentStoryId) {
        void loadStoryQuality(currentStoryId, { refresh: false, cachedOnly: true }).catch((error) =>
          showToast(error.message)
        );
      }
    });
  }

  if (judgeSamplesSelect) {
    judgeSamplesSelect.addEventListener("change", () => {
      saveQualityPreferences();
      if (currentStoryId && isDeepMode()) {
        void loadStoryQuality(currentStoryId, { refresh: false, cachedOnly: true }).catch((error) =>
          showToast(error.message)
        );
      }
    });
  }

  if (refreshQualityBtn) {
    refreshQualityBtn.addEventListener("click", async () => {
      if (!currentStoryId) {
        showToast("请先选择一条故事");
        return;
      }
      refreshQualityBtn.disabled = true;
      const oldText = refreshQualityBtn.textContent;
      refreshQualityBtn.textContent = "评分中...";
      try {
        await loadStoryQuality(currentStoryId, { refresh: true, cachedOnly: false });
        showToast("评分已刷新");
      } catch (error) {
        showToast(error.message);
      } finally {
        refreshQualityBtn.disabled = false;
        refreshQualityBtn.textContent = oldText;
      }
    });
  }

  if (exportTxtBtn) {
    exportTxtBtn.addEventListener("click", () => {
      const file = buildStoryExport("txt");
      if (!file) {
        showToast("请先选择一条故事记录");
        return;
      }
      downloadTextFile(file.filename, file.content, file.type);
    });
  }

  if (exportMdBtn) {
    exportMdBtn.addEventListener("click", () => {
      const file = buildStoryExport("md");
      if (!file) {
        showToast("请先选择一条故事记录");
        return;
      }
      downloadTextFile(file.filename, file.content, file.type);
    });
  }

  refreshBtn.addEventListener("click", async () => {
    showToast("正在刷新...");
    try {
      await refreshStories();
      showToast("历史记录已刷新");
    } catch (error) {
      showToast(error.message);
    }
  });

  loadQualityPreferences();
  updateModeUI();

  try {
    await apiRequest("/api/users/me");
    booksCache = await loadBooks();
    renderBookFilter();
    await refreshStories();
  } catch (error) {
    clearAuth();
    showToast("登录状态失效，请重新登录");
    setTimeout(() => {
      window.location.href = "/ui/login";
    }, 800);
  }
});
