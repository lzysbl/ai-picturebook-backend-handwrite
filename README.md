# 移动端实时绘本识别与智能讲述系统

面向真实亲子共读场景的毕业设计项目。系统通过手机浏览器调用摄像头，连续观察绘本页面，在页面稳定后自动识别当前页，并结合前序页面上下文生成适龄、连贯、可朗读的讲述文本。

一句话概括：这不是“上传图片生成故事”，而是一个面向移动端连续翻页场景的实时视觉理解与低时延讲述系统。

---

## 功能亮点

- 手机浏览器实时调用摄像头，无需原生 App。
- 页面稳定检测与重复页抑制，避免翻页中间态频繁识别。
- 前端引导框 + 后端 OpenCV 页框检测，自动裁剪绘本页区域。
- VLM 提取角色、场景、动作、关键物体、画面文字等页级信息。
- 基于 `session_id` 维护最近页面，实现连续翻页讲述。
- 支持快速响应与完整生成两种模式。
- 支持 Edge TTS 一键朗读当前讲述。
- 手机端使用底部故事抽屉，边拍边看/听更方便。
- 记录识别、裁剪、讲述、评估、TTS 等阶段耗时，便于论文汇报。

---

## 系统流程

```text
摄像头取景
  -> 稳定帧检测
  -> 页框裁剪 / 整图兜底
  -> 多模态页面理解
  -> 页级上下文记忆
  -> 快速讲述 / 完整生成
  -> 前端展示 / Edge TTS 朗读
  -> 日志记录时延
```

裁剪优先级：

```text
后端 OpenCV 页框 > 前端引导框 > 整图识别
```

---

## 技术栈

- 后端：FastAPI、Python 3.11、SQLAlchemy Async、Pydantic
- 前端：原生 HTML / CSS / JavaScript
- 数据：SQLite / MySQL、Redis
- 视觉：Pillow、OpenCV、Qwen VL 兼容接口
- 语音：Edge TTS，Piper 离线备用
- 部署：Docker、Docker Compose v2

---

## 快速运行

```bash
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --port 8001
```

访问：

- 实时识别：`http://127.0.0.1:8001/ui/camera`
- 登录页：`http://127.0.0.1:8001/ui/login`
- 接口文档：`http://127.0.0.1:8001/docs`

最小本地配置：

```env
DATABASE_URL=sqlite+aiosqlite:///./ai_story.db
AI_PROVIDER=mock
REDIS_ENABLED=false
TTS_PROVIDER=edge
EDGE_TTS_VOICE=zh-CN-XiaoxiaoNeural
EDGE_TTS_RATE=-5%
EDGE_TTS_VOLUME=+0%
```

使用 Qwen 时补充：

```env
AI_PROVIDER=qwen
QWEN_MODEL=qwen3.6-flash
QWEN_API_KEY=你的 API Key
```

---

## Docker 部署

```bash
cp .env.example .env
docker compose up -d --build
docker logs -f ai-picturebook-app
```

更新云端：

```bash
git pull
rm -rf uploads/tts/*
mkdir -p uploads/tts
docker rm -f ai-picturebook-app 2>/dev/null || true
docker compose build app
docker compose up -d app
```

更完整的服务器部署说明见 [DEPLOY.md](DEPLOY.md)。

---

## 响应模式

快速响应：只调用视觉理解模型，随后用本地规则生成页级短讲述，适合实时翻页。

完整生成：在页面理解后再次调用故事生成模型，文本更丰富，但耗时更高。

核心区别：

```text
快速响应：VLM 识别 -> 结构化摘要 -> 本地讲述模板
完整生成：VLM 识别 -> 上下文输入 -> 大模型故事生成
```

---

## 时延统计

扫描接口 `/api/stories/scan` 会返回 `timing` 字段，并写入日志：

```json
{
  "response_mode": "fast",
  "crop_mode": "guide_crop",
  "analysis_ms": 3200,
  "story_ms": 0,
  "quality_ms": 1,
  "total_ms": 3260
}
```

查看日志：

```bash
grep -E "scan.timing|tts.timing" logs/app.log
```

PowerShell：

```powershell
Select-String -Path logs/app.log -Pattern "scan.timing|tts.timing"
```

---

## 主要接口

- `POST /api/stories/scan`：实时识别当前摄像头帧
- `POST /api/stories/tts`：生成朗读音频
- `POST /api/stories/generate`：根据绘本图片生成故事
- `POST /api/stories/generate/submit`：异步生成故事
- `GET /api/stories/tasks/{task_id}`：查询任务进度
- `POST /api/stories/evaluate`：故事质量评估
- `GET /api/books`：绘本列表
- `POST /api/books/{book_id}/images/upload`：上传绘本图片

---

## 项目结构

```text
app/
  routers/     API 路由
  services/    视觉理解、故事生成、实时讲述、TTS、评估
  static/      前端页面与脚本
  models/      数据库模型
  core/        配置、日志、Redis

scripts/       辅助脚本
uploads/       上传文件与运行时音频
logs/          应用日志
```

---

## 测试

```bash
pytest -q
python -m py_compile app/routers/stories.py app/services/live_story_service.py app/services/tts_service.py
node --check app/static/camera.js
```

---

## 答辩表述

本课题研究的不是传统的上传图片后生成故事，而是一个面向手机浏览器连续翻页场景的实时绘本视觉理解与低时延智能讲述系统。系统通过摄像头采集、稳定检测、页框裁剪、图文联合理解、上下文记忆、快速讲述生成和语音朗读，构成从动态视觉输入到儿童适龄叙事输出的端云协同闭环。

核心创新点：

- 面向真实移动端共读场景。
- 稳定触发和重复页抑制降低无效识别。
- 页框检测与裁剪增强提升输入质量。
- 页级状态和角色表支持连续讲述。
- 快速响应与完整生成兼顾延迟和文本质量。
- 分阶段时延日志便于系统评估。

---

## 版本管理

不要提交：

- `.env`
- `logs/`
- `uploads/tts/`
- `models/piper/`
- 本地数据库和临时报告文件
