window.addEventListener("DOMContentLoaded", async () => {
  if (!initTopbar("history")) return;

  const HISTORY_QUALITY_MODE_KEY = "history_quality_mode";
  const HISTORY_JUDGE_SAMPLES_KEY = "history_judge_samples";

  const list = document.getElementById("stories-list");
  const refreshBtn = document.getElementById("refresh-stories");
  const filterSelect = document.getElementById("history-book-filter");
  const detail = document.getElementById("story-detail");
  const meta = document.getElementById("story-meta");

  const qualityModeSelect = document.getElementById("history-quality-mode");
  const judgeSamplesSelect = document.getElementById("history-judge-samples");
  const refreshQualityBtn = document.getElementById("refresh-quality");
  const qualitySummary = document.getElementById("quality-summary");
  const qualityMetrics = document.getElementById("quality-metrics");
  const qualityJudge = document.getElementById("quality-judge");

  const qOverall = document.getElementById("q-overall");
  const qCoherence = document.getElementById("q-coherence");
  const qAge = document.getElementById("q-age");
  const scoreCardOverall = document.getElementById("score-card-overall");
  const scoreCardCoherence = document.getElementById("score-card-coherence");
  const scoreCardAge = document.getElementById("score-card-age");

  let storiesCache = [];
  let booksCache = [];
  let currentStoryId = null;
  let scoreLoadToken = 0;
  const baseScoreCache = new Map();

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

  function setScoreCardVisual(node, score) {
    if (!node) return;
    node.classList.remove("score-low", "score-mid", "score-high");
    if (typeof score !== "number") return;
    if (score >= 80) node.classList.add("score-high");
    else if (score >= 60) node.classList.add("score-mid");
    else node.classList.add("score-low");
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
    meta.textContent = `故事 #${story.id} | 绘本 ${story.book_id} | 创建时间 ${story.created_at}`;
    detail.textContent = story.story_content || "";
  }

  function renderQualityEmpty(message = "暂无评分结果。") {
    if (qOverall) qOverall.textContent = "--";
    if (qCoherence) qCoherence.textContent = "--";
    if (qAge) qAge.textContent = "--";
    setScoreCardVisual(scoreCardOverall, null);
    setScoreCardVisual(scoreCardCoherence, null);
    setScoreCardVisual(scoreCardAge, null);
    if (qualityMetrics) qualityMetrics.innerHTML = "";
    if (qualityJudge) qualityJudge.textContent = "LLM评估：未启用";
    if (qualitySummary) qualitySummary.textContent = message;
  }

  function renderQuality(quality) {
    if (!quality) {
      renderQualityEmpty();
      return;
    }

    const autoScores = quality?.automatic?.scores || {};
    const metrics = quality?.metrics || {};
    const judge = quality?.judge || {};

    const overall = autoScores.overall;
    const coherence = autoScores.coherence;
    const age = autoScores.age_appropriateness;
    if (qOverall) qOverall.textContent = typeof overall === "number" ? String(overall) : "--";
    if (qCoherence) qCoherence.textContent = typeof coherence === "number" ? String(coherence) : "--";
    if (qAge) qAge.textContent = typeof age === "number" ? String(age) : "--";
    setScoreCardVisual(scoreCardOverall, overall);
    setScoreCardVisual(scoreCardCoherence, coherence);
    setScoreCardVisual(scoreCardAge, age);

    const repeat = metrics.repeat_3gram_ratio ?? "--";
    const distinct2 = metrics.distinct_2 ?? "--";
    const hallCount = metrics.hallucination_count ?? "--";
    const hallList = Array.isArray(metrics.hallucinated_entities) ? metrics.hallucinated_entities : [];
    const hallText = hallList.length > 0 ? `幻觉角色：${hallList.join("、")}` : "幻觉角色：无";

    if (qualityMetrics) {
      qualityMetrics.innerHTML = `
        <span class="metric-chip">重复率 ${repeat}</span>
        <span class="metric-chip">distinct-2 ${distinct2}</span>
        <span class="metric-chip">疑似幻觉 ${hallCount}</span>
        <span class="metric-chip metric-chip-wide">${hallText}</span>
      `;
    }

    if (qualityJudge) {
      if (judge.enabled && judge.average_scores) {
        const avg = judge.average_scores;
        qualityJudge.textContent = `LLM评估：贴合度 ${avg.grounding ?? "-"} | 连贯性 ${avg.coherence ?? "-"} | 可读性 ${avg.readability ?? "-"} | 年龄适配 ${avg.age_appropriateness ?? "-"} | 趣味性 ${avg.interestingness ?? "-"}`;
      } else if (judge.enabled && judge.error) {
        qualityJudge.textContent = `LLM评估失败：${judge.error}`;
      } else {
        qualityJudge.textContent = `LLM评估：${judge.reason || "未启用"}`;
      }
    }

    if (qualitySummary) {
      qualitySummary.textContent = `已更新评分：总分 ${overall ?? "--"}，连贯性 ${coherence ?? "--"}，年龄适配 ${age ?? "--"}`;
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
        meta.textContent = "请先在左侧点击“查看详情”。";
        detail.textContent = "";
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
      renderQualityEmpty();
      currentStoryId = null;
      return;
    }

    stories.forEach((story) => {
      const fullText = story.story_content || "";
      const previewLimit = 140;
      const previewText = fullText.length > previewLimit ? `${fullText.slice(0, previewLimit)}...` : fullText;
      const needExpand = fullText.length > previewLimit;
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
          ${needExpand ? '<button class="btn btn-soft" data-role="toggle" type="button">展开全文</button>' : ""}
          <button class="btn btn-soft btn-danger-soft" data-delete-id="${story.id}" type="button">删除</button>
          <button class="btn btn-soft" data-story-id="${story.id}" type="button">查看详情</button>
        </div>
      `;
      list.appendChild(item);

      const toggleBtn = item.querySelector('button[data-role="toggle"]');
      const previewNode = item.querySelector('[data-role="preview"]');
      if (toggleBtn && previewNode) {
        let expanded = false;
        toggleBtn.addEventListener("click", () => {
          expanded = !expanded;
          previewNode.textContent = expanded ? fullText : previewText;
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

  filterSelect.addEventListener("change", renderStoriesByFilter);

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
