"""RAG 系统交互式终端界面"""

import os
import sys
import uuid

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import KNOWLEDGE_BASE_DIR, LLM_MODEL, DEEPSEEK_BASE_URL
from document_parser import parse_document, scan_knowledge_base
from text_splitter import split_text
from opensearch_store import add_documents, search, ensure_index, clear_index
from rag_chain import rag_query
from conversation_store import init_db, get_history, clear_session, list_sessions
from web_search import web_search


def print_banner():
    print()
    print("=" * 60)
    print("       RAG 智能问答系统")
    print("       本地模型: qwen3.5:9b + nomic-embed-text:v1.5")
    print("=" * 60)
    print()


def print_menu():
    print("-" * 40)
    print("  [1] 索引知识库文件夹（批量导入）")
    print("  [2] 上传单个文件并索引")
    print("  [3] 开始对话（RAG 问答）")
    print("  [4] 联网搜索")
    print("  [5] 查看对话历史")
    print("  [6] 清空索引")
    print("  [7] 查看知识库文件")
    print("  [8] 查看已上传文件")
    print("  [0] 退出")
    print("-" * 40)


def cmd_index_knowledge_base():
    """批量索引知识库文件夹"""
    kb_dir = KNOWLEDGE_BASE_DIR
    files = scan_knowledge_base(kb_dir)

    if not files:
        print(f"\n  知识库文件夹为空: {kb_dir}")
        print("  请将文件放入该文件夹后重试。\n")
        return

    print(f"\n  发现 {len(files)} 个文件:")
    for i, f in enumerate(files, 1):
        name = os.path.basename(f)
        size = os.path.getsize(f)
        print(f"    [{i}] {name} ({size // 1024} KB)")

    confirm = input("\n  是否全部索引？(y/n): ").strip().lower()
    if confirm != "y":
        print("  已取消。\n")
        return

    total_chunks = 0
    total_indexed = 0
    for f in files:
        name = os.path.basename(f)
        try:
            text = parse_document(f)
            chunks = split_text(text)
            n = add_documents(chunks, source=name)
            total_chunks += len(chunks)
            total_indexed += n
            print(f"  [OK] {name}: {len(chunks)} chunks, {n} indexed")
        except Exception as e:
            print(f"  [FAIL] {name}: {e}")

    print(f"\n  完成！共 {total_chunks} 个切片，{total_indexed} 条入库。\n")


UPLOAD_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads")


def cmd_upload_file():
    """上传单个文件并索引（文件会保存到 uploads/ 文件夹）"""
    os.makedirs(UPLOAD_DIR, exist_ok=True)

    print("\n  支持格式: PDF, Word, PPT, Excel, MD, TXT, HTML, EPUB, 图片")
    print("  操作方式:")
    print("    1. 直接拖拽文件到终端窗口")
    print("    2. 粘贴文件完整路径")
    print("    3. 输入编号从知识库选择\n")

    # 列出知识库文件供选择
    kb_files = scan_knowledge_base(KNOWLEDGE_BASE_DIR)
    if kb_files:
        print("  知识库中的文件:")
        for i, f in enumerate(kb_files, 1):
            print(f"    [{i}] {os.path.basename(f)}")
        print()

    choice = input("  拖拽文件/输入路径/输入编号: ").strip()

    if not choice:
        print("  已取消。\n")
        return

    # 去掉拖拽文件时可能带有的引号
    choice = choice.strip('"').strip("'")

    # 如果是数字编号，从知识库选
    if choice.isdigit() and 1 <= int(choice) <= len(kb_files):
        file_path = kb_files[int(choice) - 1]
    else:
        file_path = choice

    if not os.path.exists(file_path):
        print(f"  文件不存在: {file_path}\n")
        return

    # 复制文件到 uploads/ 文件夹保存
    import shutil
    filename = os.path.basename(file_path)
    saved_path = os.path.join(UPLOAD_DIR, filename)
    # 如果同名文件已存在，加序号
    if os.path.exists(saved_path):
        name, ext = os.path.splitext(filename)
        counter = 1
        while os.path.exists(saved_path):
            saved_path = os.path.join(UPLOAD_DIR, f"{name}_{counter}{ext}")
            counter += 1
    shutil.copy2(file_path, saved_path)
    print(f"  文件已保存到: {saved_path}")

    try:
        text = parse_document(saved_path)
        chunks = split_text(text)
        n = add_documents(chunks, source=filename)
        print(f"  [OK] {filename}: {len(chunks)} chunks, {n} indexed\n")
    except Exception as e:
        print(f"  [FAIL] {e}\n")


