"""LangGraph 高级智能体编排（增强版）

增强特性：
1. 模块隔离：根据当前模块（policy/tech/admin/general）限定知识库搜索范围
2. 反思节点：生成答案后自我评估质量，不满意则重新检索
3. 并行工具调用：一轮可同时调用多个工具（知识库搜索 + 联网搜索 + 日期查询等）
4. 更丰富的图结构：analyze → [并行工具] → generate → reflect → [循环/结束]
"""

from typing import Dict, List, Any, TypedDict, Optional
from langgraph.graph import StateGraph, END
from config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, LLM_MODEL, TOP_K
from agent_tools import execute_tool, TOOLS
from llm_client import _safe_request
from opensearch_store import search as vector_search
import json


# ── 模块描述映射 ──────────────────────────────────────────────────────────

MODULE_DESCRIPTIONS = {
    "policy": "规章制度",
    "tech": "产品技术",
    "admin": "行政服务",
    "general": "自由问答",
}

MODULE_SYSTEM_PROMPTS = {
    "policy": """你是一个企业规章制度助手，专注于回答与企业规章制度、流程规范、管理制度相关的问题。
你的职责范围：报销流程、请假制度、考勤规定、差旅标准、加班申请、合同管理、奖惩条例、晋升通道、培训制度等。
如果用户的问题不属于规章制度范畴（如天气、闲聊、技术问题等），请礼貌地说明这超出了你的职责范围，并建议用户切换到"自由问答"模块。
请优先使用本地知识库的参考资料回答，回答时请引用来源。""",
    "tech": """你是一个产品技术助手，专注于回答与技术文档、产品手册、API说明、开发规范相关的问题。
你的职责范围：系统架构、API接口、数据库设计、部署运维、安全规范、性能优化、故障排查、CI/CD、微服务等。
如果用户的问题不属于技术范畴（如天气、闲聊、行政制度等），请礼貌地说明这超出了你的职责范围，并建议用户切换到对应模块。
请优先使用本地知识库的参考资料回答，回答时请引用来源。""",
    "admin": """你是一个行政服务助手，专注于回答与办公场地、IT支持、福利政策、行政事务相关的问题。
你的职责范围：办公场地申请、IT设备报修、员工福利、会议室预定、办公用品领取、考勤管理、差旅报销、员工入离职等。
如果用户的问题不属于行政服务范畴（如天气、闲聊、技术架构等），请礼貌地说明这超出了你的职责范围，并建议用户切换到对应模块。
请优先使用本地知识库的参考资料回答，回答时请引用来源。""",
    "general": """你是一个智能助手，基于检索到的信息回答问题。
请优先使用本地知识库的参考资料回答，如果本地资料不足以回答，可以结合联网搜索结果补充。
回答时请引用来源。如果参考资料中没有相关信息，请明确说明。""",
}


# ── 状态定义 ──────────────────────────────────────────────────────────────

class AgentState(TypedDict):
    """智能体状态"""
    messages: List[Dict[str, str]]
    module: str                          # 当前模块 (policy/tech/admin/general)
    knowledge_base_ids: Optional[List[int]]  # 限定的知识库 ID
    next_action: str                     # 下一步动作
    tool_calls: List[Dict[str, Any]]     # 待执行的工具调用列表
    tool_results: List[Dict[str, Any]]   # 工具执行结果
    final_answer: str                    # 最终回答
    iteration: int                       # 当前迭代次数
    reflection_passed: bool              # 反思是否通过
    reflection_reason: str               # 反思原因（未通过时）
    stream_callback: Any                 # 可选的流式回调函数


# ── 图路由 ────────────────────────────────────────────────────────────────

def should_continue(state: AgentState) -> str:
    """决定下一步动作"""
    if state["iteration"] >= 8:  # 最大迭代次数（增强版允许更多轮）
        return "generate_final"

    if state["next_action"] == "use_tool":
        return "execute_tools"
    elif state["next_action"] == "answer":
        return "generate_answer"
    elif state["next_action"] == "reflect":
        return "reflect_answer"
    elif state["next_action"] == "retry":
        return "analyze"  # 反思不通过，重新分析
    else:
        return "generate_final"


def after_reflect(state: AgentState) -> str:
    """反思后的路由"""
    if state.get("reflection_passed", True):
        return "generate_final"
    else:
        # 反思不通过，但迭代次数有限
        if state["iteration"] >= 8:
            return "generate_final"
        return "analyze"


# ─ 节点：分析查询 ────────────────────────────────────────────────────────

