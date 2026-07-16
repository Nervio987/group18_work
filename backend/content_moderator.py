"""
文档内容合规审核模块

三级审核机制：
  - PASS（绿灯）：内容安全，直接通过
  - REVIEW（黄灯）：内容存疑，需要人工审核
  - BLOCK（红灯）：内容违规，自动拒绝并删除

审核维度：
  1. 政治敏感（涉政言论、不当政治内容）
  2. 色情低俗（色情、低俗内容）
  3. 暴力恐怖（暴力、恐怖主义内容）
  4. 违法违规（违反法律法规的内容）
  5. 商业机密（可能泄露商业机密的内容）
  6. 个人隐私（包含个人敏感信息的内容）
  7. 虚假信息（明显的虚假/误导性内容）
"""

import json
import re
import os
from datetime import datetime
from typing import Optional

# ========== 关键词黑名单（快速初筛） ==========

# 高危关键词 — 直接 BLOCK
BLOCK_KEYWORDS = [
    # 政治敏感
    "推翻政府", "颠覆政权", "分裂国家", "恐怖主义", "暴乱",
    # 色情
    "色情", "淫秽", "幼女", "儿童色情",
    # 暴力
    "制造炸弹", "制造毒品", "杀人教程", "自杀方法",
    # 违法
    "洗钱", "贩毒", "走私", "诈骗教程",
    # 脏话/辱骂
    "傻逼", "煞笔", "操你妈", "草你妈", "日你妈",
    "他妈的", "去死吧", "狗东西", "畜生", "王八蛋",
    "杂种", "贱人", "婊子", "妈逼", "尼玛的",
    "滚你妈", "cnm", "nmsl", "wcnm","傻福",
    "fuck you", "fuck off", "shit", "bitch", "asshole",
]

# 敏感关键词 — 触发 REVIEW
REVIEW_KEYWORDS = [
    # 商业机密
    "机密", "保密", "内部资料", "不得外传", "商业秘密", "核心技术",
    "源代码", "数据库密码", "API密钥", "私钥",
    # 个人隐私
    "身份证号", "银行卡号", "密码是", "手机号", "家庭住址",
    "社保号", "护照号",
    # 敏感话题
    "裁员", "罢工", "投诉", "举报", "诉讼", "仲裁",
    "性骚扰", "歧视", "贪污", "腐败",
    # 不确定内容
    "仅供参考", "非官方", "传闻", "据说",
]


def keyword_scan(text: str) -> dict:
    """关键词快速扫描"""
    text_lower = text.lower()

    hit_block = [kw for kw in BLOCK_KEYWORDS if kw in text_lower]
    hit_review = [kw for kw in REVIEW_KEYWORDS if kw in text_lower]

    if hit_block:
        return {
            "verdict": "BLOCK",
            "confidence": 0.95,
            "reasons": [f"命中高危关键词: {', '.join(hit_block)}"],
            "categories": ["keyword_block"],
        }

    if hit_review:
        return {
            "verdict": "REVIEW",
            "confidence": 0.6,
            "reasons": [f"命中敏感关键词: {', '.join(hit_review)}"],
            "categories": ["keyword_review"],
        }

    return {
        "verdict": "PASS",
        "confidence": 0.8,
        "reasons": ["关键词扫描未发现问题"],
        "categories": [],
    }


def llm_moderate(text: str, filename: str = "") -> dict:
    """
    使用 LLM 进行深度内容审核。
    返回: {verdict, confidence, reasons, categories}
    """
    from llm_client import chat_completion

    system_prompt = """你是一个专业的企业文档内容审核员。请对上传的文档内容进行合规性审核。

审核维度：
1. 政治敏感 — 涉政不当言论、分裂国家、颠覆政权等
2. 色情低俗 — 色情、淫秽、低俗内容
3. 暴力恐怖 — 暴力、恐怖主义、危险行为教程
4. 违法违规 — 违反中国法律法规的内容
5. 商业机密 — 可能泄露企业商业机密的内容（源代码、密码、核心技术等）
6. 个人隐私 — 包含个人敏感信息（身份证号、银行卡号、密码等）
7. 虚假信息 — 明显的虚假或误导性内容

请严格按照以下 JSON 格式返回结果（不要返回其他内容）：
{
  "verdict": "PASS" | "REVIEW" | "BLOCK",
  "confidence": 0.0-1.0,
  "categories": ["政治敏感", "色情低俗", "暴力恐怖", "违法违规", "商业机密", "个人隐私", "虚假信息"],
  "reasons": ["具体原因1", "具体原因2"],
  "summary": "文档内容一句话摘要"
}

判定标准：
- PASS：内容完全合规，无任何风险
- REVIEW：内容存在一定风险或不确定性，需要人工确认（如包含内部资料标记、敏感话题讨论等）
- BLOCK：内容明显违规，必须拒绝（如违法内容、色情暴力、泄露核心机密等）"""

    # 截取前 3000 字符进行审核（避免 token 过多）
    sample = text[:3000]
    user_prompt = f"请审核以下文档内容（文件名：{filename}）：\n\n{sample}"

    try:
        response = chat_completion(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.1,  # 低温度，确保审核结果稳定
            max_tokens=500,
        )

        content = response.get("content", "") if isinstance(response, dict) else str(response)

        # 尝试解析 JSON
        # 去除可能的 markdown 代码块标记
        content = content.strip()
        if content.startswith("```"):
            content = re.sub(r'^```(?:json)?\s*', '', content)
            content = re.sub(r'\s*```$', '', content)
            content = content.strip()

        result = json.loads(content)

        # 验证返回格式
        if result.get("verdict") not in ("PASS", "REVIEW", "BLOCK"):
            result["verdict"] = "REVIEW"
            result["reasons"] = result.get("reasons", []) + ["LLM 返回格式异常，降级为人工审核"]

        return result

    except json.JSONDecodeError:
        return {
            "verdict": "REVIEW",
            "confidence": 0.5,
            "categories": [],
            "reasons": ["LLM 返回非 JSON 格式，需要人工审核"],
            "summary": "",
        }
    except Exception as e:
        print(f"[ContentModerator] LLM 审核失败: {e}")
        return {
            "verdict": "REVIEW",
            "confidence": 0.5,
            "categories": [],
            "reasons": [f"LLM 审核服务异常: {str(e)[:100]}，需要人工审核"],
            "summary": "",
        }


