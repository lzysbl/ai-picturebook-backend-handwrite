const ACTIVE_STORY_TASK_KEY = "active_story_task_id";

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function getActiveTaskId() {
  return localStorage.getItem(ACTIVE_STORY_TASK_KEY) || "";
}

function setActiveTaskId(taskId) {
  if (!taskId) {
    localStorage.removeItem(ACTIVE_STORY_TASK_KEY);
    return;
  }
  localStorage.setItem(ACTIVE_STORY_TASK_KEY, String(taskId));
}

function setProgress(progressWrap, progressText, progressPercent, progressBar, progress, text) {
  if (!progressWrap || !progressText || !progressPercent || !progressBar) return;
  progressWrap.classList.remove("hidden");
  const safeProgress = Math.max(0, Math.min(100, Number(progress || 0)));
  progressText.textContent = text || "处理中";
  progressPercent.textContent = `${safeProgress}%`;
  progressBar.style.width = `${safeProgress}%`;
}

function renderQuality(qualityPanel, qualitySummary, qualityDetail, quality) {
  if (!qualityPanel || !qualitySummary || !qualityDetail) return;
  if (!quality) {
    qualityPanel.classList.add("hidden");
    qualitySummary.textContent = "";
    qualityDetail.textContent = "";
    qualityDetail.classList.add("hidden");
    return;
  }

  const autoScores = quality?.automatic?.scores || {};
  const metrics = quality?.metrics || {};
  const judge = quality?.judge || {};
  const lines = [];

  const coherence = autoScores.coherence ?? "-";
  const ageFit = autoScores.age_appropriateness ?? "-";
  const overall = autoScores.overall ?? "-";
  const repeat = metrics.repeat_3gram_ratio ?? "-";
  const distinct2 = metrics.distinct_2 ?? "-";
  const hallCount = metrics.hallucination_count ?? "-";
  const hallList = Array.isArray(metrics.hallucinated_entities) ? metrics.hallucinated_entities : [];

  lines.push(`自动评分：整体 ${overall}，连贯性 ${coherence}，年龄适配 ${ageFit}`);
  lines.push(`文本指标：3-gram重复率 ${repeat}，distinct-2 ${distinct2}，疑似幻觉角色数 ${hallCount}`);
  if (hallList.length > 0) {
    lines.push(`疑似不存在角色：${hallList.join("、")}`);
  }

  if (judge.enabled && judge.average_scores) {
    const avg = judge.average_scores;
    lines.push(
      `深度评估(${judge.model || "-"})：` +
      `贴合度 ${avg.grounding ?? "-"}，` +
      `连贯性 ${avg.coherence ?? "-"}，` +
      `可读性 ${avg.readability ?? "-"}，` +
      `年龄适配 ${avg.age_appropriateness ?? "-"}，` +
      `趣味性 ${avg.interestingness ?? "-"}`,
    );
    if (judge.token_usage) {
      lines.push(
        `评估开销：input ${judge.token_usage.input_tokens || 0}，` +
        `output ${judge.token_usage.output_tokens || 0}，` +
        `预估￥${judge.token_usage.estimated_cost_cny || 0}`,
      );
    }
  } else if (judge.enabled && judge.error) {
    lines.push(`深度评估失败：${judge.error}`);
  } else {
    lines.push("深度评估：未启用");
  }

  qualitySummary.textContent = lines.join(" | ");
  qualityDetail.textContent = "";
  qualityDetail.classList.add("hidden");
  qualityPanel.classList.remove("hidden");
}

