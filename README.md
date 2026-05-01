# 面向移动端连续翻页场景的端云协同绘本视觉理解与低时延智能讲述系统

这是一个面向真实亲子共读场景的 AI 绘本实时识别与智能讲述系统。系统不再只是“上传图片后生成故事”，而是通过手机浏览器直接调用摄像头，持续观察绘本页面，在页面稳定后自动识别当前页，并结合前序页面上下文生成适龄、连贯、可朗读的讲述文本。

项目适合作为毕业设计展示：可以现场用手机对准实体绘本，完成“翻页即识别、识别后讲述、讲述可朗读、时延可统计”的完整闭环。

---

## 核心能力

- 移动端摄像头实时取景：手机浏览器访问 `/ui/camera` 即可调用摄像头。
- 页面稳定检测：只有画面签名和引导框稳定后才触发自动扫描，减少翻页中间态误识别。
- 页框裁剪与图像增强：前端引导框 + 后端 OpenCV 页框检测 + 裁剪增强，降低背景干扰。
- OCR/VLM 页面理解：提取角色、场景、动作、情绪、关键物体、画面文字等结构化信息。
- 连续翻页上下文：通过 `session_id` 维护最近页面摘要和角色表，支持跨页连贯讲述。
- 快速响应与完整生成：快速模式低时延返回页级讲述，完整模式调用故事生成模型生成更丰富文本。
- Edge TTS 朗读：识别结果可一键生成 mp3 并在浏览器播放。
- 手机端适配：摄像头优先显示，识别结果以底部故事抽屉呈现，方便边拍边看/听。
- 时延统计：接口返回并记录识别、讲述、评估、裁剪、TTS 等阶段耗时，便于论文汇报。
- 用户与绘本管理：支持注册登录、绘本管理、图片上传、故事生成、历史记录和质量评估。

---

## 技术栈

- 后端：Python 3.11、FastAPI、Uvicorn、Pydantic、SQLAlchemy Async
- 数据库：SQLite / MySQL 8.0
- 缓存：Redis，用于缓存、任务进度、限流与扫描会话
- 图像处理：Pillow、OpenCV Headless
- 多模态理解：Qwen VL 兼容接口，支持 mock 模式
- 语音合成：Edge TTS，Piper 作为离线备用方案
- 前端：原生 HTML/CSS/JavaScript，适配桌面与手机浏览器
- 部署：Docker、Docker Compose v2

---

## 系统流程

```text
手机浏览器摄像头
  -> 前端取景与稳定检测
  -> 上传关键帧和引导框坐标
  -> 后端 OpenCV 页框检测
  -> 裁剪 / 增强 / 整图兜底
  -> 多模态页面理解
  -> 页级摘要与会话记忆
  -> 快速讲述或完整生成
  -> 前端展示 / Edge TTS 朗读
  -> 日志记录阶段耗时
```

当前裁剪优先级：

```text
后端 OpenCV 检测页框 > 前端引导框 > 整图识别兜底
```

---

## 响应模式

### 快速响应

快速响应是实时识别的默认模式。它只调用一次视觉理解模型，得到页面结构化信息后，由后端本地规则快速生成短讲述。

特点：

- 延迟低，适合手机连续翻页。
- 讲述稳定，不额外调用故事生成大模型。
- 文本更像“当前页讲述提示”，不会过度扩写。

核心路径：

```text
analyze_images
  -> summarize_page_for_live_story
  -> build_contextual_live_scan_story
```

### 完整生成

完整生成会在页面理解后，再调用故事生成模型生成更完整的讲述文本。

特点：

- 文本更丰富，更像完整故事段落。
- 延迟更高，适合单页展示或最终生成。
- 可结合最近页面上下文进行连续表达。

---

## 项目结构

```text
app/
  core/        配置、日志、Redis、请求上下文
  db/          数据库会话与初始化
  models/      ORM 模型
  routers/     API 路由
  schemas/     请求与响应模型
  services/    AI 分析、故事生成、实时讲述、TTS、评估等服务
  static/      前端页面、样式和脚本
  main.py      FastAPI 应用入口

scripts/
  download_piper_model.py
  export_story_quality_report.py

uploads/       上传图片与运行时音频输出
logs/          应用日志
models/piper/  Piper 离线模型目录，不提交 Git
```

---

## 本地运行

### 1. 创建环境并安装依赖

