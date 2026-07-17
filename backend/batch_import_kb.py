"""
批量导入知识库文档脚本
扫描 backend/knowledge_base/{policy,tech,admin,general}/ 目录下的文件，
自动创建 Document 记录并处理（解析 → 切片 → 向量化 → 存入 OpenSearch）

用法:
  cd backend
  python batch_import_kb.py
"""

import os
import sys
import glob

# 确保 backend 根目录在 path 中
BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from config import KNOWLEDGE_BASE_DIR, SUPPORTED_EXTENSIONS
from app.database import SessionLocal
from app import models
from document_service import process_document

# 目录名 → 模块名映射
DIR_TO_MODULE = {
    "policy": "policy",
    "tech": "tech",
    "admin": "admin",
    "general": "general",
}

# 模块名 → 知识库名称映射（用于匹配数据库中的知识库）
MODULE_TO_KB_NAME = {
    "policy": "规章制度",
    "tech": "产品技术",
    "admin": "行政服务",
    "general": "通用知识",
}

# 默认上传用户（admin 用户）
DEFAULT_UPLOADER_USERNAME = "admin"


def get_kb_id_by_module(module: str, db) -> int | None:
    """根据模块名查找对应的知识库 ID"""
    kb_name = MODULE_TO_KB_NAME.get(module)
    if not kb_name:
        return None
    kb = db.query(models.KnowledgeBase).filter(
        models.KnowledgeBase.name == kb_name,
        models.KnowledgeBase.module == module,
    ).first()
    return kb.id if kb else None


def get_default_user_id(db) -> int:
    """获取默认上传用户 ID"""
    user = db.query(models.User).filter(models.User.username == DEFAULT_UPLOADER_USERNAME).first()
    if user:
        return user.id
    # 如果 admin 不存在，用第一个用户
    user = db.query(models.User).first()
    return user.id if user else 1


def scan_and_import():
    db = SessionLocal()
    try:
        uploader_id = get_default_user_id(db)
        print(f"使用上传用户 ID: {uploader_id}")

        # 扫描每个模块目录
        for dir_name, module in DIR_TO_MODULE.items():
            dir_path = os.path.join(KNOWLEDGE_BASE_DIR, dir_name)
            if not os.path.isdir(dir_path):
                print(f"\n[跳过] 目录不存在: {dir_path}")
                continue

            kb_id = get_kb_id_by_module(module, db)
            if not kb_id:
                print(f"\n[跳过] 未找到模块 '{module}' 对应的知识库")
                continue

            print(f"\n{'='*60}")
            print(f"模块: {module} → 知识库 ID: {kb_id}")
            print(f"{'='*60}")

            # 扫描目录下所有支持的文件
            files = []
            for ext in SUPPORTED_EXTENSIONS:
                pattern = os.path.join(dir_path, f"*{ext}")
                files.extend(glob.glob(pattern))
                # 也匹配大写扩展名
                pattern_upper = os.path.join(dir_path, f"*{ext.upper()}")
                files.extend(glob.glob(pattern_upper))

            # 去重
            files = list(set(files))

            if not files:
                print(f"  目录下没有找到支持的文件")
                continue

            print(f"  找到 {len(files)} 个文件")

            for file_path in files:
                filename = os.path.basename(file_path)
                file_ext = os.path.splitext(filename)[1].lower()

                # 检查是否已经导入过
                existing = db.query(models.Document).filter(
                    models.Document.knowledge_base_id == kb_id,
                    models.Document.filename == filename,
                ).first()

                if existing:
                    print(f"  [跳过] {filename} (已存在, 状态: {existing.status})")
                    continue

                print(f"  [处理] {filename} ...", end=" ", flush=True)

                # 创建 Document 记录
                file_size = os.path.getsize(file_path)
                db_doc = models.Document(
                    knowledge_base_id=kb_id,
                    filename=filename,
                    file_path=file_path,
                    file_type=file_ext[1:],
                    size=file_size,
                    uploaded_by=uploader_id,
                    status="processing",
                )
                db.add(db_doc)
                db.commit()
                db.refresh(db_doc)

                # 处理文档
                result = process_document(file_path, kb_id=kb_id, source=filename)

                if result["success"]:
                    db_doc.status = "completed"
                    db_doc.chunk_count = result["chunk_count"]
                    print(f"完成 ({result['chunk_count']} 个片段)")
                else:
                    db_doc.status = "failed"
                    print(f"失败: {result.get('error')}")

                db.commit()

        print(f"\n{'='*60}")
        print("批量导入完成!")
        print(f"{'='*60}")

    finally:
        db.close()


if __name__ == "__main__":
    scan_and_import()
