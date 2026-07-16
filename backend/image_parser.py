"""图片解析模块：使用 OCR 从图片中提取文字"""

import os

# 支持的图片格式
SUPPORTED_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".tif"}


def _check_tesseract_available() -> bool:
    """检查 tesseract 是否可用"""
    try:
        import pytesseract
        pytesseract.get_tesseract_version()
        return True
    except Exception:
        return False


def parse_image(file_path: str) -> str:
    """
    从图片中提取文字（OCR）。
    支持格式：PNG, JPG, JPEG, BMP, TIFF
    使用 pytesseract 进行 OCR，支持中文和英文。
    如果 tesseract 不可用，返回提示信息。
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"文件不存在: {file_path}")

    ext = os.path.splitext(file_path)[1].lower()
    if ext not in SUPPORTED_IMAGE_EXTENSIONS:
        raise ValueError(f"不支持的图片格式: {ext}，支持: {sorted(SUPPORTED_IMAGE_EXTENSIONS)}")

    # 尝试使用 pytesseract 进行 OCR
    try:
        import pytesseract
        from PIL import Image

        # 打开图片
        img = Image.open(file_path)

        # 使用中英文混合 OCR
        # chi_sim = 简体中文, eng = 英文
        ocr_text = pytesseract.image_to_string(img, lang="chi_sim+eng")

        # 清理结果：去除多余空行
        lines = [line.strip() for line in ocr_text.splitlines() if line.strip()]
        result = "\n".join(lines)

        if result:
            print(f"[OCR] 识别成功，文本长度: {len(result)}")
            return result
        else:
            print("[OCR] 未识别到文字内容")
            return "[图片中未检测到文字内容]"

    except ImportError as e:
        print(f"[OCR] 依赖缺失: {e}")
        return (
            "[OCR 不可用] 需要安装 pytesseract 和 Pillow 库。"
            "请运行: pip install pytesseract Pillow，"
            "并安装 Tesseract-OCR 引擎 (https://github.com/tesseract-ocr/tesseract)。"
        )
    except Exception as e:
        print(f"[OCR] 识别失败: {e}")
        return f"[OCR 识别失败] {str(e)}"


def parse_image_with_description(file_path: str) -> str:
    """
    从图片中提取文字，并附带图片描述占位符。
    返回 OCR 文本 + 非文字内容的描述信息。
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"文件不存在: {file_path}")

    ext = os.path.splitext(file_path)[1].lower()
    filename = os.path.basename(file_path)

    # 获取 OCR 文本
    ocr_text = parse_image(file_path)

    # 构建描述信息
    parts = []
    parts.append(f"[图片文件: {filename}]")

    # 尝试获取图片基本信息
    try:
        from PIL import Image
        img = Image.open(file_path)
        width, height = img.size
        mode = img.mode
        parts.append(f"[图片尺寸: {width}x{height}, 模式: {mode}]")
    except Exception:
        pass

    # 添加 OCR 结果
    if ocr_text and not ocr_text.startswith("["):
        parts.append("[OCR 识别内容]:")
        parts.append(ocr_text)
    else:
        parts.append(ocr_text)

    # 添加非文字内容描述占位符
    parts.append("")
    parts.append("[注: 图片中可能包含图表、图形等非文字内容，需要视觉模型进一步分析。]")

    return "\n".join(parts)
