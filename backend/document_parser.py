"""文档解析模块：MinerU API 统一转 MD + 本地兜底"""

import os
import json
import re
import requests
from config import MINERU_HOST, SUPPORTED_EXTENSIONS

# 图片格式
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".tif"}

# MIME 类型映射
MIME_MAP = {
    ".pdf": "application/pdf",
    ".doc": "application/msword",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".ppt": "application/vnd.ms-powerpoint",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ".xls": "application/vnd.ms-excel",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".md": "text/markdown",
    ".txt": "text/plain",
    ".html": "text/html",
    ".htm": "text/html",
    ".epub": "application/epub+zip",
    ".mobi": "application/x-mobipocket-ebook",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".bmp": "image/bmp",
    ".tiff": "image/tiff",
    ".tif": "image/tiff",
}


def parse_with_mineru(file_path: str) -> str:
    """通过 MinerU API 将任意格式文件转为 Markdown"""
    ext = os.path.splitext(file_path)[1].lower()
    mime = MIME_MAP.get(ext, "application/octet-stream")
    url = f"{MINERU_HOST}/file_parse"

    with open(file_path, "rb") as f:
        files = {"files": (os.path.basename(file_path), f, mime)}
        data = {
            "parse_method": "auto",
            "return_md": "true",
            "return_middle_json": "false",
            "return_model_output": "false",
            "return_content_list": "false",
            "return_images": "false",
        }
        resp = requests.post(url, files=files, data=data, timeout=300)
    resp.raise_for_status()
    result = resp.json()

    # MinerU API 返回结构: {"results": {"filename": {"md_content": "..."}}}
    results = result.get("results", {})
    if isinstance(results, dict):
        for key, item in results.items():
            if isinstance(item, dict):
                if "md_content" in item:
                    return item["md_content"]
                if "markdown" in item:
                    return item["markdown"]

    # 兼容其他返回格式
    if "md_content" in result:
        return result["md_content"]
    if "markdown" in result:
        return result["markdown"]
    if "content" in result:
        return result["content"]
    return str(result)


def parse_local(file_path: str) -> str:
    """本地直接读取（md/txt）"""
    ext = os.path.splitext(file_path)[1].lower()
    if ext in (".md", ".txt", ".html", ".htm"):
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()
    raise ValueError(f"无法本地解析: {ext}")


def _extract_text_from_binary(file_path: str) -> str:
    """从二进制文件中提取可读文本（通用兜底）"""
    with open(file_path, "rb") as f:
        raw = f.read()
    text = raw.decode("utf-8", errors="ignore")
    cleaned = re.sub(r'[^\x20-\x7e一-鿿　-〿＀-￯\n\r\t]', ' ', text)
    cleaned = re.sub(r'\s{3,}', '\n\n', cleaned)
    return cleaned.strip()


def parse_document(file_path: str) -> str:
    """
    解析文档。
    - md/txt 直接读取
    - 图片文件使用 OCR 识别
    - 其他格式（PDF/Word/PPT/Excel等）通过 MinerU API 统一转 MD
    - MinerU 不可用时：PDF→PyPDF2, DOCX→python-docx, 其他→提取可读文本
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"文件不存在: {file_path}")

    ext = os.path.splitext(file_path)[1].lower()

    if ext not in SUPPORTED_EXTENSIONS:
        raise ValueError(f"不支持的文件格式: {ext}，支持: {sorted(SUPPORTED_EXTENSIONS)}")

    # 纯文本类直接读取
    if ext in (".md", ".txt", ".html", ".htm"):
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()

    # 图片文件使用 OCR
    if ext in IMAGE_EXTENSIONS:
        print(f"[OCR] 正在解析图片: {os.path.basename(file_path)} ...")
        try:
            from image_parser import parse_image_with_description
            result = parse_image_with_description(file_path)
            print(f"[OCR] 图片解析完成，长度: {len(result)}")
            return result
        except Exception as e:
            print(f"[OCR] 图片解析失败: {e}")
            # OCR 失败，尝试通用文本提取
            fallback = _extract_text_from_binary(file_path)
            if fallback:
                return fallback
            raise RuntimeError(f"图片解析失败: {e}")

    # 其他格式优先走 MinerU API
    print(f"[MinerU] 正在解析 {os.path.basename(file_path)} ...")
    try:
        md = parse_with_mineru(file_path)
        print(f"[MinerU] 解析成功，长度: {len(md)}")
        return md
    except Exception as e:
        print(f"[MinerU] 解析失败: {e}")

    # ---- 兜底策略 ----

    # PDF 兜底：PyPDF2
    if ext == ".pdf":
        try:
            from PyPDF2 import PdfReader
            reader = PdfReader(file_path)
            texts = []
            for page in reader.pages:
                text = page.extract_text()
                if text:
                    texts.append(text)
            result = "\n\n".join(texts)
            if result.strip():
                print(f"[PyPDF2] 兜底解析成功，长度: {len(result)}")
                return result
        except Exception as e2:
            print(f"[PyPDF2] 兜底失败: {e2}")

    # DOCX/DOC 兜底：python-docx
    if ext in (".doc", ".docx"):
        try:
            from docx import Document
            doc = Document(file_path)
            texts = [p.text for p in doc.paragraphs if p.text.strip()]
            result = "\n\n".join(texts)
            if result.strip():
                print(f"[python-docx] 兜底解析成功，长度: {len(result)}")
                return result
        except Exception as e2:
            print(f"[python-docx] 兜底失败: {e2}")

    # 通用兜底：从二进制提取可读文本
    fallback = _extract_text_from_binary(file_path)
    if len(fallback) > 50:
        print(f"[RawText] 兜底解析成功，长度: {len(fallback)}")
        return fallback

    raise RuntimeError(f"所有解析方式均失败，无法解析 {ext} 格式文件")


def scan_knowledge_base(kb_dir: str) -> list[str]:
    """扫描知识库文件夹，返回所有支持的文件路径"""
    files = []
    if not os.path.isdir(kb_dir):
        return files
    for name in sorted(os.listdir(kb_dir)):
        ext = os.path.splitext(name)[1].lower()
        if ext in SUPPORTED_EXTENSIONS:
            files.append(os.path.join(kb_dir, name))
    return files
