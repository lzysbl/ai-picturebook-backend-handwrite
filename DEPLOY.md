# 部署说明

本项目推荐使用 Docker Compose 部署。部署后包含三个服务：

- `app`：FastAPI 应用，提供前端页面和后端接口。
- `db`：MySQL 8.0，保存用户、绘本、图片、故事记录。
- `redis`：Redis 7，保存任务进度、评分缓存和限流数据。

## 1. 服务器准备

服务器需要安装：

- Docker
- Docker Compose v2

检查命令：

```bash
docker --version
docker compose version
```

## 2. 准备环境变量

复制环境变量模板：

```bash
cp .env.example .env
```

至少修改这些字段：

```env
APP_ENV=production
APP_DEBUG=false
SECRET_KEY=换成一段足够长的随机字符串

AI_PROVIDER=qwen
QWEN_MODEL=qwen3.6-plus
QWEN_API_KEY=你的阿里云百炼APIKey

JUDGE_ENABLED=true
JUDGE_MODEL=qwen3.6-plus
JUDGE_SAMPLES=1

MYSQL_ROOT_PASSWORD=换成你的MySQL容器密码
MYSQL_DATABASE=ai_story
APP_PORT=8001
```

说明：

- `docker-compose.yml` 会自动把应用内数据库地址改成 `db` 容器地址。
- 上传图片保存在宿主机的 `uploads/` 目录。
- 日志保存在宿主机的 `logs/` 目录。
- `.env` 不要提交到 GitHub。

## 3. 启动服务

在项目根目录执行：

```bash
docker compose up -d --build
```

查看容器：

```bash
docker compose ps
```

查看日志：

```bash
docker compose logs -f app
```

## 4. 访问系统

如果服务器安全组已经放行 `8001` 端口，可以访问：

```text
http://服务器公网IP:8001/ui/login
```

接口文档：

```text
http://服务器公网IP:8001/docs
```

健康检查：

```text
http://服务器公网IP:8001/health
```

## 5. 更新部署

拉取或上传新代码后执行：

```bash
docker compose up -d --build
```

## 6. 停止服务

停止容器但保留数据库数据：

```bash
docker compose down
```

如果连 MySQL 和 Redis 数据卷也要删除：

```bash
docker compose down -v
```

生产环境不要轻易执行 `docker compose down -v`。

## 7. 论文和答辩可描述内容

部署架构可以这样描述：

```text
系统采用容器化部署方式，将 FastAPI 应用、MySQL 数据库和 Redis 缓存服务拆分为独立容器，通过 Docker Compose 统一编排。应用容器负责提供前端页面、REST API 和 AI 绘本生成能力；MySQL 负责持久化用户、绘本、图片和故事记录；Redis 负责异步任务进度、评分缓存和接口限流。该部署方式提升了系统环境一致性，便于迁移到云服务器进行演示和后续扩展。
```