```powershell
pip install -r requirements.txt
```

如果使用 Edge TTS，确保依赖已安装：

```powershell
pip install edge-tts
```

### 2. 准备环境变量

```powershell
copy .env.example .env
```

最小本地配置可以使用 SQLite 和 mock 模式：

```env
DATABASE_URL=sqlite+aiosqlite:///./ai_story.db
AI_PROVIDER=mock
REDIS_ENABLED=false
TTS_PROVIDER=edge
EDGE_TTS_VOICE=zh-CN-XiaoxiaoNeural
EDGE_TTS_RATE=-5%
EDGE_TTS_VOLUME=+0%
```

使用 Qwen 视觉模型时配置：

```env
AI_PROVIDER=qwen
QWEN_MODEL=qwen3.6-flash
QWEN_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
QWEN_API_KEY=你的API_KEY
```

### 3. 启动服务

```powershell
uvicorn app.main:app --reload --port 8001
```

访问：

- 登录页：`http://127.0.0.1:8001/ui/login`
- 实时识别：`http://127.0.0.1:8001/ui/camera`
- 接口文档：`http://127.0.0.1:8001/docs`
- 健康检查：`http://127.0.0.1:8001/health`

---

## Docker 部署

项目提供 `Dockerfile` 和 `docker-compose.yml`，默认包含：

- `app`：FastAPI 应用
- `db`：MySQL 8.0
- `redis`：Redis 7

### 首次部署

```bash
cd ~/ai-picturebook-backend-handwrite
cp .env.example .env
```

生产环境建议配置：

```env
APP_ENV=production
APP_DEBUG=false
APP_PORT=8001
SECRET_KEY=换成足够长的随机字符串

AI_PROVIDER=qwen
QWEN_MODEL=qwen3.6-flash
QWEN_API_KEY=你的API_KEY

TTS_PROVIDER=edge
TTS_MAX_CHARS=220
EDGE_TTS_VOICE=zh-CN-XiaoxiaoNeural
EDGE_TTS_RATE=-5%
EDGE_TTS_VOLUME=+0%

MYSQL_ROOT_PASSWORD=换成数据库密码
MYSQL_DATABASE=ai_story
```

启动：

```bash
docker compose up -d --build
docker ps
docker logs -f ai-picturebook-app
```

### 更新部署

```bash
cd ~/ai-picturebook-backend-handwrite
git pull

rm -rf uploads/tts/*
mkdir -p uploads/tts

docker rm -f ai-picturebook-app 2>/dev/null || true
docker rm -f $(docker ps -aq --filter "name=ai-picturebook-app") 2>/dev/null || true

docker compose build app
docker compose up -d app
docker logs -f ai-picturebook-app
```

如果服务器缺少 Compose v2：

```bash
apt update
apt install -y docker-compose-plugin
docker compose version
```

如果 `git pull` 走了失效代理：

```bash
git config --global --unset http.proxy || true
git config --global --unset https.proxy || true
unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY
git pull
```

---

## Edge TTS 与 Piper

默认推荐 Edge TTS：

```env
TTS_PROVIDER=edge
TTS_MAX_CHARS=220
EDGE_TTS_VOICE=zh-CN-XiaoxiaoNeural
EDGE_TTS_RATE=-5%
EDGE_TTS_VOLUME=+0%
```

接口：

```http
POST /api/stories/tts
```

请求示例：

```json
{
  "text": "故事从安静的小房间里慢慢开始。小主角好像发现了新的线索。",
  "voice_preset": null
}
```

返回 `data.audio_url`，前端直接用 `<audio>` 播放。

Piper 可以作为离线备用：

```env
TTS_PROVIDER=piper
PIPER_BINARY=piper
PIPER_MODEL_PATH=models/piper/zh_CN-huayan-medium.onnx
PIPER_CONFIG_PATH=models/piper/zh_CN-huayan-medium.onnx.json
```

下载 Piper 中文模型：

```bash
python scripts/download_piper_model.py --voice zh_CN-huayan-medium
```

注意：`models/piper/` 和 `uploads/tts/` 不提交 Git。

---

## 时延统计

系统会在 `/api/stories/scan` 返回 `timing` 字段，并写入日志。

示例：

