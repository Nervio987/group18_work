"""
创建 content_audit_logs 表
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
        # 检查表是否已存在
        tables = conn.execute(text("""
            SELECT table_name FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name = 'content_audit_logs'
        """)).fetchall()

        if tables:
            print("content_audit_logs 表已存在，跳过创建")
            return

        conn.execute(text("""
            CREATE TABLE content_audit_logs (
                id SERIAL PRIMARY KEY,
                document_id INTEGER REFERENCES documents(id),
                filename VARCHAR(300) NOT NULL,
                knowledge_base_id INTEGER REFERENCES knowledge_bases(id),
                user_id INTEGER REFERENCES users(id) NOT NULL,
                verdict VARCHAR(20) NOT NULL,
                confidence FLOAT DEFAULT 0.5,
                categories TEXT,
                reasons TEXT,
                summary TEXT,
                raw_result TEXT,
                status VARCHAR(20) DEFAULT 'pending',
                reviewer_id INTEGER REFERENCES users(id),
                reviewer_comment TEXT,
                created_at TIMESTAMP DEFAULT NOW(),
                reviewed_at TIMESTAMP
            )
        """))

        conn.execute(text("""
            CREATE INDEX ix_content_audit_logs_verdict ON content_audit_logs (verdict)
        """))
        conn.execute(text("""
            CREATE INDEX ix_content_audit_logs_status ON content_audit_logs (status)
        """))
        conn.execute(text("""
            CREATE INDEX ix_content_audit_logs_user ON content_audit_logs (user_id)
        """))

        conn.commit()
        print("content_audit_logs 表创建完成!")


if __name__ == "__main__":
    migrate()
