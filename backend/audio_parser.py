"""音频解析模块：语音转文字（预留 Whisper 集成接口）"""

import os

# 支持的音频格式
SUPPORTED_AUDIO_EXTENSIONS = {".mp3", ".wav", ".flac", ".ogg", ".m4a", ".aac", ".wma"}


def parse_audio(file_path: str) -> str:
    """
    音频转文字（占位实现）。
    当前返回提示信息，表示需要 Whisper 模型支持。
    未来可集成 OpenAI Whisper 进行本地语音转文字。
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"文件不存在: {file_path}")

    ext = os.path.splitext(file_path)[1].lower()
    if ext not in SUPPORTED_AUDIO_EXTENSIONS:
        raise ValueError(f"不支持的音频格式: {ext}，支持: {sorted(SUPPORTED_AUDIO_EXTENSIONS)}")

    filename = os.path.basename(file_path)
    file_size_mb = os.path.getsize(file_path) / (1024 * 1024)

    return (
        f"[音频文件: {filename}]\n"
        f"[文件大小: {file_size_mb:.2f} MB]\n"
        f"[格式: {ext}]\n\n"
        "[音频处理需要 Whisper 模型支持]\n"
        "当前音频转文字功能尚未启用。\n"
        "如需启用，请安装 OpenAI Whisper:\n"
        "  pip install openai-whisper\n"
        "并在代码中集成 whisper 模型进行本地语音识别。\n\n"
        "集成示例:\n"
        "  import whisper\n"
        "  model = whisper.load_model('base')\n"
        "  result = model.transcribe(file_path)\n"
        "  text = result['text']\n"
    )


def parse_audio_with_whisper(file_path: str, model_name: str = "base") -> str:
    """
    使用 Whisper 模型进行音频转文字。
    需要安装: pip install openai-whisper

    参数:
        file_path: 音频文件路径
        model_name: Whisper 模型名称 (tiny, base, small, medium, large)

    返回:
        转录的文本内容
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"文件不存在: {file_path}")

    try:
        import whisper

        print(f"[Whisper] 正在加载模型: {model_name} ...")
        model = whisper.load_model(model_name)

        print(f"[Whisper] 正在转录: {os.path.basename(file_path)} ...")
        result = model.transcribe(file_path, language="zh")

        text = result.get("text", "")
        print(f"[Whisper] 转录完成，文本长度: {len(text)}")
        return text

    except ImportError:
        raise RuntimeError(
            "Whisper 未安装。请运行: pip install openai-whisper"
        )
    except Exception as e:
        raise RuntimeError(f"Whisper 转录失败: {e}")
