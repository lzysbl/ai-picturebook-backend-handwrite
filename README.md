# AI 绘本故事生成系统（毕业论文项目）

一个可运行的 FastAPI 全栈原型系统，支持：
- 用户注册、登录（JWT 鉴权）
- 绘本创建、查询、删除
- 图片上传与分页管理
- 多页图片分析并生成故事
- 故事历史查询、详情查看、删除
- 规则评分 + 可选 LLM 深度评分
- 异步任务进度轮询（刷新页面可恢复）
- Swagger 接口文档

---

## 1. 技术栈

- Python 3.11+
- FastAPI + Uvicorn
- SQLAlchemy（Async）+ Pydantic
- SQLite / MySQL（可切换）
- Redis（可选：任务进度、评分缓存、限流）
- Pillow
- OpenAI 兼容 SDK（用于 Qwen 兼容接口）

---

## 2. 项目结构

```text
app/
  core/        # 配置、日志、Redis、请求上下文
  db/          # Base、异步会话、建表初始化
  models/      # ORM 模型（users/books/book_images/stories）
  routers/     # API 路由层
  schemas/     # 请求与响应模型
  services/    # 业务逻辑（用户/绘本/图片/AI/评估/任务进度）
  static/      # 前端页面与 JS/CSS（登录、注册、管理、上传、生成、历史）
  utils/       # 工具函数（安全、限流、爬虫等）
  main.py      # 应用入口

tests/         # 测试与连通性脚本
uploads/       # 上传图片目录
logs/          # 运行日志目录
```

---

## 3. 环境准备

### 3.1 安装依赖

```bash
pip install -r requirements.txt
```

### 3.2 使用 `.env.example`

项目已提供环境变量模板文件 [`.env.example`](C:/Users/runsing/Desktop/毕业论文/项目代码_手写版/.env.example)。

先复制为 `.env`：

```bash
cp .env.example .env
```

Windows PowerShell：

```powershell
Copy-Item .env.example .env
```

然后修改 `.env` 中这些关键项：
- `DATABASE_URL`
- `SECRET_KEY`
- `QWEN_API_KEY`（如果启用 Qwen）

### 3.3 `.env` 字段结构说明

#### 应用基础
- `APP_NAME`：应用名称（Swagger 标题会使用）
- `APP_ENV`：运行环境（如 `development` / `production`）
- `APP_DEBUG`：是否调试模式（`true/false`）

#### 数据库
- `DATABASE_URL`：数据库连接串
  - SQLite：`sqlite+aiosqlite:///./ai_story.db`
  - MySQL：`mysql+aiomysql://用户名:密码@主机:端口/库名?charset=utf8mb4`

#### 鉴权
- `SECRET_KEY`：JWT 签名密钥（必须自定义，不要泄露）
- `ACCESS_TOKEN_EXPIRE_MINUTES`：登录 token 过期时间（分钟）

#### 文件上传
- `UPLOAD_DIR`：上传图片保存目录（如 `./uploads`）

#### AI 生成
- `AI_PROVIDER`：`mock` 或 `qwen`
- `QWEN_MODEL`：模型名（如 `qwen3.6-flash`）
- `QWEN_BASE_URL`：兼容接口地址
- `QWEN_API_KEY`：模型服务 API Key（敏感）

#### Redis（可选）
- `REDIS_ENABLED`：是否启用 Redis
- `REDIS_URL`：Redis 连接地址
- `STORY_CACHE_TTL_SECONDS`：任务状态缓存 TTL（秒）
- `QUALITY_CACHE_TTL_SECONDS`：评分缓存 TTL（秒）

#### 限流
- `RATE_LIMIT_ENABLED`：是否启用限流
- `RATE_LIMIT_LOGIN_LIMIT` / `RATE_LIMIT_LOGIN_WINDOW_SECONDS`
- `RATE_LIMIT_REGISTER_LIMIT` / `RATE_LIMIT_REGISTER_WINDOW_SECONDS`
- `RATE_LIMIT_STORY_SUBMIT_LIMIT` / `RATE_LIMIT_STORY_SUBMIT_WINDOW_SECONDS`