def cmd_chat():
    """RAG 对话"""
    session_id = str(uuid.uuid4())[:8]
    print(f"\n  会话 ID: {session_id}")
    print("  输入问题开始对话")
    print("  /web    - 切换联网模式")
    print("  /rerank - 切换 Rerank 精排")
    print("  /rewrite- 切换查询重述")
    print("  /exit   - 退出对话\n")

    use_web = False
    use_rerank = True
    use_rewrite = True
    while True:
        flags = []
        if use_web:
            flags.append("联网")
        if use_rerank:
            flags.append("Rerank")
        if use_rewrite:
            flags.append("重述")
        mode = f"[{'|'.join(flags) if flags else '基础'}]"
        query = input(f"  {mode} 你: ").strip()

        if not query:
            continue
        if query == "/exit":
            break
        if query == "/web":
            use_web = not use_web
            print(f"  联网模式: {'开' if use_web else '关'}\n")
            continue
        if query == "/rerank":
            use_rerank = not use_rerank
            print(f"  Rerank 精排: {'开' if use_rerank else '关'}\n")
            continue
        if query == "/rewrite":
            use_rewrite = not use_rewrite
            print(f"  查询重述: {'开' if use_rewrite else '关'}\n")
            continue

        try:
            print(f"\n  助手: ", end="", flush=True)
            answer = rag_query(query, session_id=session_id, use_web=use_web,
                               use_rerank=use_rerank, use_rewrite=use_rewrite)
            print()
        except Exception as e:
            print(f"\n  [ERROR] {e}\n")


def cmd_web_search():
    """联网搜索"""
    query = input("\n  搜索关键词: ").strip()
    if not query:
        return

    results = web_search(query, count=5)
    if not results:
        print("  无结果。\n")
        return

    print(f"\n  找到 {len(results)} 条结果:\n")
    for i, r in enumerate(results, 1):
        print(f"  [{i}] {r['title']}")
        print(f"      {r['url']}")
        print(f"      {r['content'][:120]}")
        print()


def cmd_history():
    """查看对话历史"""
    session_id = input("\n  输入会话 ID（留空查看最近会话）: ").strip()

    if not session_id:
        # 列出所有会话（从 Redis）
        sessions = list_sessions(limit=10)
        if not sessions:
            print("  暂无对话记录。\n")
            return
        print("\n  最近会话:")
        for s in sessions:
            print(f"    {s['session_id']}  (最后: {s['last_message_at']})")
        print()
        return

    msgs = get_history(session_id, turns=20)
    if not msgs:
        print("  该会话无记录。\n")
        return

    print(f"\n  会话 {session_id} 的历史:\n")
    for msg in msgs:
        role = "你" if msg["role"] == "user" else "助手"
        content = msg["content"]
        if len(content) > 200:
            content = content[:200] + "..."
        print(f"  [{role}] {content}")
    print()


def cmd_clear_index():
    """清空索引"""
    confirm = input("\n  确定清空所有索引？(y/n): ").strip().lower()
    if confirm == "y":
        clear_index()
        ensure_index()
        print("  索引已清空。\n")
    else:
        print("  已取消。\n")


def cmd_list_files():
    """查看知识库文件"""
    files = scan_knowledge_base(KNOWLEDGE_BASE_DIR)
    print(f"\n  知识库目录: {KNOWLEDGE_BASE_DIR}")
    if not files:
        print("  (空)\n")
        return
    for i, f in enumerate(files, 1):
        name = os.path.basename(f)
        size = os.path.getsize(f)
        print(f"    [{i}] {name} ({size // 1024} KB)")
    print()


def cmd_list_uploads():
    """查看已上传文件"""
    if not os.path.isdir(UPLOAD_DIR):
        print(f"\n  上传目录: {UPLOAD_DIR}")
        print("  (空)\n")
        return
    files = []
    for name in sorted(os.listdir(UPLOAD_DIR)):
        fpath = os.path.join(UPLOAD_DIR, name)
        if os.path.isfile(fpath):
            files.append((name, os.path.getsize(fpath)))
    print(f"\n  上传目录: {UPLOAD_DIR}")
    if not files:
        print("  (空)\n")
        return
    for i, (name, size) in enumerate(files, 1):
        print(f"    [{i}] {name} ({size // 1024} KB)")
    print()


def main():
    print_banner()

    # 初始化
    ensure_index()
    init_db()

    # 自动索引知识库
    kb_files = scan_knowledge_base(KNOWLEDGE_BASE_DIR)
    if kb_files:
        print(f"  发现知识库文件夹中有 {len(kb_files)} 个文件")
        auto = input("  是否自动索引？(y/n): ").strip().lower()
        if auto == "y":
            print()
            for f in kb_files:
                name = os.path.basename(f)
                try:
                    text = parse_document(f)
                    chunks = split_text(text)
                    n = add_documents(chunks, source=name)
                    print(f"  [OK] {name}: {len(chunks)} chunks, {n} indexed")
                except Exception as e:
                    print(f"  [FAIL] {name}: {e}")
            print()

    while True:
        print_menu()
        choice = input("  请选择: ").strip()

        if choice == "1":
            cmd_index_knowledge_base()
        elif choice == "2":
            cmd_upload_file()
        elif choice == "3":
            cmd_chat()
        elif choice == "4":
            cmd_web_search()
        elif choice == "5":
            cmd_history()
        elif choice == "6":
            cmd_clear_index()
        elif choice == "7":
            cmd_list_files()
        elif choice == "8":
            cmd_list_uploads()
        elif choice == "0":
            print("\n  再见！\n")
            break
        else:
            print("  无效选择，请重新输入。\n")


if __name__ == "__main__":
    main()
