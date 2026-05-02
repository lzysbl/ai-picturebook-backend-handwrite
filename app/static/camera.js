window.addEventListener("DOMContentLoaded", async () => {
  if (!initTopbar("camera")) return;
  document.body.classList.add("camera-page-body");

  function syncMobileNavigation() {
    syncCameraMobileNavigation();
  }

  syncMobileNavigation();
  window.addEventListener("resize", syncMobileNavigation);
  updateBrowserWarning();

  const startBtn = document.getElementById("start-camera");
  const captureBtn = document.getElementById("capture-frame");
  const toggleAutoScanBtn = document.getElementById("toggle-auto-scan");
  const rescanBtn = document.getElementById("rescan-frame");
  const ttsPlayBtn = document.getElementById("camera-tts-play");
  const ttsAudio = document.getElementById("camera-tts-audio");
  const resetLiveStoryBtn = document.getElementById("reset-live-story");
  const saveLiveStoryBtn = document.getElementById("save-live-story");
  const video = document.getElementById("camera-video");
  const canvas = document.getElementById("camera-canvas");
  const browserWarning = document.getElementById("camera-browser-warning");
  const cameraStage = document.querySelector(".camera-stage");
  const emptyHint = document.getElementById("camera-empty");
  const guideBox = document.getElementById("camera-page-box");
  const guideBoxLabel = document.getElementById("camera-page-box-label");
  const detectedBox = document.getElementById("camera-detected-box");
  const detectedBoxLabel = document.getElementById("camera-detected-box-label");
  const statusNode = document.getElementById("camera-status");
  const styleSelect = document.getElementById("camera-style");
  const ageSelect = document.getElementById("camera-age");
  const modeSelect = document.getElementById("camera-mode");
  const promptInput = document.getElementById("camera-prompt");
  const pageStateNode = document.getElementById("camera-page-state");
  const stabilityStateNode = document.getElementById("camera-stability-state");
  const signatureStateNode = document.getElementById("camera-signature-state");
  const contextStateNode = document.getElementById("camera-context-state");
  const cropStateNode = document.getElementById("camera-crop-state");
  const resultMeta = document.getElementById("camera-result-meta");
  const storyOutput = document.getElementById("camera-story-output");
  const totalStoryOutput = document.getElementById("camera-total-output");
  const qualityPanel = document.getElementById("camera-quality-panel");
  const qualitySummary = document.getElementById("camera-quality-summary");
  const analysisOutput = document.getElementById("camera-analysis-output");
  const cameraTabs = Array.from(document.querySelectorAll("[data-camera-tab]"));
  const storyPanel = document.getElementById("camera-story-panel");
  const totalPanel = document.getElementById("camera-total-panel");
  const debugPanel = document.getElementById("camera-debug-panel");
  const mobileResult = document.getElementById("camera-mobile-result");
  const mobileMeta = document.getElementById("camera-mobile-meta");
  const mobileStory = document.getElementById("camera-mobile-story");
  const mobileToggleBtn = document.getElementById("camera-mobile-toggle");
  const mobileOpenDetailBtn = document.getElementById("camera-mobile-open-detail");
  const mobileTtsBtn = document.getElementById("camera-mobile-tts");

  let stream = null;
  let isScanning = false;
  let lastCaptureAt = 0;
  let lastFrameSignature = "";
  let lastScannedSignature = "";
  let stableFrameCount = 0;
  let scanSessionId = globalThis.crypto?.randomUUID?.() || `scan-${Date.now()}`;
  let currentGuideBox = null;
  let currentDetectedBox = null;
  let latestStoryText = "";
  let latestStoryAudioKey = "";
  let latestAnalysisResult = [];
  let pageStories = [];
  let activeCameraTab = "story";
  let continuousScanEnabled = false;
  let continuousReadingEnabled = false;
  let ttsQueue = [];
  let isPreparingQueuedTTS = false;

  const STABLE_FRAMES_REQUIRED = 2;
  const SIGNATURE_DIFF_THRESHOLD = 18;

  function detectEmbeddedBrowser() {
    const ua = navigator.userAgent || "";
    if (/MicroMessenger/i.test(ua)) return "wechat";
    if (/\bQQ\/|\bMQQBrowser\/|\bQQBrowser\//i.test(ua)) return "qq";
    return "";
  }

  function updateBrowserWarning() {
    if (!browserWarning) return;
    const embedded = detectEmbeddedBrowser();
    if (!embedded) {
      browserWarning.classList.add("hidden");
      browserWarning.textContent = "";
      return;
    }
    browserWarning.classList.remove("hidden");
    browserWarning.textContent =
      embedded === "wechat"
        ? "当前正在微信内打开。微信内置浏览器可能无法稳定调用摄像头，建议点击右上角后选择“在浏览器打开”。"
        : "当前正在 QQ 内打开。QQ 内置浏览器可能无法稳定调用摄像头，建议点击右上角后选择“在浏览器打开”。";
  }

  async function ensureAuth() {
    try {
      await apiRequest("/api/users/me");
    } catch (error) {
      clearAuth();
      showToast("登录状态失效，请重新登录");
      setTimeout(() => (window.location.href = "/ui/login"), 800);
      throw error;
    }
  }

  function setStatus(text) {
    if (statusNode) statusNode.textContent = text;
  }

  function syncEmptyHintVisibility() {
    if (!emptyHint) return;
    const hasStream = Boolean(video?.srcObject || stream);
    emptyHint.classList.toggle("hidden", hasStream);
    cameraStage?.classList.toggle("is-live", hasStream);
  }

  function updateMobileResult(summary, story) {
    if (!mobileResult || !mobileMeta || !mobileStory) return;
    mobileMeta.textContent = summary || "识别结果";
    const compact = String(story || "").split("\n").slice(0, 5).join("\n");
    mobileStory.textContent = compact;
    mobileResult.classList.remove("hidden");
    if (mobileTtsBtn) mobileTtsBtn.disabled = !String(story || "").trim();
    if (window.matchMedia && window.matchMedia("(max-width: 900px)").matches) {
      mobileResult.classList.add("expanded", "has-result");
      if (mobileToggleBtn) mobileToggleBtn.textContent = "收起";
    }
  }

  function setTtsAudioSource(audioUrl, storyKey) {
    if (!ttsAudio || !audioUrl) return;
    ttsAudio.src = audioUrl;
    ttsAudio.dataset.storyKey = storyKey || "";
    ttsAudio.classList.remove("hidden");
  }

  function makeStoryAudioKey(text) {
    const value = String(text || "");
    return `${value.length}:${value.slice(0, 24)}:${value.slice(-24)}`;
  }

  function isAudioPlaying() {
    return Boolean(ttsAudio && !ttsAudio.paused && !ttsAudio.ended && ttsAudio.currentTime > 0);
  }

  function updateTtsButtonState() {
    const readableText = getReadableStoryText();
    const isTotalTab = activeCameraTab === "total";
    if (ttsPlayBtn) {
      ttsPlayBtn.disabled = !readableText || isPreparingQueuedTTS;
      ttsPlayBtn.textContent = isPreparingQueuedTTS
        ? "生成语音中..."
        : ttsQueue.length
          ? `朗读${isTotalTab ? "总故事" : "当前页"}（队列 ${ttsQueue.length}）`
          : `朗读${isTotalTab ? "总故事" : "当前页"}`;
    }
    if (mobileTtsBtn) {
      mobileTtsBtn.disabled = !readableText || isPreparingQueuedTTS;
      mobileTtsBtn.textContent = ttsQueue.length ? `朗读队列(${ttsQueue.length})` : "朗读";
    }
  }

  function updateSaveStoryButtonState() {
    if (!saveLiveStoryBtn) return;
    saveLiveStoryBtn.disabled = isScanning || !getTotalStoryText().trim();
  }

  function clearTtsAudio(options = {}) {
    const { stopCurrent = true, clearQueue = false } = options;
    latestStoryAudioKey = "";
    if (clearQueue) {
      ttsQueue = [];
    }
    if (ttsAudio && stopCurrent) {
      ttsAudio.pause();
      ttsAudio.removeAttribute("src");
      ttsAudio.dataset.storyKey = "";
      ttsAudio.load();
      ttsAudio.classList.add("hidden");
    }
    updateTtsButtonState();
  }

  function clearRecognitionResult(message = "已清空上次识别结果，请重新识别当前页。", options = {}) {
    const { clearQueue = false, clearTotal = false } = options;
    latestStoryText = "";
    latestAnalysisResult = [];
    clearTtsAudio({ stopCurrent: false, clearQueue });
    if (storyOutput) storyOutput.textContent = "正在等待新的识别结果...";
    if (clearTotal) {
      pageStories = [];
      if (totalStoryOutput) totalStoryOutput.textContent = "开启“连续识别”后，每识别一页都会累积到这里。";
    }
    if (resultMeta) resultMeta.textContent = "已清空上次识别结果。";
    if (qualityPanel) qualityPanel.classList.add("hidden");
    if (qualitySummary) qualitySummary.textContent = "";
    if (analysisOutput) analysisOutput.textContent = "";
    if (mobileStory) mobileStory.textContent = "";
    if (mobileMeta) mobileMeta.textContent = "等待新的识别结果";
    setStatus(message);
    updateSaveStoryButtonState();
  }

  function updateContinuousScanButton() {
    if (!toggleAutoScanBtn) return;
    toggleAutoScanBtn.textContent = continuousScanEnabled ? "连续识别：开" : "连续识别：关";
    toggleAutoScanBtn.setAttribute("aria-pressed", continuousScanEnabled ? "true" : "false");
    toggleAutoScanBtn.classList.toggle("is-active", continuousScanEnabled);
  }

  function setContinuousScanEnabled(enabled) {
    continuousScanEnabled = Boolean(enabled);
    updateContinuousScanButton();
    if (continuousScanEnabled) {
      setStatus("连续识别已开启：每次点击识别会沿用前序页面上下文。");
      showToast("连续识别已开启");
    } else {
      scanSessionId = globalThis.crypto?.randomUUID?.() || `scan-${Date.now()}`;
      stableFrameCount = 0;
      lastFrameSignature = "";
      lastScannedSignature = "";
      pageStories = [];
      if (totalStoryOutput) totalStoryOutput.textContent = "开启“连续识别”后，每识别一页都会累积到这里。";
      updateContextBadge({ recent_page_count: 0, character_registry: [] });
      updateSaveStoryButtonState();
      setStatus("连续识别已关闭：下一次识别只讲当前页。");
      showToast("连续识别已关闭");
    }
  }

  async function synthesizeStoryAudio(text) {
    const data = await apiRequest("/api/stories/tts", {
      method: "POST",
      body: JSON.stringify({ text }),
    });
    const audioUrl = data?.audio_url;
    if (!audioUrl) throw new Error("未返回音频地址");
    return data;
  }

  async function playAudioUrl(audioUrl, storyKey) {
    if (!ttsAudio || !audioUrl) return;
    latestStoryAudioKey = storyKey || "";
    setTtsAudioSource(audioUrl, storyKey);
    await ttsAudio.play();
  }

  async function queueStoryForContinuousReading(text, reason = "next-page") {
    const cleanText = String(text || "").trim();
    if (!cleanText || !continuousReadingEnabled) return;
    const storyKey = makeStoryAudioKey(cleanText);
    if (ttsQueue.some((item) => item.storyKey === storyKey) || latestStoryAudioKey === storyKey) return;

    isPreparingQueuedTTS = true;
    updateTtsButtonState();
    try {
      const data = await synthesizeStoryAudio(cleanText);
      ttsQueue.push({
        storyKey,
        text: cleanText,
        audioUrl: data.audio_url,
      });
      const segmentText = Number(data?.segment_count || 1) > 1 ? `，分 ${data.segment_count} 段` : "";
      showToast(`新讲述已加入朗读队列${segmentText}`);
      if (!isAudioPlaying() && ttsAudio?.paused) {
        playNextQueuedAudio();
      }
    } catch (error) {
      showToast(error.message || "新讲述语音生成失败");
    } finally {
      isPreparingQueuedTTS = false;
      updateTtsButtonState();
    }
  }

  async function playNextQueuedAudio() {
    if (!ttsQueue.length || isAudioPlaying()) return;
    const next = ttsQueue.shift();
    updateTtsButtonState();
    try {
      await playAudioUrl(next.audioUrl, next.storyKey);
    } catch (error) {
      showToast(error.message || "队列朗读失败");
    }
  }

  function toggleMobileResult() {
    if (!mobileResult || !mobileToggleBtn) return;
    const expanded = mobileResult.classList.toggle("expanded");
    mobileToggleBtn.textContent = expanded ? "收起" : "展开";
  }

  function switchCameraTab(tabName) {
    activeCameraTab = tabName;
    cameraTabs.forEach((tab) => {
      tab.classList.toggle("active", tab.dataset.cameraTab === tabName);
    });
    storyPanel?.classList.toggle("active", tabName === "story");
    totalPanel?.classList.toggle("active", tabName === "total");
    debugPanel?.classList.toggle("active", tabName === "debug");
    updateTtsButtonState();
  }

  function toggleMobileDetailPanel(forceOpen = null) {
    const panel = document.querySelector(".camera-result-panel");
    if (!panel) return;
    const shouldOpen = forceOpen === null ? !panel.classList.contains("mobile-open") : Boolean(forceOpen);
    panel.classList.toggle("mobile-open", shouldOpen);
    if (mobileOpenDetailBtn) mobileOpenDetailBtn.textContent = shouldOpen ? "关闭详情" : "详情";
    if (shouldOpen) switchCameraTab("story");
  }

  function updateStateBadges({ pageState, stabilityText, signatureText } = {}) {
    if (pageStateNode && pageState) pageStateNode.textContent = pageState;
    if (stabilityStateNode && stabilityText) stabilityStateNode.textContent = stabilityText;
    if (signatureStateNode && signatureText) signatureStateNode.textContent = signatureText;
  }

  function updateContextBadge(context) {
    if (!contextStateNode) return;
    const count = Number(context?.recent_page_count || 0);
    const roles = Array.isArray(context?.character_registry) ? context.character_registry : [];
    contextStateNode.textContent = `连续讲述：${count} 页${roles.length ? ` | 角色 ${roles.slice(0, 3).join("、")}` : ""}`;
  }

  function updateCropBadge(cropMode) {
    if (!cropStateNode) return;
    const textMap = {
      frontend_crop: "前端框裁剪",
      model_crop: "后端检测裁剪",
      guide_crop: "引导框裁剪",
      full_frame: "整图",
      cropped: "页面裁剪",
    };
    cropStateNode.textContent = `裁剪模式：${textMap[cropMode] || "整图"}`;
  }

  function getTotalStoryText() {
    if (!pageStories.length) return "";
    return pageStories.map((item, index) => `第${index + 1}页：${item.text}`).join("\n\n");
  }

  function getReadableStoryText() {
    if (activeCameraTab === "total") {
      return getTotalStoryText().trim();
    }
    return String(latestStoryText || "").trim();
  }

  function updateStoryOutputs(currentText, result, replaceLastPage) {
    const cleanText = String(currentText || "").trim();
    latestStoryText = cleanText;
    if (storyOutput) storyOutput.textContent = cleanText || "未返回讲述文本";

    if (continuousScanEnabled || replaceLastPage) {
      const contextCount = Number(result?.context?.recent_page_count || 0);
      const pageNo = contextCount > 0 ? contextCount : pageStories.length + 1;
      const nextPage = { page: pageNo, text: cleanText, image_path: result?.scan_image_path || "" };
      if (replaceLastPage && pageStories.length) {
        pageStories[pageStories.length - 1] = nextPage;
      } else if (cleanText) {
        pageStories.push(nextPage);
      }
    } else {
      pageStories = cleanText ? [{ page: 1, text: cleanText, image_path: result?.scan_image_path || "" }] : [];
    }

    const totalText = getTotalStoryText();
    if (totalStoryOutput) {
      totalStoryOutput.textContent = totalText || "开启“连续识别”后，每识别一页都会累积到这里。";
    }
    updateSaveStoryButtonState();
    return totalText;
  }

  function applyScanSuccessState(signature, replaceLastPage) {
    lastScannedSignature = signature;
    stableFrameCount = 0;
    lastFrameSignature = signature;
    updateStateBadges({
      pageState: replaceLastPage ? "页面状态：当前页已刷新" : "页面状态：当前页识别完成",
      stabilityText: `稳定帧：0 / ${STABLE_FRAMES_REQUIRED}`,
      signatureText: "重复检测：已记录当前页",
    });
    setStatus(
      replaceLastPage
        ? "重新识别完成，当前页讲述已刷新。"
        : continuousScanEnabled
          ? "识别完成。翻到下一页后再次点击识别即可连续讲述。"
          : "识别完成。当前为单页讲述模式。",
    );
    showToast(replaceLastPage ? "当前页已重新识别" : "实时识别完成");
  }

  function parseSseEvents(buffer, onEvent) {
    return parseCameraSseEvents(buffer, onEvent);
  }

  async function apiRequestStream(url, formData, onEvent) {
    await apiRequestCameraStream(url, formData, onEvent);
  }

  async function scanCurrentFrameStream(formData, signature, replaceLastPage) {
    let streamedText = "";
    let finalResult = null;
    latestStoryText = "";
    if (storyOutput) storyOutput.textContent = "";
    if (resultMeta) resultMeta.textContent = "快速讲述生成中...";
    if (qualityPanel) qualityPanel.classList.add("hidden");
    setStatus("正在连接大模型，讲述会边生成边显示...");

    await apiRequestStream("/api/stories/scan/stream", formData, (event) => {
      if (event.type === "meta") {
        updateContextBadge(event.context || null);
        updateCropBadge(event.crop_mode || "full_frame");
        if (event.crop_box) {
          currentDetectedBox = event.crop_box;
          setDetectedBox(currentDetectedBox, "流式裁剪区域");
        }
        return;
      }
      if (event.type === "delta") {
        streamedText += event.text || "";
        latestStoryText = streamedText.trim();
        if (storyOutput) storyOutput.textContent = latestStoryText || "正在生成...";
        updateMobileResult("快速讲述生成中...", latestStoryText);
        updateTtsButtonState();
        return;
      }
      if (event.type === "done") {
        finalResult = event;
        return;
      }
      if (event.type === "error") {
        throw new Error(event.message || "流式识别失败");
      }
    });

    if (!finalResult) throw new Error("流式识别未返回完整结果");
    renderScanResult({ ...finalResult, story_content: finalResult.story_content || streamedText }, { replaceLastPage });
    applyScanSuccessState(signature, replaceLastPage);
  }

  function resetLiveStoryBook() {
    if (pageStories.length && !window.confirm("确认清空当前连续故事书吗？")) return;
    pageStories = [];
    latestStoryText = "";
    latestStoryAudioKey = "";
    latestAnalysisResult = [];
    scanSessionId = globalThis.crypto?.randomUUID?.() || `scan-${Date.now()}`;
    stableFrameCount = 0;
    lastFrameSignature = "";
    lastScannedSignature = "";
    clearTtsAudio({ stopCurrent: true, clearQueue: true });
    if (storyOutput) storyOutput.textContent = "故事书已重置，请重新识别第一页。";
    if (totalStoryOutput) totalStoryOutput.textContent = "开启“连续识别”后，每识别一页都会累积到这里。";
    if (resultMeta) resultMeta.textContent = "故事书已重置。";
    if (analysisOutput) analysisOutput.textContent = "";
    if (qualityPanel) qualityPanel.classList.add("hidden");
    if (qualitySummary) qualitySummary.textContent = "";
    if (mobileStory) mobileStory.textContent = "";
    if (mobileMeta) mobileMeta.textContent = "故事书已重置";
    updateContextBadge({ recent_page_count: 0, character_registry: [] });
    updateStateBadges({
      pageState: "页面状态：等待识别",
      stabilityText: `稳定帧：0 / ${STABLE_FRAMES_REQUIRED}`,
      signatureText: "重复检测：未命中",
    });
    updateSaveStoryButtonState();
    updateTtsButtonState();
    setStatus("故事书已重置，请从第一页重新识别。");
    showToast("故事书已重置");
  }

  async function saveLiveStoryRecord() {
    const storyContent = getTotalStoryText().trim();
    if (!storyContent) {
      showToast("请先识别至少一页");
      return;
    }
    const oldLabel = saveLiveStoryBtn?.textContent || "保存故事记录";
    if (saveLiveStoryBtn) {
      saveLiveStoryBtn.disabled = true;
      saveLiveStoryBtn.textContent = "保存中...";
    }
    try {
      const imagePaths = pageStories.map((page) => page.image_path).filter(Boolean);
      const data = await apiRequest("/api/stories/scan/save", {
        method: "POST",
        body: JSON.stringify({
          story_content: storyContent,
          page_stories: pageStories,
          analysis_result: latestAnalysisResult,
          image_paths: imagePaths,
          prompt: promptInput.value.trim(),
          narration_style: styleSelect.value,
          audience_age: ageSelect.value,
          response_mode: modeSelect?.value || "fast",
          session_id: scanSessionId,
        }),
      });
      const storyId = data?.story?.id ? ` #${data.story.id}` : "";
      showToast(`故事已保存${storyId}`);
      setStatus("故事记录已保存，可在故事历史中查看。");
    } catch (error) {
      showToast(error.message || "保存失败");
    } finally {
      if (saveLiveStoryBtn) saveLiveStoryBtn.textContent = oldLabel;
      updateSaveStoryButtonState();
    }
  }

  function buildGuidePageBox() {
    return buildCameraGuidePageBox(video);
  }

  function applyBox(target, labelTarget, box, label, kind) {
    if (!target || !labelTarget) return;
    if (!box) {
      target.classList.add("hidden");
      target.style.removeProperty("left");
      target.style.removeProperty("top");
      target.style.removeProperty("width");
      target.style.removeProperty("height");
      labelTarget.textContent = label;
      if (kind) target.dataset.kind = kind;
      return;
    }

    target.classList.remove("hidden");
    target.style.left = `${box.x * 100}%`;
    target.style.top = `${box.y * 100}%`;
    target.style.width = `${box.width * 100}%`;
    target.style.height = `${box.height * 100}%`;
    target.dataset.kind = kind || "";
    labelTarget.textContent = label;
  }

  function setGuideBox(box, label = "请将绘本页放入引导框") {
    applyBox(guideBox, guideBoxLabel, box || currentGuideBox || buildGuidePageBox(), label, "guide");
  }

  function setDetectedBox(box, label = "后端识别框") {
    applyBox(detectedBox, detectedBoxLabel, box, label, "detected");
  }

  function renderScanResult(result, options = {}) {
    const { replaceLastPage = false } = options;
    const analysisResult = Array.isArray(result?.analysis_result) ? result.analysis_result : [];
    latestAnalysisResult = analysisResult;
    const first = analysisResult[0] || {};
    const quality = result?.quality || null;
    const timing = result?.timing || null;
    const cropMode = result?.crop_mode || "full_frame";
    const cropBox = result?.crop_box && typeof result.crop_box === "object" ? result.crop_box : null;

    updateContextBadge(result?.context || null);
    updateCropBadge(cropMode);

    setGuideBox(currentGuideBox, "引导框");
    if (cropMode === "model_crop" && cropBox) {
      currentDetectedBox = cropBox;
      setDetectedBox(currentDetectedBox, "后端检测到页面");
    } else if (cropMode === "frontend_crop" && cropBox) {
      currentDetectedBox = cropBox;
      setDetectedBox(currentDetectedBox, "前端检测到页面");
    } else if (cropMode === "guide_crop" || cropMode === "full_frame") {
      setDetectedBox(currentDetectedBox, currentDetectedBox ? "沿用上次识别框" : "后端识别框");
    }

    const currentStoryText = String(result?.story_content || "");
    const shouldQueueNewStory = continuousReadingEnabled && (isAudioPlaying() || ttsQueue.length > 0);
    if (!shouldQueueNewStory) {
      clearTtsAudio({ stopCurrent: false });
    }
    const totalStoryText = updateStoryOutputs(currentStoryText, result, replaceLastPage);
    updateTtsButtonState();
    if (first?.is_picturebook_page === false) {
      resultMeta.textContent = "未检测到绘本页：请把书页放进引导框";
    } else {
      resultMeta.textContent = `识别完成：角色 ${Array.isArray(first["角色"]) ? first["角色"].join("、") || "未识别" : "未识别"} | 场景 ${first["场景"] || "未识别"}`;
    }

    updateMobileResult(
      continuousScanEnabled ? `当前页已更新｜总计 ${pageStories.length} 页` : "识别结果已更新",
      continuousScanEnabled ? totalStoryText || latestStoryText : latestStoryText,
    );
    if (shouldQueueNewStory && latestStoryText) {
      queueStoryForContinuousReading(latestStoryText);
      setStatus("识别完成，新讲述已准备排队朗读，不会打断当前语音。");
    }

    if (quality) {
      qualityPanel.classList.remove("hidden");
      const paper = quality.paper_metrics || {};
      const modeText =
        result?.response_mode === "full"
          ? "完整生成"
          : result?.response_mode === "direct"
            ? "直接讲述"
            : "快速响应";
      const cropText =
        cropMode === "model_crop"
          ? "后端检测页框"
          : cropMode === "guide_crop"
            ? "引导框裁剪"
            : cropMode === "frontend_crop"
              ? "前端框裁剪"
              : "整图回退";
      qualitySummary.textContent =
        `${modeText} | ${cropText} | 总耗时 ${timing?.total_ms ?? "-"}ms | 识别 ${timing?.analysis_ms ?? "-"}ms | 讲述 ${timing?.story_ms ?? "-"}ms | 评估 ${timing?.quality_ms ?? "-"}ms | 整体 ${paper.overall ?? "-"} | 连贯 ${paper.coherence ?? "-"} | 适龄 ${paper.age_appropriateness ?? "-"} | 页面覆盖率 ${paper.page_coverage_ratio ?? "-"}`;
      analysisOutput.textContent = JSON.stringify(analysisResult, null, 2);
      if (timing) {
        analysisOutput.textContent = `${JSON.stringify({ timing }, null, 2)}\n\n${JSON.stringify(analysisResult, null, 2)}`;
      }
    } else {
      qualityPanel.classList.add("hidden");
      qualitySummary.textContent = "";
      analysisOutput.textContent = "";
    }
  }

  async function playStoryTTS(options = {}) {
    const { forceRegenerate = false, autoplay = true } = options;
    const text = getReadableStoryText();
    if (!text) {
      showToast(activeCameraTab === "total" ? "请先累积总故事文本" : "请先完成一次识别");
      return;
    }
    if (!ttsPlayBtn) return;
    const storyKey = makeStoryAudioKey(text);
    if (!forceRegenerate && ttsAudio?.src && latestStoryAudioKey === storyKey) {
      try {
        ttsAudio.classList.remove("hidden");
        if (autoplay) await ttsAudio.play();
        return;
      } catch (error) {
        showToast(error.message || "播放失败");
        return;
      }
    }
    const oldLabel = ttsPlayBtn.textContent;
    ttsPlayBtn.disabled = true;
    ttsPlayBtn.textContent = "生成语音中...";
    if (mobileTtsBtn) mobileTtsBtn.disabled = true;
    try {
      continuousReadingEnabled = true;
      const data = await synthesizeStoryAudio(text);
      const audioUrl = data?.audio_url;
      if (!audioUrl) throw new Error("未返回音频地址");
      if (!ttsAudio) return;
      if (autoplay) {
        await playAudioUrl(audioUrl, storyKey);
      } else {
        latestStoryAudioKey = storyKey;
        setTtsAudioSource(audioUrl, storyKey);
      }
      const timingText = data?.timing?.total_ms ? `，耗时 ${data.timing.total_ms}ms` : "";
      const segmentText = Number(data?.segment_count || 1) > 1 ? `，已分 ${data.segment_count} 段合成` : "";
      showToast(`开始朗读${timingText}${segmentText}`);
    } catch (error) {
      showToast(error.message || "朗读失败");
    } finally {
      ttsPlayBtn.textContent = oldLabel || "朗读当前讲述";
      updateTtsButtonState();
    }
  }

  async function startCamera() {
    if (stream) return;
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        video: {
          facingMode: { ideal: "environment" },
          width: { ideal: 1280 },
          height: { ideal: 720 },
        },
        audio: false,
      });
      video.srcObject = stream;
      syncEmptyHintVisibility();
      captureBtn.disabled = false;
      if (toggleAutoScanBtn) toggleAutoScanBtn.disabled = false;
      if (rescanBtn) rescanBtn.disabled = false;
      currentGuideBox = buildGuidePageBox();
      setGuideBox(currentGuideBox);
      setDetectedBox(currentDetectedBox, currentDetectedBox ? "沿用上次识别框" : "后端识别框");
      setStatus("摄像头已启动，请尽量让绘本页贴近引导框。");
      updateStateBadges({
        pageState: "页面状态：引导框模式",
        stabilityText: `稳定帧：${stableFrameCount} / ${STABLE_FRAMES_REQUIRED}`,
        signatureText: "重复检测：未命中",
      });
      updateCropBadge("guide_crop");
    } catch (error) {
      showToast("摄像头启动失败，请检查浏览器权限");
      const embedded = detectEmbeddedBrowser();
      const browserHint =
        embedded === "wechat"
          ? "，当前为微信内置浏览器，建议改用系统浏览器打开"
          : embedded === "qq"
            ? "，当前为 QQ 内置浏览器，建议改用系统浏览器打开"
            : "";
      setStatus(`摄像头启动失败：${error.message || "未知错误"}${browserHint}`);
    }
  }

  function captureFrameBlob() {
    return new Promise((resolve, reject) => {
      const width = video.videoWidth;
      const height = video.videoHeight;
      if (!width || !height) {
        reject(new Error("摄像头画面尚未就绪"));
        return;
      }

      const fastMode = (modeSelect?.value || "fast") === "fast";
      const maxWidth = fastMode ? 640 : 960;
      const scale = Math.min(1, maxWidth / width);
      canvas.width = Math.round(width * scale);
      canvas.height = Math.round(height * scale);

      const ctx = canvas.getContext("2d");
      ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
      canvas.toBlob(
        (blob) => {
          if (!blob) {
            reject(new Error("图像压缩失败"));
            return;
          }
          resolve(blob);
        },
        "image/jpeg",
        fastMode ? 0.66 : 0.78,
      );
    });
  }

  function captureFrameSignature() {
    const width = video.videoWidth;
    const height = video.videoHeight;
    if (!width || !height) return "";

    const sampleSize = 12;
    canvas.width = sampleSize;
    canvas.height = sampleSize;
    const ctx = canvas.getContext("2d", { willReadFrequently: true });
    ctx.drawImage(video, 0, 0, sampleSize, sampleSize);
    const { data } = ctx.getImageData(0, 0, sampleSize, sampleSize);

    const values = [];
    for (let i = 0; i < data.length; i += 4) {
      const gray = Math.round((data[i] + data[i + 1] + data[i + 2]) / 3);
      values.push(gray);
    }
    const avg = values.reduce((sum, value) => sum + value, 0) / values.length;
    return values.map((value) => (value >= avg ? "1" : "0")).join("");
  }

  function signatureDiff(a, b) {
    if (!a || !b || a.length !== b.length) return Number.MAX_SAFE_INTEGER;
    let diff = 0;
    for (let i = 0; i < a.length; i += 1) {
      if (a[i] !== b[i]) diff += 1;
    }
    return diff;
  }

  function updateFrameStability(signature) {
    if (!signature) return false;

    if (!lastFrameSignature) {
      lastFrameSignature = signature;
      stableFrameCount = 1;
      updateStateBadges({
        pageState: "页面状态：引导框模式",
        stabilityText: `稳定帧：${stableFrameCount} / ${STABLE_FRAMES_REQUIRED}`,
        signatureText: "重复检测：未命中",
      });
      return false;
    }

    const diff = signatureDiff(signature, lastFrameSignature);
    if (diff <= SIGNATURE_DIFF_THRESHOLD) {
      stableFrameCount += 1;
    } else {
      stableFrameCount = 1;
      lastFrameSignature = signature;
    }

    updateStateBadges({
      pageState: "页面状态：引导框稳定检测",
      stabilityText: `稳定帧：${stableFrameCount} / ${STABLE_FRAMES_REQUIRED}`,
      signatureText: `重复检测：签名差异 ${diff}`,
    });
    return stableFrameCount >= STABLE_FRAMES_REQUIRED;
  }

  async function scanCurrentFrame(options = {}) {
    const { force = false, clearBeforeScan = false, replaceLastPage = false } = options;
    const now = Date.now();
    if (isScanning) return;
    if (!force && now - lastCaptureAt < 1200) {
      showToast("识别过于频繁，请稍后再试");
      return;
    }
    if (!stream) {
      showToast("请先启动摄像头");
      return;
    }

    currentGuideBox = currentGuideBox || buildGuidePageBox();
    setGuideBox(currentGuideBox);
    if (clearBeforeScan) {
      clearRecognitionResult("正在重新识别当前页...", { clearQueue: false, clearTotal: false });
      lastScannedSignature = "";
    }

    const signature = captureFrameSignature();
    updateFrameStability(signature);

    isScanning = true;
    updateSaveStoryButtonState();
    lastCaptureAt = now;
    captureBtn.disabled = true;
    if (rescanBtn) rescanBtn.disabled = true;
    captureBtn.textContent = replaceLastPage ? "重新识别中..." : "识别中...";
    setStatus(replaceLastPage ? "正在刷新当前页讲述..." : "正在压缩并上传当前画面...");

    try {
      const blob = await captureFrameBlob();
      const formData = new FormData();
      formData.append("image", blob, "camera-frame.jpg");
      if (continuousScanEnabled || replaceLastPage) {
        formData.append("session_id", scanSessionId);
      }
      formData.append("prompt", promptInput.value.trim());
      formData.append("narration_style", styleSelect.value);
      formData.append("audience_age", ageSelect.value);
      formData.append("response_mode", modeSelect?.value || "fast");
      formData.append("replace_last_page", replaceLastPage ? "true" : "false");
      formData.append("crop_source", "guide");
      formData.append("crop_x", String(currentGuideBox.x));
      formData.append("crop_y", String(currentGuideBox.y));
      formData.append("crop_width", String(currentGuideBox.width));
      formData.append("crop_height", String(currentGuideBox.height));

      if (["fast", "direct"].includes(modeSelect?.value || "fast")) {
        await scanCurrentFrameStream(formData, signature, replaceLastPage);
        return;
      }

      const result = await apiRequest("/api/stories/scan", {
        method: "POST",
        body: formData,
      });

      renderScanResult(result, { replaceLastPage });
      applyScanSuccessState(signature, replaceLastPage);
    } catch (error) {
      showToast(error.message || "识别失败");
      setStatus(`识别失败：${error.message || "未知错误"}`);
    } finally {
      isScanning = false;
      captureBtn.disabled = !stream;
      if (rescanBtn) rescanBtn.disabled = !stream;
      captureBtn.textContent = "识别当前页";
      updateSaveStoryButtonState();
    }
  }

  startBtn?.addEventListener("click", startCamera);
  captureBtn?.addEventListener("click", () => scanCurrentFrame());
  toggleAutoScanBtn?.addEventListener("click", () => setContinuousScanEnabled(!continuousScanEnabled));
  rescanBtn?.addEventListener("click", () =>
    scanCurrentFrame({ force: true, clearBeforeScan: true, replaceLastPage: true }),
  );
  ttsPlayBtn?.addEventListener("click", playStoryTTS);
  resetLiveStoryBtn?.addEventListener("click", resetLiveStoryBook);
  saveLiveStoryBtn?.addEventListener("click", saveLiveStoryRecord);
  cameraTabs.forEach((tab) => {
    tab.addEventListener("click", () => switchCameraTab(tab.dataset.cameraTab || "story"));
  });

  mobileToggleBtn?.addEventListener("click", toggleMobileResult);
  mobileOpenDetailBtn?.addEventListener("click", () => {
    toggleMobileDetailPanel();
  });
  mobileTtsBtn?.addEventListener("click", playStoryTTS);
  ttsAudio?.addEventListener("ended", () => {
    playNextQueuedAudio();
  });

  video?.addEventListener("loadedmetadata", syncEmptyHintVisibility);
  video?.addEventListener("playing", syncEmptyHintVisibility);
  video?.addEventListener("pause", syncEmptyHintVisibility);
  video?.addEventListener("emptied", () => {
    if (emptyHint) emptyHint.classList.remove("hidden");
    cameraStage?.classList.remove("is-live");
  });

  window.addEventListener("beforeunload", () => {
    if (stream) stream.getTracks().forEach((track) => track.stop());
  });

  await ensureAuth();
  updateContinuousScanButton();
  updateSaveStoryButtonState();
  syncEmptyHintVisibility();
});
