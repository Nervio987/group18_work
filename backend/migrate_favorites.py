"""
为 conversation_favorites 表添加新字段：query, answer, module
"""

import sys
import os

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app.database import engine
from sqlalchemy import text


def migrate():
    with engine.connect() as conn:
        # 检查字段是否已存在
        columns = conn.execute(text("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'conversation_favorites'
        """)).fetchall()

        existing_cols = [c[0] for c in columns]
        print(f"现有字段: {existing_cols}")

        # 添加 query 字段
        if 'query' not in existing_cols:
            conn.execute(text("ALTER TABLE conversation_favorites ADD COLUMN query TEXT"))
            print("已添加 query 字段")

        # 添加 answer 字段
        if 'answer' not in existing_cols:
            conn.execute(text("ALTER TABLE conversation_favorites ADD COLUMN answer TEXT"))
            print("已添加 answer 字段")

        # 添加 module 字段
        if 'module' not in existing_cols:
            conn.execute(text("ALTER TABLE conversation_favorites ADD COLUMN module VARCHAR(50) DEFAULT 'general'"))
            print("已添加 module 字段")

        conn.commit()
        print("数据库迁移完成!")


if __name__ == "__main__":
    migrate()