def analyze_query(state: AgentState) -> AgentState:
    """分析用户查询，决定是否需要使用工具（支持并行多工具决策）"""
    messages = state["messages"]
    query = messages[-1]["content"] if messages else ""
    module = state.get("module", "general")
    module_name = MODULE_DESCRIPTIONS.get(module, "通用")

    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json",
    }

    # 构建模块感知的工具列表
    available_tools = """
1. search_knowledge_base - 搜索本地知识库（参数: query, top_k）
   - 非自由问答模块（规章制度/产品技术/行政服务）必须使用此工具搜索对应模块知识
   - 自由问答模块可同时搜索多个知识库
2. web_search - 搜索互联网（参数: query, count）
   - 当知识库信息不足时使用
   - 非自由问答模块仅在知识库无结果时才使用
3. calculate - 数学计算（参数: expression）
4. get_current_date - 获取当前系统日期时间（无参数）
   - 涉及"今天"、"现在"、"最新"、"当前"、"近期"等时间相关问题时必须先调用
5. get_system_info - 获取系统信息（无参数）
6. create_document - 生成 Word/PDF 文档（参数: content, format, title）
   - 当用户要求导出/下载/生成文档时使用"""

    system_prompt = f"""你是一个智能任务分析器。当前模块：{module_name}。分析用户的问题，决定需要使用哪些工具。

可用工具：{available_tools}

重要规则：
- 涉及"今天"、"现在"、"最新"、"当前"、"近期"等时间相关问题时，必须先调用 get_current_date 获取真实日期
- 再用真实日期生成查询词（如 "2026年7月12日 新闻"），避免编造日期
- 非自由问答模块的问题，优先使用 search_knowledge_base 搜索对应模块的知识库
- 可以同时使用多个工具（如同时搜索知识库和获取日期）
- 如果问题不属于当前模块职责范围，请在回答中说明

返回 JSON 格式：
{{
  "need_tools": true/false,
  "tools": [
    {{"tool": "工具名", "args": {{参数}}}},
    ...
  ],
  "can_answer_directly": true/false
}}

如果可以直接回答（不需要任何工具），返回：
{{"need_tools": false, "tools": [], "can_answer_directly": true}}

只返回 JSON，不要其他内容。"""

    response = _safe_request(
        "POST",
        f"{DEEPSEEK_BASE_URL}/v1/chat/completions",
        max_retries=3,
        headers=headers,
        json={
            "model": LLM_MODEL,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": query}
            ],
            "temperature": 0.1
        },
        timeout=30
    )

    try:
        result = response.json()
        content = result["choices"][0]["message"]["content"]
        decision = json.loads(content)

        if decision.get("need_tools") and decision.get("tools"):
            state["next_action"] = "use_tool"
            state["tool_calls"] = decision["tools"]
        else:
            state["next_action"] = "answer"
            state["tool_calls"] = []
    except Exception:
        # 解析失败时，默认使用知识库搜索
        state["next_action"] = "use_tool"
        state["tool_calls"] = [{"tool": "search_knowledge_base", "args": {"query": query, "top_k": TOP_K}}]

    state["iteration"] += 1
    return state


# ── 节点：执行工具（支持并行） ────────────────────────────────────────────

def execute_tools_node(state: AgentState) -> AgentState:
    """并行执行多个工具调用"""
    tool_calls = state.get("tool_calls", [])
    tool_results = []
    module = state.get("module", "general")

    for tool_call in tool_calls:
        tool_name = tool_call.get("tool", "")
        tool_args = tool_call.get("args", {})

        print(f"[LangGraph] 执行工具: {tool_name}, 参数: {tool_args}")

        # 特殊处理：知识库搜索需要传入模块信息
        if tool_name == "search_knowledge_base":
            result = _search_knowledge_base(
                query=tool_args.get("query", ""),
                top_k=tool_args.get("top_k", TOP_K),
                knowledge_base_ids=state.get("knowledge_base_ids"),
            )
        else:
            result = execute_tool(tool_name, tool_args)

        tool_results.append({
            "tool": tool_name,
            "result": result
        })

    state["tool_results"] = tool_results
    state["next_action"] = "answer"
    return state


