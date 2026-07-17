"""
为 conversation_favorites 表添加 message_id 字段
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
        columns = conn.execute(text("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'conversation_favorites'
        """)).fetchall()

        existing_cols = [c[0] for c in columns]
        print(f"现有字段: {existing_cols}")

        if 'message_id' not in existing_cols:
            conn.execute(text("ALTER TABLE conversation_favorites ADD COLUMN message_id VARCHAR(100)"))
            conn.execute(text("CREATE INDEX ix_conversation_favorites_message_id ON conversation_favorites (message_id)"))
            print("已添加 message_id 字段及索引")

        conn.commit()
        print("数据库迁移完成!")


if __name__ == "__main__":
    migrate()
