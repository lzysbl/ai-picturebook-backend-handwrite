# 基于多模态大模型的绘本讲述应用（毕业论文项目）

## 1. 项目定位
本项目对应毕业设计题目《基于多模态大模型的绘本讲述应用》，面向“绘本插画输入 -> 图像语义理解 -> 图文对齐 -> 故事生成 -> 讲述展示与交互 -> 质量评估”的完整流程，构建可运行的后端系统原型。

## 2. 研究与实现方向
项目重点覆盖以下研究与实现方向：
- 插画输入处理与多图像序列建模
- 视觉特征提取与结构化语义信息（角色/场景/情绪）组织
- 跨模态对齐（视觉信息到文本讲述）
- 条件化讲述生成（语气/长度/适龄控制）
- 讲述结果展示与基础交互
- 质量评估（图文对应性、连贯性、适龄性、趣味性/用户体验）

## 3. 当前系统功能（后端）
- 用户注册、登录
- 绘本创建、查询、删除
- 绘本图片上传与查询
- 故事生成（Mock AI 服务层，便于后续接入真实多模态模型）
- 故事记录保存与历史查询
- 故事质量评估接口（可解释评分）

## 4. 技术栈
- Python 3.11
- FastAPI
- SQLAlchemy
- Pydantic
- SQLite / MySQL（可切换）
- Redis（缓存）
- Pillow（图像基础信息读取）

## 5. 项目结构
```text
app/
  core/        # 配置与基础能力（如缓存）
  db/          # 数据库连接、会话、初始化
  models/      # ORM 实体
  schemas/     # 请求/响应模型
  services/    # 业务逻辑
  routers/     # 接口路由
  utils/       # 工具函数（安全、通用能力）
  main.py      # 应用入口
```

## 6. 开发顺序
1. `app/core/config.py`
2. `app/db/base.py` + `app/db/session.py` + `app/db/init_db.py` + `app/db/__init__.py`
3. `app/models/*.py`
4. `app/schemas/*.py`
5. `app/utils/security.py`
6. `app/services/*.py`
7. `app/routers/*.py`
8. `app/main.py`
9. `tests/test_health.py`

## 7. Schemas 图
```mermaid
classDiagram
    class ApiResponse {
      +bool success
      +str message
      +Any|None data
    }

    class UserRegisterRequest {
      +str username
      +str password
    }

    class UserLoginRequest {
      +str username
      +str password
    }

    class UserInfo {
      +int id
      +str username
      +datetime created_at
    }

    class LoginResponseData {
      +str access_token
      +str token_type
      +UserInfo user
    }

    class BookCreateRequest {
      +str title
      +str|None cover_image
    }

    class BookInfo {
      +int id
      +int user_id
      +str title
      +str|None cover_image
      +datetime created_at
    }

    class BookImageInfo {
      +int id
      +int book_id
      +str image_path
      +int image_order
      +datetime created_at
    }

    class StoryGenerateRequest {
      +int user_id
      +int book_id
      +str|None prompt
      +str|None narration_style
      +str|None audience_age
      +str|None story_length
      +str|None character_name
    }

    class StoryEvaluateRequest {
      +str|None story_content
    }

    class StoryInfo {
      +int id
      +int book_id
      +int user_id
      +str|None prompt
      +str|None image_analysis
      +str story_content
      +datetime created_at
    }

    StoryEvaluateRequest --|> StoryGenerateRequest
    LoginResponseData --> UserInfo
    ApiResponse --> LoginResponseData
    ApiResponse --> UserInfo
    ApiResponse --> BookInfo
    ApiResponse --> BookImageInfo
    ApiResponse --> StoryInfo
```

## 8. 数据库 ER 图
```mermaid
erDiagram
    USERS ||--o{ BOOKS : owns
    USERS ||--o{ STORIES : creates
    BOOKS ||--o{ BOOK_IMAGES : contains
    BOOKS ||--o{ STORIES : generates_from

    USERS {
        int id PK
        string username UK
        string password_hash
        datetime created_at
    }

    BOOKS {
        int id PK
        int user_id FK
        string title
        string cover_image
        datetime created_at
    }

    BOOK_IMAGES {
        int id PK
        int book_id FK
        string image_path
        int image_order
        datetime created_at
    }

    STORIES {
        int id PK
        int book_id FK
        int user_id FK
        text prompt
        text image_analysis
        text story_content
        datetime created_at
    }
```

## 9. 后续工作
- 接入真实多模态模型（替换 Mock AI 服务层）
- 完善图文对齐与多页上下文一致性策略
- 增强讲述交互（用户偏好、风格连续调节）
- 完成小规模用户测试与指标统计分析