window.addEventListener("DOMContentLoaded", async () => {
  if (!initTopbar("generate")) return;

  const form = document.getElementById("generate-form");
  const bookSelect = document.getElementById("book-select");
  const promptInput = document.getElementById("prompt");
  const audienceAgeSelect = document.getElementById("audience-age");
  const output = document.getElementById("generated-story");
  if (!form || !bookSelect || !promptInput || !output) return;

  const generationModeInputs = Array.from(document.querySelectorAll('input[name="generation-mode"]'));
  const includeJudgeCheckbox = document.getElementById("include-judge");
  const judgeSamplesSelect = document.getElementById("judge-samples");
  const qualityPanel = document.getElementById("quality-panel");
  const qualitySummary = document.getElementById("quality-summary");
  const qualityDetail = document.getElementById("quality-detail");

  const submitBtn = form.querySelector('button[type="submit"]');
  const progressWrap = document.getElementById("task-progress");
  const progressText = document.getElementById("progress-text");
  const progressPercent = document.getElementById("progress-percent");
  const progressBar = document.getElementById("progress-bar");
  const coverPreview = document.getElementById("book-cover-preview");
  const coverImg = document.getElementById("book-cover-preview-img");
  const coverText = document.getElementById("book-cover-preview-text");

  let booksCache = [];

  function getGenerationMode() {
    const checked = generationModeInputs.find((item) => item.checked);
    return checked?.value || "whole_book";
  }

  if (includeJudgeCheckbox && judgeSamplesSelect) {
    includeJudgeCheckbox.addEventListener("change", () => {
      judgeSamplesSelect.disabled = !includeJudgeCheckbox.checked;
    });
  }

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

  async function waitTaskResult(taskId) {
    const maxPollCount = 240;
    for (let i = 0; i < maxPollCount; i += 1) {
      let task;
      try {
        task = await apiRequest(`/api/stories/tasks/${taskId}`);
      } catch (error) {
        if (String(error.message || "").includes("任务不存在")) setActiveTaskId("");
        throw error;
      }

      setProgress(
        progressWrap,
        progressText,
        progressPercent,
        progressBar,
        task.progress || 0,
        task.current_step || "处理中",
      );

      if (task.status === "completed") {
        setActiveTaskId("");
        return task.result;
      }
      if (task.status === "failed") {
        setActiveTaskId("");
        throw new Error(task.error || "故事生成失败");
      }
      await sleep(1200);
    }
    throw new Error("生成超时，请稍后到历史页查看结果");
  }

  async function resumeTaskIfExists() {
    const taskId = getActiveTaskId();
    if (!taskId || !submitBtn) return;
    showToast("检测到未完成任务，正在恢复进度...");
    submitBtn.disabled = true;
    const oldText = submitBtn.textContent;
    submitBtn.textContent = "恢复中...";

    try {
      const result = await waitTaskResult(taskId);
      output.textContent = result?.story_content || "未返回故事文本";
      renderQuality(qualityPanel, qualitySummary, qualityDetail, result?.quality);
      showToast("故事生成成功");
    } catch (error) {
      showToast(error.message);
    } finally {
      submitBtn.disabled = false;
      submitBtn.textContent = oldText;
    }
  }

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const bookId = bookSelect.value;
    if (!bookId) {
      showToast("请先选择绘本");
      return;
    }

    const prompt = promptInput.value.trim();
    const audienceAge = (audienceAgeSelect?.value || "3-6").trim();
    const includeJudge = Boolean(includeJudgeCheckbox?.checked);
    const judgeSamples = includeJudge ? Number(judgeSamplesSelect?.value || 1) : null;

    output.textContent = "";
    renderQuality(qualityPanel, qualitySummary, qualityDetail, null);
    if (!submitBtn) return;

    submitBtn.disabled = true;
    const oldText = submitBtn.textContent;
    submitBtn.textContent = "提交中...";
    setProgress(progressWrap, progressText, progressPercent, progressBar, 0, "任务已创建，等待执行");

    try {
      const submitData = await apiRequest("/api/stories/generate/submit", {
        method: "POST",
        body: JSON.stringify({
          book_id: Number(bookId),
          prompt: prompt || null,
          audience_age: audienceAge,
          story_length: "long",
          generation_mode: getGenerationMode(),
          include_judge: includeJudge,
          judge_samples: judgeSamples,
        }),
      });

      setActiveTaskId(submitData.task_id);
      const result = await waitTaskResult(submitData.task_id);
      output.textContent = result?.story_content || "未返回故事文本";
      renderQuality(qualityPanel, qualitySummary, qualityDetail, result?.quality);
      setSelectedBookId(bookId);
      showToast("故事生成成功");
    } catch (error) {
      output.textContent = `生成失败：${error.message || "请检查模型配置或稍后再试"}`;
      showToast(error.message);
    } finally {
      submitBtn.disabled = false;
      submitBtn.textContent = oldText;
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
    await resumeTaskIfExists();
  } catch (error) {
    console.error("generate init error:", error);
    showToast(`页面初始化异常：${error.message || "未知错误"}`);
  }
});
