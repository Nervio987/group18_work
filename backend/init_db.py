from sqlalchemy.orm import Session

from app.database import engine, SessionLocal
from app import models
from app.security import get_password_hash

DEFAULT_ROLES = [
    {
        "name": "管理员",
        "description": "拥有系统所有权限，可管理所有知识库和用户",
        "permissions": ["all"],
    },
    {
        "name": "普通用户",
        "description": "可使用知识库、对话机器人，管理个人知识库",
        "permissions": ["read_all", "write_documents", "manage_personal_kb"],
    },
]

DEFAULT_USERS = [
    {"username": "admin", "email": "admin@example.com", "password": "admin123", "full_name": "管理员", "department": "技术部", "role_name": "管理员"},
    {"username": "admin01", "email": "admin01@example.com", "password": "admin123", "full_name": "管理员01", "department": "技术部", "role_name": "管理员"},
    {"username": "admin02", "email": "admin02@example.com", "password": "admin123", "full_name": "管理员02", "department": "技术部", "role_name": "管理员"},
    {"username": "admin03", "email": "admin03@example.com", "password": "admin123", "full_name": "管理员03", "department": "技术部", "role_name": "管理员"},
    {"username": "admin04", "email": "admin04@example.com", "password": "admin123", "full_name": "管理员04", "department": "技术部", "role_name": "管理员"},
    {"username": "test", "email": "test@example.com", "password": "test123", "full_name": "测试用户", "department": "测试部", "role_name": "普通用户"},
]


def init_db():
    db = SessionLocal()
    try:
        for role_data in DEFAULT_ROLES:
            existing_role = db.query(models.Role).filter(models.Role.name == role_data["name"]).first()
            if not existing_role:
                role = models.Role(**role_data)
                db.add(role)
                db.commit()
                db.refresh(role)
                print(f"Created role: {role.name}")

        for user_data in DEFAULT_USERS:
            existing_user = db.query(models.User).filter(models.User.username == user_data["username"]).first()
            if not existing_user:
                role = db.query(models.Role).filter(models.Role.name == user_data["role_name"]).first()
                hashed_password = get_password_hash(user_data["password"])
                user = models.User(
                    username=user_data["username"],
                    email=user_data["email"],
                    password_hash=hashed_password,
                    full_name=user_data["full_name"],
                    department=user_data["department"],
                    role_id=role.id if role else 2,
                )
                db.add(user)
                db.commit()
                db.refresh(user)
                print(f"Created user: {user.username}")

        print("Database initialization complete!")
    finally:
        db.close()


if __name__ == "__main__":
    init_db()
