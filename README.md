# AI 绘本故事生成网站

这个目录是给你从 0 到 1 手写代码用的。
我已经帮你把文件创建好，每个文件里都有注释提示。

## 手写顺序（严格按这个来）
1. `app/core/config.py`
2. `app/db/base.py` + `app/db/session.py` + `app/db/init_db.py` + `app/db/__init__.py`
3. `app/models/*.py`
4. `app/schemas/*.py`
5. `app/utils/security.py`
6. `app/services/*.py`
7. `app/routers/*.py`
8. `app/main.py`
9. `tests/test_health.py`

## Schemas 图
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

## 数据库 ER 图
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