def moderate_document(text: str, filename: str = "") -> dict:
    """
    完整的文档审核流程：关键词扫描 → LLM 深度审核 → 综合判定

    返回:
    {
        "verdict": "PASS" | "REVIEW" | "BLOCK",
        "confidence": 0.0-1.0,
        "categories": [...],
        "reasons": [...],
        "summary": "...",
        "keyword_result": {...},
        "llm_result": {...},
    }
    """
    if not text or not text.strip():
        return {
            "verdict": "BLOCK",
            "confidence": 1.0,
            "categories": ["空内容"],
            "reasons": ["文档内容为空"],
            "summary": "",
        }

    # 第一层：关键词快速扫描
    kw_result = keyword_scan(text)

    # 如果关键词已经判定 BLOCK，直接返回（高危内容无需 LLM 二次确认）
    if kw_result["verdict"] == "BLOCK":
        return {
            **kw_result,
            "summary": "",
            "keyword_result": kw_result,
            "llm_result": None,
        }

    # 第二层：LLM 深度审核
    llm_result = llm_moderate(text, filename)

    # 综合判定逻辑
    # BLOCK 优先级最高：任一方判定 BLOCK → BLOCK
    if kw_result["verdict"] == "BLOCK" or llm_result.get("verdict") == "BLOCK":
        verdict = "BLOCK"
        confidence = max(kw_result.get("confidence", 0), llm_result.get("confidence", 0))
    # 任一方 REVIEW → REVIEW
    elif kw_result["verdict"] == "REVIEW" or llm_result.get("verdict") == "REVIEW":
        verdict = "REVIEW"
        confidence = min(kw_result.get("confidence", 0.6), llm_result.get("confidence", 0.7))
    else:
        verdict = "PASS"
        confidence = max(kw_result.get("confidence", 0.8), llm_result.get("confidence", 0.8))

    # 合并原因和分类
    reasons = kw_result.get("reasons", []) + llm_result.get("reasons", [])
    categories = list(set(kw_result.get("categories", []) + llm_result.get("categories", [])))

    return {
        "verdict": verdict,
        "confidence": round(confidence, 2),
        "categories": categories,
        "reasons": reasons,
        "summary": llm_result.get("summary", ""),
        "keyword_result": kw_result,
        "llm_result": llm_result,
    }


# ========== 对话内容审核（轻量级，仅关键词） ==========

def moderate_chat_query(text: str) -> dict:
    """
    对用户聊天提问做快速关键词审核。
    不做 LLM 审核（避免每条消息都调 LLM 增加延迟）。
    只检查高危关键词，命中即 BLOCK。
    """
    if not text or not text.strip():
        return {"verdict": "BLOCK", "reasons": ["空内容"]}

    text_lower = text.lower()
    hit_block = [kw for kw in BLOCK_KEYWORDS if kw in text_lower]

    if hit_block:
        return {
            "verdict": "BLOCK",
            "reasons": [f"包含违规内容: {', '.join(hit_block)}"],
        }

    return {"verdict": "PASS"}


def moderate_chat_answer(text: str) -> dict:
    """
    对 AI 回答做快速关键词审核。
    检查是否包含不应输出的内容。
    """
    if not text or not text.strip():
        return {"verdict": "PASS"}

    text_lower = text.lower()
    hit_block = [kw for kw in BLOCK_KEYWORDS if kw in text_lower]

    if hit_block:
        return {
            "verdict": "BLOCK",
            "reasons": [f"AI 回答包含违规内容: {', '.join(hit_block)}"],
        }

    return {"verdict": "PASS"}


# ========== 审核记录持久化 ==========

def save_audit_record(
    document_id: Optional[int],
    filename: str,
    knowledge_base_id: Optional[int],
    user_id: int,
    result: dict,
    db_session=None,
) -> Optional[int]:
    """保存审核记录到数据库，返回记录 ID"""
    try:
        from app.database import SessionLocal
        from app import models

        session = db_session or SessionLocal()
        should_close = db_session is None

        record = models.ContentAuditLog(
            document_id=document_id,
            filename=filename,
            knowledge_base_id=knowledge_base_id,
            user_id=user_id,
            verdict=result.get("verdict", "REVIEW"),
            confidence=result.get("confidence", 0.5),
            categories=json.dumps(result.get("categories", []), ensure_ascii=False),
            reasons=json.dumps(result.get("reasons", []), ensure_ascii=False),
            summary=result.get("summary", ""),
            raw_result=json.dumps(result, ensure_ascii=False),
            status="pending" if result.get("verdict") == "REVIEW" else "auto_processed",
        )
        session.add(record)
        session.commit()
        session.refresh(record)
        audit_id = record.id

        if should_close:
            session.close()

        return audit_id

    except Exception as e:
        print(f"[ContentModerator] 保存审核记录失败: {e}")
        return None