def _search_knowledge_base(query: str, top_k: int = TOP_K, knowledge_base_ids: list = None) -> dict:
    """搜索本地知识库（带模块隔离）"""
    try:
        results = vector_search(query, top_k=top_k, knowledge_base_ids=knowledge_base_ids)
        if results:
            return {
                "success": True,
                "data": {
                    "results": results,
                    "count": len(results),
                    "knowledge_base_ids": knowledge_base_ids,
                }
            }
        return {
            "success": True,
            "data": {
                "results": [],
                "count": 0,
                "message": "知识库中未找到相关信息",
            }
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


# ── 节点：生成答案 ────────────────────────────────────────────────────────

def generate_answer(state: AgentState) -> AgentState:
    """基于工具结果生成答案（带模块感知 prompt）"""
    messages = state["messages"]
    tool_results = state.get("tool_results", [])
    stream_callback = state.get("stream_callback")
    module = state.get("module", "general")

    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json",
    }

    # 获取模块对应的系统 prompt
    system_prompt = MODULE_SYSTEM_PROMPTS.get(module, MODULE_SYSTEM_PROMPTS["general"])

    # 构建包含工具结果的上下文
    context_parts = []
    for tr in tool_results:
        tool_name = tr.get("tool", "unknown")
        result = tr.get("result", {})
        if result.get("success"):
            data = result.get("data", {})
            # 知识库搜索结果格式化
            if tool_name == "search_knowledge_base" and isinstance(data, dict) and "results" in data:
                for i, r in enumerate(data["results"], 1):
                    content = r.get("content", "")[:2000]
                    source = r.get("source", "")
                    context_parts.append(f"[知识库 {i}] (来源: {source}) {content}")
            else:
                context_parts.append(f"[工具 {tool_name}] 返回结果: {json.dumps(data, ensure_ascii=False)}")
        else:
            context_parts.append(f"[工具 {tool_name}] 执行失败: {result.get('error', '未知错误')}")

    query = messages[-1]["content"] if messages else ""
    user_content = query
    if context_parts:
        user_content += "\n\n参考资料：\n" + "\n\n".join(context_parts)

    if stream_callback:
        # 流式模式
        response = _safe_request(
            "POST",
            f"{DEEPSEEK_BASE_URL}/v1/chat/completions",
            max_retries=3,
            headers=headers,
            json={
                "model": LLM_MODEL,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content}
                ],
                "temperature": 0.7,
                "stream": True
            },
            stream=True,
            timeout=60
        )
        response.raise_for_status()

        answer = ""
        for line in response.iter_lines():
            if line:
                line_str = line.decode("utf-8")
                if line_str.startswith("data: "):
                    data_str = line_str[6:]
                    if data_str.strip() == "[DONE]":
                        break
                    try:
                        data = json.loads(data_str)
                        delta = data["choices"][0].get("delta", {})
                        reasoning = delta.get("reasoning_content", "")
                        content = delta.get("content", "")
                        if reasoning:
                            stream_callback("reasoning", reasoning)
                        if content:
                            answer += content
                            stream_callback("content", content)
                    except json.JSONDecodeError:
                        continue
    else:
        # 非流式模式
        response = _safe_request(
            "POST",
            f"{DEEPSEEK_BASE_URL}/v1/chat/completions",
            max_retries=3,
            headers=headers,
            json={
                "model": LLM_MODEL,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content}
                ],
                "temperature": 0.7
            },
            timeout=60
        )

        result = response.json()
        answer = result["choices"][0]["message"]["content"]

    state["final_answer"] = answer
    state["next_action"] = "reflect"
    return state


# ── 节点：反思 ────────────────────────────────────────────────────────────

def reflect_answer(state: AgentState) -> AgentState:
    """自我评估答案质量，决定是否重新检索"""
    messages = state["messages"]
    answer = state.get("final_answer", "")
    tool_results = state.get("tool_results", [])
    module = state.get("module", "general")
    query = messages[-1]["content"] if messages else ""

    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json",
    }

    # 构建工具结果摘要
    tool_summary = ""
    for tr in tool_results:
        tool_name = tr.get("tool", "unknown")
        result = tr.get("result", {})
        if result.get("success"):
            data = result.get("data", {})
            if tool_name == "search_knowledge_base" and isinstance(data, dict):
                count = data.get("count", 0)
                tool_summary += f"- 知识库搜索: 找到 {count} 条相关结果\n"
            else:
                tool_summary += f"- {tool_name}: 成功返回结果\n"
        else:
            tool_summary += f"- {tool_name}: 失败 ({result.get('error', '')})\n"

    system_prompt = """你是一个答案质量评估器。评估 AI 助手给出的回答质量。

评估标准：
1. 回答是否直接回应了用户的问题
2. 回答是否有足够的信息支撑（不是空洞的套话）
3. 如果使用了知识库搜索，回答是否充分利用了检索结果
4. 回答是否准确、没有明显的事实错误
5. 回答是否属于当前模块的职责范围

返回 JSON 格式：
{
  "passed": true/false,
  "reason": "通过/不通过的原因",
  "suggestion": "如果不通过，建议如何改进（如重新搜索、换关键词等）"
}

只返回 JSON，不要其他内容。"""

    user_content = f"""用户问题：{query}

工具使用情况：
{tool_summary if tool_summary else "未使用任何工具"}

AI 回答：
{answer}

请评估这个回答的质量。"""

    try:
        response = _safe_request(
            "POST",
            f"{DEEPSEEK_BASE_URL}/v1/chat/completions",
            max_retries=2,
            headers=headers,
            json={
                "model": LLM_MODEL,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content}
                ],
                "temperature": 0.1
            },
            timeout=20
        )

        result = response.json()
        reflection = json.loads(result["choices"][0]["message"]["content"])

        state["reflection_passed"] = reflection.get("passed", True)
        state["reflection_reason"] = reflection.get("reason", "")

        if not state["reflection_passed"]:
            print(f"[LangGraph] 反思未通过: {state['reflection_reason']}")
            state["next_action"] = "retry"
        else:
            print(f"[LangGraph] 反思通过: {state['reflection_reason']}")
            state["next_action"] = "end"
    except Exception as e:
        # 反思失败时默认通过
        print(f"[LangGraph] 反思节点异常: {e}，默认通过")
        state["reflection_passed"] = True
        state["next_action"] = "end"

    return state


