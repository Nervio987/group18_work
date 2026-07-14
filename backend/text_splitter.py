"""文本切片模块：带 overlap 的滑动窗口切片"""

import re
from config import CHUNK_SIZE, CHUNK_OVERLAP


def split_text(text: str, chunk_size: int = CHUNK_SIZE, chunk_overlap: int = CHUNK_OVERLAP) -> list[str]:
    """
    智能文本切片，防止语义截断。

    策略：
    1. 先按段落（\n\n）分段，短段落合并
    2. 超长段落按句子切分
    3. 滑动窗口：相邻 chunk 之间有 chunk_overlap 字符重叠
    """
    # 先按双换行分段
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    if not paragraphs:
        return []

    # 第一阶段：合并短段落为粗块
    raw_chunks = []
    current = ""
    for para in paragraphs:
        if len(current) + len(para) + 2 <= chunk_size:
            current = current + "\n\n" + para if current else para
        else:
            if current:
                raw_chunks.append(current)
            current = para
    if current:
        raw_chunks.append(current)

    # 第二阶段：对超长块按句子切分
    fine_chunks = []
    for chunk in raw_chunks:
        if len(chunk) <= chunk_size:
            fine_chunks.append(chunk)
        else:
            fine_chunks.extend(_split_by_sentences(chunk, chunk_size))

    # 第三阶段：滑动窗口 overlap
    if chunk_overlap <= 0 or len(fine_chunks) <= 1:
        return fine_chunks

    result = [fine_chunks[0]]
    for i in range(1, len(fine_chunks)):
        prev = fine_chunks[i - 1]
        curr = fine_chunks[i]
        # 取前一个 chunk 的尾部 chunk_overlap 个字符作为重叠
        overlap = prev[-chunk_overlap:] if len(prev) > chunk_overlap else prev
        # 避免 overlap 和 curr 开头重复
        if curr.startswith(overlap[-30:]):
            overlap = overlap[:-30]
        combined = (overlap + "\n" + curr).strip()
        result.append(combined)

    return result


def _split_by_sentences(text: str, max_len: int) -> list[str]:
    """按句子切分超长段落"""
    parts = re.split(r'([。！？\.\!\?\n]+)', text)
    sentences = []
    buf = ""
    for part in parts:
        buf += part
        if len(buf) >= max_len:
            sentences.append(buf.strip())
            buf = ""
    if buf.strip():
        sentences.append(buf.strip())
    return sentences
