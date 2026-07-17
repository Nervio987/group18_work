"""
为 documents 表添加审核相关字段，并更新 status 枚举
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
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'documents'
        """)).fetchall()
        existing_cols = [c[0] for c in columns]
        print(f"现有字段: {existing_cols}")

        if 'audit_id' not in existing_cols:
            conn.execute(text("ALTER TABLE documents ADD COLUMN audit_id INTEGER REFERENCES content_audit_logs(id)"))
            print("已添加 audit_id 字段")

        if 'audit_status' not in existing_cols:
            conn.execute(text("ALTER TABLE documents ADD COLUMN audit_status VARCHAR(20) DEFAULT 'pending'"))
            print("已添加 audit_status 字段")

        if 'rejection_reason' not in existing_cols:
            conn.execute(text("ALTER TABLE documents ADD COLUMN rejection_reason TEXT"))
            print("已添加 rejection_reason 字段")

        # 更新 status 枚举类型，添加 rejected 和 pending_review
        try:
            conn.execute(text("""
                ALTER TYPE document_status ADD VALUE 'rejected'
            """))
            conn.execute(text("""
                ALTER TYPE document_status ADD VALUE 'pending_review'
            """))
            print("已更新 document_status 枚举类型")
        except Exception as e:
            print(f"枚举更新跳过（可能已存在）: {e}")

        conn.commit()
        print("documents 表迁移完成!")


if __name__ == "__main__":
    migrate()