#### 深度评分
- `JUDGE_ENABLED`：是否开启 LLM 深度评分
- `JUDGE_MODEL`：深度评分模型
- `JUDGE_SAMPLES`：采样次数（建议 1~3）

#### 日志
- `LOG_LEVEL`：日志级别（`INFO`/`WARNING`/`ERROR`）
- `LOG_DIR`：日志目录
- `LOG_FILE`：日志文件名
- `LOG_MAX_BYTES`：单文件最大字节数
- `LOG_BACKUP_COUNT`：日志轮转保留份数

---

## 4. 数据库启动（MySQL 可选）

如果使用 MySQL，先建库：

```sql
CREATE DATABASE IF NOT EXISTS ai_story DEFAULT CHARSET utf8mb4;
```

应用启动时会自动执行建表（`init_db`）。

---

## 5. 运行项目

在项目根目录执行：

```bash
uvicorn app.main:app --reload --port 8001
```

访问：
- 前端入口：`http://127.0.0.1:8001/ui/login`
- Swagger：`http://127.0.0.1:8001/docs`
- 健康检查：`http://127.0.0.1:8001/health`

---

## 6. 页面入口（已拆分）

- `/ui/login`：登录
- `/ui/register`：注册
- `/ui/books`：绘本管理
- `/ui/upload`：图片上传
- `/ui/generate`：故事生成
- `/ui/history`：历史记录与评分

---

## 7. 主要 API

### 用户
- `POST /api/users/register`
- `POST /api/users/login`
- `GET /api/users/me`

### 绘本
- `POST /api/books`
- `GET /api/books`
- `GET /api/books/{book_id}`
- `DELETE /api/books/{book_id}`

### 图片
- `POST /api/books/{book_id}/images/upload`
- `GET /api/books/{book_id}/images`

### 故事
- `POST /api/stories/generate`（同步）
- `POST /api/stories/generate/submit`（异步提交）
- `GET /api/stories/tasks/{task_id}`（进度轮询）
- `GET /api/stories`
- `GET /api/stories/{story_id}`
- `DELETE /api/stories/{story_id}`
- `GET /api/stories/{story_id}/quality`
- `POST /api/stories/evaluate`

统一响应格式：

```json
{
  "success": true,
  "message": "xxx",
  "data": {}
}
```

---

## 8. 生成与评分流程

1. 前端提交异步任务 `/api/stories/generate/submit`
2. 后端按页分析图片（并发）
3. 生成故事并入库
4. 计算基础评分（连贯性、年龄适配、文本指标）
5. 可选 LLM 深度评分（`JUDGE_ENABLED=true` + `include_judge=true`）
6. 前端轮询任务进度并展示结果

---

## 9. Redis 在本项目中的作用

- 异步任务进度状态缓存
- 故事评分缓存（避免重复评分）
- 接口限流（登录/注册/生成）

当 `REDIS_ENABLED=false` 或 Redis 不可用时，系统自动降级为内存模式（单机开发可用）。

---

## 10. 常见问题

1. `ModuleNotFoundError: No module named 'app'`  
请在项目根目录运行：`uvicorn app.main:app ...`

2. `ConnectionRefusedError: ('127.0.0.1', 3306)`  
MySQL 未启动或连接串错误，检查 `DATABASE_URL`。

3. `WinError 10013`  
端口冲突或权限问题，换端口：

```bash
uvicorn app.main:app --reload --port 8002
```

4. `bcrypt` 相关报错  
项目已固定兼容版本：`passlib[bcrypt]==1.7.4` + `bcrypt==4.0.1`

---

## 11. 说明

- `.env`、`uploads/`、`logs/`、`demo_book/`、`learning/` 已被忽略，不会提交到 Git。
- 本项目目标是：可运行、可演示、可扩展，支持毕业设计展示与求职项目展示。
