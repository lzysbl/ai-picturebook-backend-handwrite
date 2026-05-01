# AI 绘本故事生成系统（毕业设计项目）

一个基于 FastAPI 的多模态绘本系统，支持：
- 用户注册、登录、找回与重置密码
- 绘本创建/删除、图片上传与分页管理
- 绘本故事生成（同步/异步任务）
- 实时识别（手机浏览器调用摄像头）与连续讲述
- 质量评估（规则指标 + 可选 LLM Judge）
- 论文导出脚本（JSON/CSV）

---

## 1. 技术栈

- Python 3.11
- FastAPI + Uvicorn
- SQLAlchemy Async + Pydantic
- MySQL / SQLite
- Redis（可选但推荐，任务与缓存）
- Pillow + OpenCV（页框检测与图像预处理）

---

## 2. 项目结构

```text
app/
  core/        配置、日志、Redis、请求上下文
  db/          会话与建表初始化
  models/      ORM 模型
  routers/     API 路由
  schemas/     请求/响应模型
  services/    业务逻辑（生成、评估、实时识别等）
  static/      前端页面与脚本（含 camera）
  main.py      应用入口

scripts/       论文评估导出等脚本
tests/         自动化测试
uploads/       上传目录
logs/          日志目录
```

---

## 3. 快速开始（本地）

### 3.1 安装依赖

```bash
pip install -r requirements.txt
```

### 3.2 配置环境变量

```bash
cp .env.example .env
```

至少修改：
- `SECRET_KEY`
- `AI_PROVIDER`（`mock` 或 `qwen`）
- 若用 qwen：`QWEN_API_KEY`

### 3.3 启动服务

```bash
uvicorn app.main:app --reload --port 8001
```

访问地址：
- 登录页：`http://127.0.0.1:8001/ui/login`
- 实时识别：`http://127.0.0.1:8001/ui/camera`
- Swagger：`http://127.0.0.1:8001/docs`
- 健康检查：`http://127.0.0.1:8001/health`

---

## 4. Docker 部署（推荐）

项目提供：
- `Dockerfile`
- `docker-compose.yml`

启动：

```bash
docker compose up -d --build
docker compose ps
docker compose logs -f app
```

服务默认端口：`8001`。

---

## 5. 重要接口

### 用户
- `POST /api/users/register`
- `POST /api/users/login`
- `POST /api/users/forgot-password`
- `POST /api/users/reset-password`
- `POST /api/users/change-password`
- `GET /api/users/me`

### 绘本与图片
- `POST /api/books`
- `GET /api/books`
- `GET /api/books/{book_id}`
- `DELETE /api/books/{book_id}`
- `POST /api/books/{book_id}/images/upload`
- `GET /api/books/{book_id}/images`

### 故事与实时识别
- `POST /api/stories/generate`
- `POST /api/stories/generate/submit`
- `GET /api/stories/tasks/{task_id}`
- `POST /api/stories/scan`
- `POST /api/stories/evaluate`
- `GET /api/stories/{story_id}/quality`
- `GET /api/stories`
- `GET /api/stories/{story_id}`
- `DELETE /api/stories/{story_id}`

统一响应格式：

```json
{
  "success": true,
  "message": "xxx",
  "data": {}
}
```

---

## 6. 实时识别（手机）

页面：`/ui/camera`

当前链路：
1. 手机浏览器调用摄像头
2. 前端引导框与稳定检测
3. 后端可选 OpenCV 页框检测/裁剪
4. 视觉分析（`vision_analysis_service`）
5. 快速讲述或完整生成
6. 质量评估与上下文记忆返回

建议：
- 用 HTTPS 打开页面（手机摄像头权限更稳定）
- 后摄优先，尽量保证光线均匀
- 先点“启动摄像头”，再“识别当前页”

---

## 7. 论文评估导出

脚本：`scripts/export_story_quality_report.py`

示例：

```bash
# 按故事记录导出
python scripts/export_story_quality_report.py --story-id 12 --format json

# 本地文件导出
python scripts/export_story_quality_report.py \
  --analysis-file ./sample_analysis.json \
  --story-file ./sample_story.txt \
  --format csv \
  --output ./report.csv
```

---

## 8. 常见问题

### 8.1 `KeyError: 'ContainerConfig'`（docker-compose 1.29.2）

这是旧版 `docker-compose`（v1）常见问题，建议升级到 Compose v2，并使用 `docker compose`（有空格）。

临时恢复：

```bash
docker rm -f ai-picturebook-app 2>/dev/null || true
docker-compose rm -f app || true
docker-compose up -d --build --no-deps --force-recreate app
```

长期方案：

```bash
sudo apt-get update
sudo apt-get install -y docker-compose-plugin
docker compose version
```

### 8.2 手机端摄像头无法启动

- 检查浏览器权限是否允许摄像头
- 确认使用 HTTPS（或本地 `localhost`）
- 清理浏览器缓存和站点权限后重试

### 8.3 识别文案出现乱码或异常口吻

- 先确认已拉取并部署最新代码
- 检查 `app/services/live_story_service.py` 与 `app/routers/stories.py` 是否为最新版本
- 重新构建镜像并重启 `app` 容器

---

## 9. 测试

```bash
pytest -q
```

可额外做编译检查：

```bash
python -m py_compile app/routers/stories.py app/services/live_story_service.py
```

---

## 10. 说明

- `.env`、`uploads/`、`logs/` 不应提交到仓库
- 项目包含演示与论文场景，建议优先用 Docker 保证环境一致性
## Edge TTS / Piper TTS（可选）

已新增接口：`POST /api/stories/tts`  
用于把实时识别后的讲述文本转成音频并返回播放地址。当前推荐默认使用 Edge TTS，普通话更自然；Piper 保留为离线备用方案。

请求示例：

```json
{
  "text": "这一页里，小熊和小兔一起出发去森林探险。",
  "voice_preset": null
}
```

返回 `data.audio_url`，前端可直接 `<audio src>` 播放。

环境变量：

```env
TTS_PROVIDER=edge
TTS_MAX_CHARS=220

EDGE_TTS_VOICE=zh-CN-XiaoxiaoNeural
EDGE_TTS_RATE=+0%
EDGE_TTS_VOLUME=+0%

# 如需离线朗读，可改为 TTS_PROVIDER=piper
PIPER_BINARY=piper
PIPER_MODEL_PATH=models/piper/zh_CN-huayan-medium.onnx
PIPER_CONFIG_PATH=models/piper/zh_CN-huayan-medium.onnx.json
PIPER_LENGTH_SCALE=1.08
PIPER_NOISE_SCALE=0.667
PIPER_NOISE_W=0.8
PIPER_SENTENCE_SILENCE=0.2
PIPER_USE_CUDA=false
```

Edge TTS 首次使用前安装依赖：

```bash
pip install edge-tts
```

如需使用 Piper 离线模型，首次使用前下载默认中文语音模型：
```bash
python scripts/download_piper_model.py --voice zh_CN-huayan-medium
```

说明：
- 默认关闭（`TTS_PROVIDER=none`），不影响原有识别/生成流程。
- 音频文件保存在 `uploads/tts/`。
- Edge TTS 会生成 mp3，Piper 会生成 wav，前端会直接使用返回的 `audio_url` 播放。
- Piper 模型文件建议放在 `models/piper/`，便于本地和服务器使用同一套路径。
