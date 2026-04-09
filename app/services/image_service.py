"""图片业务服务层（你开发实现）。

本文件建议实现 3 个函数：
1. save_upload_file(file, upload_dir, book_id)
2. create_book_image_record(db, book_id, image_path, image_order)
3. list_book_images(db, book_id)

设计原则：
- service 只做“文件保存 + 数据库记录”业务，不处理 HTTP 层细节。
- 文件名要避免冲突，目录不存在要自动创建。
"""

# TODO: 导入 os / uuid / pathlib（用于路径和文件名处理）
# 示例：import uuid
# 示例：from pathlib import Path
#
# TODO: 导入 UploadFile（如果你函数参数使用 FastAPI 的上传类型）
# 示例：from fastapi import UploadFile
#
# TODO: 导入 AsyncSession + select（异步 ORM）
# 示例：from sqlalchemy.ext.asyncio import AsyncSession
# 示例：from sqlalchemy import select
#
# TODO: 导入 BookImage 模型
# 示例：from app.models.book_image import BookImage
#
# TODO: 导入 settings（如果 upload_dir 统一从配置读取）
# 示例：from app.core.config import settings


async def save_upload_file(file, upload_dir, book_id):
    """
    保存上传图片到磁盘，返回保存后的路径字符串。

    你要写的逻辑：
    1. 目标目录规则建议：{upload_dir}/books/{book_id}/
    2. 目录不存在就创建（mkdir(parents=True, exist_ok=True)）
    3. 生成唯一文件名（uuid + 原后缀）
    4. 读取 file 内容并写入目标路径
    5. 返回最终路径（建议统一为字符串）

    注意：
    - 后续如果要做安全增强，可以校验后缀/文件头。
    """
    # TODO: 写文件保存逻辑
    pass


async def create_book_image_record(db, book_id, image_path, image_order):
    """
    创建 book_images 表记录。

    你要写的逻辑：
    1. 构建 BookImage(book_id=..., image_path=..., image_order=...)
    2. db.add(record)
    3. await db.commit()
    4. await db.refresh(record)
    5. 返回 record
    """
    # TODO: 写落库逻辑
    pass


async def list_book_images(db, book_id):
    """
    查询某本绘本的全部图片，按 image_order 升序。

    你要写的逻辑：
    1. stmt = select(BookImage).where(BookImage.book_id == book_id).order_by(BookImage.image_order.asc())
    2. result = await db.execute(stmt)
    3. 返回 result.scalars().all()
    """
    # TODO: 写查询逻辑
    pass