```json
{
  "timing": {
    "cache_hit": false,
    "response_mode": "fast",
    "crop_mode": "guide_crop",
    "read_ms": 1,
    "page_detect_ms": 38,
    "crop_ms": 4,
    "enhance_ms": 12,
    "analysis_ms": 3200,
    "story_ms": 0,
    "quality_ms": 1,
    "total_ms": 3260
  }
}
```

日志筛选：

```bash
grep -E "scan.timing|tts.timing" logs/app.log
```

Windows PowerShell：

```powershell
Select-String -Path logs/app.log -Pattern "scan.timing|tts.timing"
```

答辩或论文中可以统计：

- `total_ms`：端到端扫描耗时
- `analysis_ms`：视觉模型识别耗时
- `story_ms`：讲述生成耗时
- `page_detect_ms`：页框检测耗时
- `crop_ms`：裁剪耗时
- `enhance_ms`：图像增强耗时
- `quality_ms`：质量评估耗时
- `tts.timing total_ms`：语音生成耗时

---

## 主要接口

用户：

- `POST /api/users/register`
- `POST /api/users/login`
- `GET /api/users/me`

绘本：

- `POST /api/books`
- `GET /api/books`
- `GET /api/books/{book_id}`
- `DELETE /api/books/{book_id}`

图片：

- `POST /api/books/{book_id}/images/upload`
- `GET /api/books/{book_id}/images`

故事与实时识别：

- `POST /api/stories/generate`
- `POST /api/stories/generate/submit`
- `GET /api/stories/tasks/{task_id}`
- `POST /api/stories/scan`
- `POST /api/stories/tts`
- `POST /api/stories/evaluate`
- `GET /api/stories/{story_id}/quality`
- `GET /api/stories`
- `GET /api/stories/{story_id}`
- `DELETE /api/stories/{story_id}`

健康检查：

- `GET /health`
- `GET /health/ready`

---

## 测试与检查

```bash
pytest -q
```

编译检查：

```bash
python -m py_compile app/routers/stories.py app/services/live_story_service.py app/services/tts_service.py
```

前端脚本检查：

```bash
node --check app/static/camera.js
```

---

## 常见问题

### 手机摄像头无法启动

- 优先使用 HTTPS 域名访问。
- 检查浏览器摄像头权限。
- 清理站点权限和缓存后重试。
- 微信/部分内置浏览器权限可能不稳定，建议使用手机系统浏览器。

### Docker 报 `KeyError: 'ContainerConfig'`

这是旧版 `docker-compose` v1 常见问题。推荐使用 Compose v2：

```bash
apt install -y docker-compose-plugin
docker compose version
```

临时处理：

```bash
docker rm -f ai-picturebook-app 2>/dev/null || true
docker compose up -d --build app
```

### Git 不小心提交了语音文件

项目已忽略 `uploads/tts/`。如果历史中已被跟踪，可以执行：

```bash
git rm --cached -r uploads/tts
git add .gitignore
git commit -m "chore: ignore generated tts audio files"
```

云端清理：

```bash
rm -rf uploads/tts/*
mkdir -p uploads/tts
```

---

## 论文与答辩表述

可以这样介绍本项目：

```text
本课题研究的不是传统的上传图片后生成故事，而是一个面向手机浏览器连续翻页场景的实时绘本视觉理解与低时延智能讲述系统。系统通过摄像头采集、页面稳定检测、页框裁剪、图文联合理解、上下文记忆、快速讲述生成和语音朗读，构成从动态视觉输入到儿童适龄叙事输出的端云协同闭环。
```

核心创新点：

- 面向真实移动端共读场景，而不是离线图片上传。
- 设计了稳定帧触发和重复页抑制机制，避免翻页中间态频繁识别。
- 使用页框检测、引导框裁剪和整图兜底，提高输入质量和系统鲁棒性。
- 将 VLM 识别结果转为页级状态，维护最近页面和角色表，实现连续讲述。
- 区分快速响应与完整生成，兼顾实时体验和文本质量。
- 加入 Edge TTS 与手机端底部结果抽屉，形成可展示的讲述闭环。
- 记录端到端与分阶段时延，便于系统评估和论文实验分析。

---

## 版本管理说明

不建议提交：

- `.env`
- `logs/`
- `uploads/tts/`
- `models/piper/`
- 本地数据库文件
- 论文中间产物和临时测试文件

推荐提交：

- 后端源码
- 前端静态页面
- `requirements.txt`
- `Dockerfile`
- `docker-compose.yml`
- `.env.example`
- README / DEPLOY 文档
