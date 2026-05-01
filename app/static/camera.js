window.addEventListener("DOMContentLoaded", async () => {
  if (!initTopbar("camera")) return;

  const startBtn = document.getElementById("start-camera");
  const captureBtn = document.getElementById("capture-frame");
  const toggleAutoScanBtn = document.getElementById("toggle-auto-scan");
  const rescanBtn = document.getElementById("rescan-frame");
  const ttsPlayBtn = document.getElementById("camera-tts-play");
  const ttsAudio = document.getElementById("camera-tts-audio");
  const video = document.getElementById("camera-video");
  const canvas = document.getElementById("camera-canvas");
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
  const intervalSelect = document.getElementById("camera-interval");
  const promptInput = document.getElementById("camera-prompt");
  const pageStateNode = document.getElementById("camera-page-state");
  const stabilityStateNode = document.getElementById("camera-stability-state");
  const signatureStateNode = document.getElementById("camera-signature-state");
  const contextStateNode = document.getElementById("camera-context-state");
  const cropStateNode = document.getElementById("camera-crop-state");
  const resultMeta = document.getElementById("camera-result-meta");
  const storyOutput = document.getElementById("camera-story-output");
  const qualityPanel = document.getElementById("camera-quality-panel");
  const qualitySummary = document.getElementById("camera-quality-summary");
  const analysisOutput = document.getElementById("camera-analysis-output");
  const cameraTabs = Array.from(document.querySelectorAll("[data-camera-tab]"));
  const storyPanel = document.getElementById("camera-story-panel");
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
  let autoScanTimer = null;
  let lastFrameSignature = "";
  let lastScannedSignature = "";
  let stableFrameCount = 0;
  let scanSessionId = globalThis.crypto?.randomUUID?.() || `scan-${Date.now()}`;
  let currentGuideBox = null;
  let currentDetectedBox = null;
  let latestStoryText = "";
  let latestStoryAudioKey = "";
  let autoScanEnabled = false;
  let continuousReadingEnabled = false;
  let ttsQueue = [];
  let isPreparingQueuedTTS = false;

  const STABLE_FRAMES_REQUIRED = 2;
  const SIGNATURE_DIFF_THRESHOLD = 18;

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
    if (ttsPlayBtn) {
      ttsPlayBtn.disabled = !latestStoryText || isPreparingQueuedTTS;
      ttsPlayBtn.textContent = isPreparingQueuedTTS
        ? "生成语音中..."
        : ttsQueue.length
          ? `朗读当前讲述（队列 ${ttsQueue.length}）`
          : "朗读当前讲述";
    }
    if (mobileTtsBtn) {
      mobileTtsBtn.disabled = !latestStoryText || isPreparingQueuedTTS;
      mobileTtsBtn.textContent = ttsQueue.length ? `朗读队列(${ttsQueue.length})` : "朗读";
    }
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
    const { clearQueue = false } = options;
    latestStoryText = "";
    clearTtsAudio({ stopCurrent: false, clearQueue });
    if (storyOutput) storyOutput.textContent = "正在等待新的识别结果...";
    if (resultMeta) resultMeta.textContent = "已清空上次识别结果。";
    if (qualityPanel) qualityPanel.classList.add("hidden");
    if (qualitySummary) qualitySummary.textContent = "";
    if (analysisOutput) analysisOutput.textContent = "";
    if (mobileStory) mobileStory.textContent = "";
    if (mobileMeta) mobileMeta.textContent = "等待新的识别结果";
    setStatus(message);
  }

  function updateAutoScanButton() {
    if (!toggleAutoScanBtn) return;
    toggleAutoScanBtn.textContent = autoScanEnabled ? "自动识别：开" : "自动识别：关";
    toggleAutoScanBtn.setAttribute("aria-pressed", autoScanEnabled ? "true" : "false");
    toggleAutoScanBtn.classList.toggle("is-active", autoScanEnabled);
  }

  function setAutoScanEnabled(enabled) {
    autoScanEnabled = Boolean(enabled);
    updateAutoScanButton();
    if (autoScanEnabled) {
      restartAutoScanIfNeeded();
      setStatus("自动识别已开启：画面稳定后会自动上传当前页。");
      showToast("自动识别已开启");
    } else {
      stopAutoScan();
      setStatus("自动识别已关闭，你可以手动识别当前页。");
      showToast("自动识别已关闭");
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
    cameraTabs.forEach((tab) => {
      tab.classList.toggle("active", tab.dataset.cameraTab === tabName);
    });
    storyPanel?.classList.toggle("active", tabName === "story");
    debugPanel?.classList.toggle("active", tabName === "debug");
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

  function buildGuidePageBox() {
    const videoAspect = (video.videoWidth || 3) / Math.max(1, video.videoHeight || 4);
    const marginX = 0.03;
    const marginY = 0.04;
    let guideWidth = 1 - marginX * 2;
    let guideHeight = 1 - marginY * 2;

    const aspect = guideWidth / Math.max(0.0001, guideHeight);
    if (aspect < 0.55) guideWidth = Math.min(0.96, guideHeight * 0.65);
    if (aspect > 1.15) guideHeight = Math.min(0.96, guideWidth / 1.05);
    if (videoAspect < 0.7) guideWidth = Math.min(guideWidth, 0.9);

    return {
      x: (1 - guideWidth) / 2,
      y: (1 - guideHeight) / 2,
      width: guideWidth,
      height: guideHeight,
      source: "guide",
    };
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

  function renderScanResult(result) {
    const analysisResult = Array.isArray(result?.analysis_result) ? result.analysis_result : [];
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

    latestStoryText = String(result?.story_content || "");
    const shouldQueueNewStory = continuousReadingEnabled && (isAudioPlaying() || ttsQueue.length > 0);
    if (!shouldQueueNewStory) {
      clearTtsAudio({ stopCurrent: false });
    }
    storyOutput.textContent = latestStoryText || "未返回讲述文本";
    updateTtsButtonState();
    resultMeta.textContent = `识别完成：角色 ${Array.isArray(first["角色"]) ? first["角色"].join("、") || "未识别" : "未识别"} | 场景 ${first["场景"] || "未识别"}`;

    updateMobileResult("识别结果已更新", latestStoryText);
    if (shouldQueueNewStory && latestStoryText) {
      queueStoryForContinuousReading(latestStoryText);
      setStatus("识别完成，新讲述已准备排队朗读，不会打断当前语音。");
    }

    if (quality) {
      qualityPanel.classList.remove("hidden");
      const paper = quality.paper_metrics || {};
      const modeText = result?.response_mode === "full" ? "完整生成" : "快速响应";
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
    const text = String(latestStoryText || "").trim();
    if (!text) {
      showToast("请先完成一次识别");
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
      restartAutoScanIfNeeded();
    } catch (error) {
      showToast("摄像头启动失败，请检查浏览器权限");
      setStatus(`摄像头启动失败：${error.message || "未知错误"}`);
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

      const maxWidth = 960;
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
        0.78,
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

  function stopAutoScan() {
    if (autoScanTimer) {
      clearInterval(autoScanTimer);
      autoScanTimer = null;
    }
  }

  function restartAutoScanIfNeeded() {
    stopAutoScan();
    if (!stream || !autoScanEnabled) return;
    const intervalMs = Number(intervalSelect?.value || 2000);
    autoScanTimer = setInterval(() => {
      scanCurrentFrame({ automatic: true }).catch(() => {});
    }, intervalMs);
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
    const { automatic = false, force = false, clearBeforeScan = false } = options;
    const now = Date.now();
    if (isScanning) return;
    if (!force && now - lastCaptureAt < 1200) {
      if (!automatic) showToast("识别过于频繁，请稍后再试");
      return;
    }
    if (!stream) {
      if (!automatic) showToast("请先启动摄像头");
      return;
    }

    currentGuideBox = currentGuideBox || buildGuidePageBox();
    setGuideBox(currentGuideBox);
    if (clearBeforeScan) {
      clearRecognitionResult("正在重新识别当前页...", { clearQueue: false });
      lastScannedSignature = "";
    }

    const signature = captureFrameSignature();
    const isStable = updateFrameStability(signature);
    if (automatic && !force && !isStable) {
      setStatus("自动扫描中：等待画面稳定...");
      return;
    }

    const scannedDiff = signatureDiff(signature, lastScannedSignature);
    if (automatic && !force && scannedDiff <= SIGNATURE_DIFF_THRESHOLD) {
      updateStateBadges({
        pageState: "页面状态：与上个结果接近",
        stabilityText: `稳定帧：${stableFrameCount} / ${STABLE_FRAMES_REQUIRED}`,
        signatureText: `重复检测：命中缓存阈值 ${scannedDiff}`,
      });
      setStatus("自动扫描中：当前页与上一结果接近，已跳过重复请求。");
      return;
    }

    isScanning = true;
    lastCaptureAt = now;
    captureBtn.disabled = true;
    if (rescanBtn) rescanBtn.disabled = true;
    captureBtn.textContent = automatic ? "自动识别中..." : "识别中...";
    setStatus(automatic ? "自动扫描命中稳定帧，正在上传..." : "正在压缩并上传当前画面...");

    try {
      const blob = await captureFrameBlob();
      const formData = new FormData();
      formData.append("image", blob, "camera-frame.jpg");
      formData.append("session_id", scanSessionId);
      formData.append("prompt", promptInput.value.trim());
      formData.append("narration_style", styleSelect.value);
      formData.append("audience_age", ageSelect.value);
      formData.append("response_mode", modeSelect?.value || "fast");
      formData.append("crop_source", "guide");
      formData.append("crop_x", String(currentGuideBox.x));
      formData.append("crop_y", String(currentGuideBox.y));
      formData.append("crop_width", String(currentGuideBox.width));
      formData.append("crop_height", String(currentGuideBox.height));

      const result = await apiRequest("/api/stories/scan", {
        method: "POST",
        body: formData,
      });

      lastScannedSignature = signature;
      stableFrameCount = 0;
      lastFrameSignature = signature;
      renderScanResult(result);
      updateStateBadges({
        pageState: automatic ? "页面状态：自动识别完成" : "页面状态：手动识别完成",
        stabilityText: `稳定帧：0 / ${STABLE_FRAMES_REQUIRED}`,
        signatureText: "重复检测：已记录当前页",
      });
      setStatus(automatic ? "自动识别完成，继续监测翻页。" : "识别完成。你可以翻页后继续扫描。");
      if (!automatic) showToast("实时识别完成");
    } catch (error) {
      showToast(error.message || "识别失败");
      setStatus(`识别失败：${error.message || "未知错误"}`);
    } finally {
      isScanning = false;
      captureBtn.disabled = !stream;
      if (rescanBtn) rescanBtn.disabled = !stream;
      captureBtn.textContent = "识别当前页";
    }
  }

  startBtn?.addEventListener("click", startCamera);
  captureBtn?.addEventListener("click", () => scanCurrentFrame({ automatic: false }));
  toggleAutoScanBtn?.addEventListener("click", () => setAutoScanEnabled(!autoScanEnabled));
  rescanBtn?.addEventListener("click", () =>
    scanCurrentFrame({ automatic: false, force: true, clearBeforeScan: true }),
  );
  ttsPlayBtn?.addEventListener("click", playStoryTTS);
  intervalSelect?.addEventListener("change", restartAutoScanIfNeeded);
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
    stopAutoScan();
    if (stream) stream.getTracks().forEach((track) => track.stop());
  });

  await ensureAuth();
  updateAutoScanButton();
  syncEmptyHintVisibility();
});
