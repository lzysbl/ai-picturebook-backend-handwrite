# 移动端实时绘本识别与智能讲述系统

面向毕业论文与演示场景的多模态绘本辅助阅读系统。项目通过手机浏览器调用摄像头，识别当前绘本页，生成适龄讲述文本，并支持连续翻页上下文、语音朗读、延迟记录和云端部署。

## 项目定位

本系统的重点不是“上传图片后生成一段故事”，而是面向真实亲子共读流程的实时辅助阅读：

- 手机端直接调用摄像头，无需单独安装 App
- 支持当前页识别、连续翻页讲述、重新识别、保存故事记录
- 支持流式直接讲述与低延迟快速响应
- 支持 TTS 朗读与运行时延迟统计
- 支持本地开发与 Docker 云端部署

论文方向建议表述为：`多模态实时绘本辅助阅读系统`。

## 核心能力

- 实时摄像头识别：浏览器采集视频帧，结合引导框与后端裁剪识别绘本页
- 多种响应模式：
  - `fast`：紧凑识别 + 快速讲述
  - `direct`：直接讲述
  - `full`：完整生成
- 连续故事上下文：用 `session_id` 维护最近页内容，生成总故事文本
- 朗读能力：支持 `edge-tts`，可扩展 `piper`
- 实验指标记录：扫描、流式首字延迟、TTS 时延都会写入日志
- 云端部署：支持 `docker compose` 一键启动

## 系统流程

```text
手机摄像头取景
-> 页面稳定检测
-> 引导框 / OpenCV 裁剪
-> 视觉模型识别
-> 当前页讲述 / 总故事累积
-> TTS 朗读
-> 日志记录与实验统计
```

## 技术栈

- 后端：FastAPI、Pydantic、SQLAlchemy Async
- 前端：HTML、CSS、Vanilla JavaScript
- 数据：SQLite / MySQL、Redis
- 视觉模型：Qwen / Doubao（实时识别可单独配置）
- 语音：Edge TTS、Piper
- 部署：Docker、Docker Compose v2

## 目录结构

```text
app/
  core/        配置、日志、Redis
  db/          数据库会话与初始化
  models/      ORM 模型
  routers/     API 路由
  schemas/     请求/响应模型
  services/    视觉识别、实时扫描、故事生成、TTS、评估
  static/      前端页面与脚本

scripts/       论文辅助脚本、模型下载、日志导出
tests/         单元测试
uploads/       运行期图片与语音
logs/          应用日志
```

## 快速开始

1. 安装依赖

```bash
pip install -r requirements.txt
```

2. 复制环境变量

```bash
cp .env.example .env
```

Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

3. 启动项目

```bash
uvicorn app.main:app --reload --port 8001
```

4. 打开页面

- 登录页：`http://127.0.0.1:8001/ui/login`
- 实时识别：`http://127.0.0.1:8001/ui/camera`
- 接口文档：`http://127.0.0.1:8001/docs`

## 环境变量说明

普通绘本生成与实时识别支持分离配置：

```env
AI_PROVIDER=qwen
LIVE_AI_PROVIDER=doubao
QWEN_MODEL=qwen3.6-flash
DOUBAO_MODEL=doubao-seed-2-0-mini-260215
```

TTS 示例：

```env
TTS_PROVIDER=edge
EDGE_TTS_VOICE=zh-CN-XiaoxiaoNeural
EDGE_TTS_RATE=+0%
EDGE_TTS_VOLUME=+0%
```

## 主要接口

- `POST /api/stories/scan`：实时识别当前帧
- `POST /api/stories/scan/stream`：流式讲述当前帧
- `POST /api/stories/tts`：将讲述文本转为语音
- `POST /api/stories/scan/save`：保存实时扫描故事记录
- `POST /api/stories/generate`：根据绘本图片生成故事
- `POST /api/stories/evaluate`：独立评估故事质量

## 时延与论文实验

### 运行时日志

系统会将关键时延写入 `logs/app.log`：

- `scan.timing`
- `scan.stream_timing`
- `tts.timing`

可以直接搜索：

```bash
grep -E "scan.timing|scan.stream_timing|tts.timing" logs/app.log
```

PowerShell:

```powershell
Select-String -Path logs/app.log -Pattern "scan.timing|scan.stream_timing|tts.timing"
```

### 导出实验表格

新增脚本：

```bash
python scripts/export_runtime_metrics.py
```

默认输出到：

```text
reports/runtime_metrics/runtime_metrics_summary.md
reports/runtime_metrics/scan_metrics_raw.csv
reports/runtime_metrics/tts_metrics_raw.csv
```

这几份文件可以直接作为论文实验表、附录原始数据或答辩材料使用。

## 测试与检查

静态检查：

```bash
python -m py_compile app/routers/stories.py app/services/*.py
node --check app/static/camera.js
```

核心测试：

```bash
pytest tests/test_story_scan_crop.py tests/test_live_story_tone.py tests/test_eval_service.py tests/test_health.py
```

## 云端部署

使用 Docker Compose v2：

```bash
cp .env.example .env
docker compose up -d --build
docker compose logs -f app
```

更新部署可参考 [DEPLOY.md](DEPLOY.md)。

如果服务器网络不稳定，也可以先在本地执行：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/build_deploy_zip.ps1
```

部署压缩包会输出到 `release/deploy.zip`，该目录已加入忽略规则，不会影响 `git status`。

## 真实应用参考

论文中可用于对比的真实产品方向：

- Microsoft Seeing AI：强调摄像头识别、语音反馈、文档/场景阅读
- Google Lookout：强调模式化识别与辅助阅读
- Gemini Storybooks：强调个性化故事体验与多模态生成

本项目与这些真实应用的区别在于：聚焦中文绘本辅助阅读、移动端实时扫描、连续上下文讲述和论文可复现实验。
