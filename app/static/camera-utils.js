function syncCameraMobileNavigation() {
  const isMobile = window.matchMedia?.("(max-width: 900px)")?.matches;
  const workspaceNav = document.querySelector(".workspace-nav");
  const returnNav = document.querySelector(".mobile-return-nav");
  if (workspaceNav) workspaceNav.hidden = Boolean(isMobile);
  if (returnNav) returnNav.hidden = !isMobile;
}

function parseCameraSseEvents(buffer, onEvent) {
  const parts = buffer.split("\n\n");
  const rest = parts.pop() || "";
  parts.forEach((part) => {
    const dataLine = part
      .split("\n")
      .map((line) => line.trim())
      .find((line) => line.startsWith("data:"));
    if (!dataLine) return;
    const raw = dataLine.slice(5).trim();
    if (!raw) return;
    onEvent(JSON.parse(raw));
  });
  return rest;
}

async function apiRequestCameraStream(url, formData, onEvent) {
  const token = getToken();
  const headers = {};
  if (token) headers.Authorization = `Bearer ${token}`;
  const response = await fetch(url, {
    method: "POST",
    headers,
    body: formData,
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error(parseErrorMessage(payload));
  }
  if (!response.body) throw new Error("浏览器不支持流式响应");

  const reader = response.body.getReader();
  const decoder = new TextDecoder("utf-8");
  let buffer = "";
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    buffer = parseCameraSseEvents(buffer, onEvent);
  }
  buffer += decoder.decode();
  if (buffer.trim()) parseCameraSseEvents(`${buffer}\n\n`, onEvent);
}

function buildCameraGuidePageBox(video) {
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

window.syncCameraMobileNavigation = syncCameraMobileNavigation;
window.parseCameraSseEvents = parseCameraSseEvents;
window.apiRequestCameraStream = apiRequestCameraStream;
window.buildCameraGuidePageBox = buildCameraGuidePageBox;