# ── 节点：最终答案（反思不通过时的兜底） ──────────────────────────────────

def generate_final(state: AgentState) -> AgentState:
    """最终答案输出（兜底节点）"""
    if not state.get("final_answer"):
        state["final_answer"] = "抱歉，经过多次尝试，我暂时无法回答这个问题。建议您换个方式提问，或联系相关同事。"
    state["next_action"] = "end"
    return state


# ── 图构建 ────────────────────────────────────────────────────────────────

def create_agent_graph():
    """创建增强版 LangGraph 智能体图

    图结构：
    analyze → [条件] → execute_tools → generate_answer → reflect_answer → [条件]
        ↑                                                              ↓
        └──────────────── 循环（最多 8 轮）──────────────────────────────┘
                                                                       ↓
                                                                 generate_final → END
    """
    workflow = StateGraph(AgentState)

    # 添加节点
    workflow.add_node("analyze", analyze_query)
    workflow.add_node("execute_tools", execute_tools_node)
    workflow.add_node("generate_answer", generate_answer)
    workflow.add_node("reflect_answer", reflect_answer)
    workflow.add_node("generate_final", generate_final)

    # 设置入口
    workflow.set_entry_point("analyze")

    # 分析 → 条件路由
    workflow.add_conditional_edges(
        "analyze",
        should_continue,
        {
            "execute_tools": "execute_tools",
            "generate_answer": "generate_answer",
            "generate_final": "generate_final",
            "end": END,
        }
    )

    # 执行工具 → 生成答案
    workflow.add_edge("execute_tools", "generate_answer")

    # 生成答案 → 反思
    workflow.add_edge("generate_answer", "reflect_answer")

    # 反思 → 条件路由
    workflow.add_conditional_edges(
        "reflect_answer",
        after_reflect,
        {
            "generate_final": "generate_final",
            "analyze": "analyze",  # 重新分析（重试）
        }
    )

    # 最终答案 → 结束
    workflow.add_edge("generate_final", END)

    return workflow.compile()


# ── 入口 ──────────────────────────────────────────────────────────────────

def run_agent(query: str, session_id: str = "default", stream_callback=None,
              module: str = "general", knowledge_base_ids: list = None) -> str:
    """运行增强版 LangGraph 智能体

    Args:
        query: 用户查询
        session_id: 会话 ID（用于对话历史）
        stream_callback: 可选的流式回调函数
        module: 当前模块 (policy/tech/admin/general)
        knowledge_base_ids: 限定的知识库 ID 列表
    """
    # 加载对话历史
    try:
        from conversation_store import get_history
        history = get_history(session_id, turns=5)
    except Exception:
        history = []

    graph = create_agent_graph()

    initial_state = {
        "messages": [
            *history,
            {"role": "user", "content": query}
        ],
        "module": module,
        "knowledge_base_ids": knowledge_base_ids,
        "next_action": "analyze",
        "tool_calls": [],
        "tool_results": [],
        "final_answer": "",
        "iteration": 0,
        "reflection_passed": True,
        "reflection_reason": "",
        "stream_callback": stream_callback,
    }

    module_name = MODULE_DESCRIPTIONS.get(module, module)
    print(f"\n[LangGraph] 开始处理查询 (模块: {module_name}): {query[:50]}...")

    try:
        final_state = graph.invoke(initial_state)
        answer = final_state.get("final_answer", "抱歉，我无法回答这个问题。")
        print(f"[LangGraph] 生成答案完成，共 {len(answer)} 字符\n")
        return answer
    except Exception as e:
        error_msg = f"LangGraph 智能体执行失败: {str(e)}"
        print(f"[LangGraph] {error_msg}")
        return error_msg
