# RAG 智能问答系统 - 快速启动指南

## 项目概述

基于本地模型的 RAG（检索增强生成）全流程系统，支持：
- 多格式文档解析（PDF/Word/PPT/Excel/图片 → Markdown）
- 向量嵌入与存储（nomic-embed-text + OpenSearch）
- 语义检索与 RAG 链
- 联网搜索补充（SearXNG）
- 对话历史管理（SQLite）
- 交互式终端界面

## 环境要求

### 已安装的服务
- **Ollama**: http://localhost:11434
  - 模型: `qwen3.5:9b` (LLM), `nomic-embed-text:v1.5` (嵌入)
- **OpenSearch**: https://localhost:9200
  - 账号: `admin` / 密码: `MyPassword123!`
- **SearXNG**: http://localhost:18080
  - Secret: `your-random-secret-key-change-this`
- **MinerU**: http://localhost:8000 (可选，用于文档解析)

### Python 依赖
已安装在 `.venv` 虚拟环境中。

## 快速开始

### 方式一：交互式终端界面（推荐）

```bash
.venv\Scripts\python.exe cli.py
```

功能菜单：
1. **索引知识库文件夹** - 批量导入 `knowledge_base/` 中的文件
2. **上传单个文件** - 支持 PDF/Word/PPT/Excel/MD/TXT/图片
3. **开始对话** - RAG 问答（流式输出）
4. **联网搜索** - SearXNG 搜索
5. **查看对话历史**
6. **清空索引**
7. **查看知识库文件**

### 方式二：FastAPI 服务

```bash
.venv\Scripts\python.exe main.py
```

服务启动在 http://localhost:8888

API 接口：
- `POST /upload` - 上传文件
- `POST /index_knowledge_base` - 批量索引知识库
- `POST /search` - 向量检索
- `POST /chat` - RAG 对话
- `GET /web_search?q=xxx` - 联网搜索
- `GET /history/{session_id}` - 对话历史

### 方式三：运行测试

```bash
.venv\Scripts\python.exe test_rag.py
```

## 知识库管理

### 文件夹位置
```
c:\Users\cc\OneDrive\Desktop\program\backend\knowledge_base\
```

### 已预置的文档
- `rag_intro.md` - RAG 技术详解
- `llm_basics.md` - 大语言模型基础
- `vector_search.md` - 向量搜索技术

### 添加新文档
1. 将文件放入 `knowledge_base/` 文件夹
2. 支持格式：PDF, Word (.doc/.docx), PPT (.ppt/.pptx), Excel (.xls/.xlsx), MD, TXT, HTML, EPUB, 图片
3. 在 CLI 中选择 `[1] 索引知识库文件夹` 或启动时自动索引

## 系统架构

```
用户输入
  ↓
[1] 向量检索 (OpenSearch)
  ↓
[2] 联网搜索 (SearXNG，可选)
  ↓
[3] 构建上下文 + 对话历史
  ↓
[4] LLM 生成 (qwen3.5:9b，流式输出)
  ↓
[5] 保存对话历史 (SQLite)
  ↓
返回答案
```

### 核心模块

| 模块 | 文件 | 功能 |
|------|------|------|
| 配置 | `config.py` | 所有服务地址和参数 |
| 文档解析 | `document_parser.py` | MinerU 统一转 MD + 本地兜底 |
| 文本切片 | `text_splitter.py` | 智能分块 |
| 向量嵌入 | `embedder.py` | nomic-embed-text 调用 |
| 向量存储 | `opensearch_store.py` | OpenSearch KNN 检索 |
| 联网搜索 | `web_search.py` | SearXNG POST + secret |
| RAG 链 | `rag_chain.py` | 检索 + 流式生成 |
| 对话历史 | `conversation_store.py` | SQLite 存储 |
| 终端界面 | `cli.py` | 交互式菜单 |
| API 服务 | `main.py` | FastAPI 接口 |

## 测试验证

运行 `test_rag.py` 验证全流程：

```
测试 1: 文本切片              [PASS]
测试 2: 向量嵌入 (768维)      [PASS]
测试 3: OpenSearch 存储检索   [PASS]
测试 4: SearXNG 联网搜索      [PASS]
测试 5: RAG 完整链路          [PASS]
测试 6: 文档全流程            [PASS]
```

## 注意事项

1. **MinerU 服务**：如果未运行，PDF 会使用 PyPDF2 兜底解析，其他格式（Word/PPT/Excel）需要 MinerU
2. **LLM 推理时间**：qwen3.5:9b 首次加载较慢，后续对话会快一些
3. **SearXNG 配置**：已启用 JSON 格式输出，使用 POST + secret 避免 403
4. **向量维度**：nomic-embed-text 输出 768 维向量，OpenSearch 索引已配置

## 作业要求覆盖

- [x] 离线索引（文档解析 → 切片 → 嵌入 → 存储）
- [x] 向量检索（OpenSearch KNN）
- [x] RAG 链（检索 + 上下文 + LLM 生成）
- [x] 对话历史存储（SQLite）
- [x] 联网搜索（SearXNG）
- [x] 多格式文档支持（MinerU）
- [x] 可交互终端界面
- [x] 知识库文件夹管理

## 代码提交清单

```
backend/
├── config.py              # 配置
├── document_parser.py     # 文档解析
├── text_splitter.py       # 文本切片
├── embedder.py            # 向量嵌入
├── opensearch_store.py    # 向量存储
── web_search.py          # 联网搜索
── rag_chain.py           # RAG 链
├── conversation_store.py  # 对话历史
├── cli.py                 # 终端界面
├── main.py                # API 服务
├── test_rag.py            # 测试脚本
└── knowledge_base/        # 知识库
    ├── rag_intro.md
    ├── llm_basics.md
    └── vector_search.md
```
