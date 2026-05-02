# 云端部署说明

本项目推荐使用 `Docker Compose v2` 部署，默认包含：

- `app`：FastAPI 应用
- `db`：MySQL 8
- `redis`：Redis 7

## 1. 服务器准备

确认服务器已安装：

```bash
docker --version
docker compose version
```

## 2. 准备环境变量

复制模板：

```bash
cp .env.example .env
```

至少修改这些字段：

```env
APP_ENV=production
APP_DEBUG=false
SECRET_KEY=replace_with_a_long_random_secret

AI_PROVIDER=qwen
LIVE_AI_PROVIDER=doubao
QWEN_API_KEY=your_qwen_key
DOUBAO_API_KEY=your_doubao_key

JUDGE_ENABLED=true
JUDGE_MODEL=qwen3.6-plus
JUDGE_SAMPLES=1

TTS_PROVIDER=edge
EDGE_TTS_VOICE=zh-CN-XiaoxiaoNeural

MYSQL_ROOT_PASSWORD=replace_mysql_password
MYSQL_DATABASE=ai_story
APP_PORT=8001
```

说明：

- 普通绘本生成与实时识别可以使用不同模型
- `uploads/` 用于保存运行期图片和音频
- `logs/` 用于保存日志与实验数据
- `.env` 不应提交到 Git

## 3. 首次启动

```bash
docker compose up -d --build
docker compose ps
docker compose logs -f app
```

## 4. 访问地址

- 登录页：`http://服务器IP:8001/ui/login`
- 实时识别：`http://服务器IP:8001/ui/camera`
- 接口文档：`http://服务器IP:8001/docs`
- 健康检查：`http://服务器IP:8001/health`

## 5. 更新部署

如果服务器可以直接拉 Git：

```bash
git pull
rm -rf uploads/tts/*
mkdir -p uploads/tts
docker rm -f ai-picturebook-app 2>/dev/null || true
docker compose build app
docker compose up -d app
docker logs -f ai-picturebook-app
```

如果服务器无法直接访问 GitHub，可以本地打包代码后上传再执行：

```bash
rm -rf uploads/tts/*
mkdir -p uploads/tts
docker rm -f ai-picturebook-app 2>/dev/null || true
docker compose build app
docker compose up -d app
docker logs -f ai-picturebook-app
```

## 6. 实验日志与指标导出

扫描与 TTS 指标在日志中记录：

```bash
grep -E "scan.timing|scan.stream_timing|tts.timing" logs/app.log
```

导出论文实验表格：

```bash
python scripts/export_runtime_metrics.py
```

输出目录：

```text
reports/runtime_metrics/
```

## 7. 停止服务

```bash
docker compose down
```

如果连数据库卷一起删除：

```bash
docker compose down -v
```

生产环境不要轻易执行 `docker compose down -v`。

## 8. 论文答辩可用描述

```text
系统采用容器化部署方式，将 FastAPI 应用、MySQL 数据库和 Redis 缓存服务拆分为独立容器，
通过 Docker Compose 统一编排。应用容器负责提供前端页面、REST API、实时绘本识别、
讲述生成与语音朗读能力；MySQL 负责用户、绘本、图片与故事记录持久化；Redis 负责
扫描缓存、会话上下文与限流控制。该部署方式提升了环境一致性，便于迁移到云服务器
进行演示，并支持后续扩展与实验复现。
```
