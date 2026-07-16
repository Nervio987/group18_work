"""RAG系统配置"""

import os
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))

# PostgreSQL
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_PORT = int(os.getenv("POSTGRES_PORT", "5432"))
POSTGRES_DB = os.getenv("POSTGRES_DB", "rag_db")
POSTGRES_USER = os.getenv("POSTGRES_USER", "postgres")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "MyPassword123!")

# OpenSearch
OPENSEARCH_HOST = os.getenv("OPENSEARCH_HOST", "https://localhost:9200")
OPENSEARCH_USER = os.getenv("OPENSEARCH_USER", "admin")
OPENSEARCH_PASSWORD = os.getenv("OPENSEARCH_PASSWORD", "MyPassword123!")
OPENSEARCH_INDEX_PREFIX = os.getenv("OPENSEARCH_INDEX_PREFIX", "rag_docs")
OPENSEARCH_INDEX = OPENSEARCH_INDEX_PREFIX  # 向后兼容别名
OPENSEARCH_USE_SSL = OPENSEARCH_HOST.startswith("https://")

# Ollama (仅用于嵌入模型)
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
EMBED_MODEL = os.getenv("EMBED_MODEL", "qwen3-embedding:0.6b")

# DeepSeek API (用于 LLM 推理)
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
LLM_MODEL = os.getenv("LLM_MODEL", "deepseek-chat")

# Ollama 本地聊天模型（备选）
OLLAMA_CHAT_MODEL = os.getenv("OLLAMA_CHAT_MODEL", "qwen3.5:9b")

# SearXNG
SEARXNG_HOST = os.getenv("SEARXNG_HOST", "http://localhost:18080")
SEARXNG_SECRET = os.getenv("SEARXNG_SECRET", "your-random-secret-key-change-this")

# MinerU API
MINERU_HOST = os.getenv("MINERU_HOST", "http://127.0.0.1:8000")

# Redis
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))

# 知识库文件夹
KNOWLEDGE_BASE_DIR = os.path.join(BASE_DIR, "knowledge_base")

# 文本切片
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "500"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "100"))

# 检索
TOP_K = int(os.getenv("TOP_K", "5"))
WEB_SEARCH_COUNT = int(os.getenv("WEB_SEARCH_COUNT", "3"))

# 对话历史
HISTORY_TURNS = int(os.getenv("HISTORY_TURNS", "10"))

# 嵌入维度（qwen3-embedding:0.6b = 1024, qwen3-embedding:4b = 2560, nomic-embed-text = 768）
EMBED_DIMENSION = int(os.getenv("EMBED_DIMENSION", "1024"))

# LLM 推理超时（秒）
LLM_TIMEOUT = int(os.getenv("LLM_TIMEOUT", "600"))

# 支持的文件格式（MinerU 可处理）
SUPPORTED_EXTENSIONS = {
    ".pdf", ".doc", ".docx", ".ppt", ".pptx",
    ".xls", ".xlsx", ".md", ".txt", ".html", ".htm",
    ".epub", ".mobi", ".jpg", ".jpeg", ".png",
}

# ========== LoRA 微调配置 ==========
FINETUNE_BASE_MODEL = os.getenv("FINETUNE_BASE_MODEL", "Qwen/Qwen2.5-7B-Instruct")
FINETUNE_OUTPUT_DIR = os.path.join(BASE_DIR, "finetune", "output")
FINETUNE_DATA_DIR = os.path.join(BASE_DIR, "finetune", "data")

# LoRA 参数
FINETUNE_LORA_R = int(os.getenv("FINETUNE_LORA_R", "16"))
FINETUNE_LORA_ALPHA = int(os.getenv("FINETUNE_LORA_ALPHA", "32"))
FINETUNE_LORA_DROPOUT = float(os.getenv("FINETUNE_LORA_DROPOUT", "0.05"))

# 训练参数
FINETUNE_NUM_EPOCHS = int(os.getenv("FINETUNE_NUM_EPOCHS", "3"))
FINETUNE_BATCH_SIZE = int(os.getenv("FINETUNE_BATCH_SIZE", "4"))
FINETUNE_LEARNING_RATE = float(os.getenv("FINETUNE_LEARNING_RATE", "2e-4"))
FINETUNE_GRADIENT_ACCUMULATION_STEPS = int(os.getenv("FINETUNE_GRADIENT_ACCUMULATION_STEPS", "4"))
FINETUNE_MAX_SEQ_LENGTH = int(os.getenv("FINETUNE_MAX_SEQ_LENGTH", "2048"))
FINETUNE_WARMUP_RATIO = float(os.getenv("FINETUNE_WARMUP_RATIO", "0.1"))
FINETUNE_WEIGHT_DECAY = float(os.getenv("FINETUNE_WEIGHT_DECAY", "0.01"))

# 数据准备
FINETUNE_MIN_QUERY_LENGTH = int(os.getenv("FINETUNE_MIN_QUERY_LENGTH", "5"))
FINETUNE_MIN_ANSWER_LENGTH = int(os.getenv("FINETUNE_MIN_ANSWER_LENGTH", "10"))
FINETUNE_TEST_SPLIT_RATIO = float(os.getenv("FINETUNE_TEST_SPLIT_RATIO", "0.1"))
