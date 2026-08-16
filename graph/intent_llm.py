"""LLM 意图分类（规则兜底）"""
import json
import os
import re
from typing import Optional, Tuple

from graph.intent import classify_intent, route_to_subagent

VALID_INTENTS = frozenset(
    {"emergency", "route", "city_poi", "nearby", "complex", "image_gen", "chat"}
)
VALID_AGENTS = frozenset({"trip_planner", "realtime_guard", "companion", "general"})


def _parse_llm_json(text: str) -> Optional[dict]:
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{[^{}]+\}", text)
        if m:
            try:
                return json.loads(m.group())
            except json.JSONDecodeError:
                return None
    return None


def llm_classify(user_text: str) -> Optional[Tuple[str, str]]:
    """调用 LLM 返回 (intent, active_agent)，失败返回 None。"""
    if os.getenv("USE_LLM_INTENT", "false").lower() != "true":
        return None
    try:
        from langchain_core.messages import HumanMessage, SystemMessage
        from llm_factory import get_llm

        llm = get_llm(streaming=False)
        sys = SystemMessage(
            content=(
                "你是意图分类器。根据用户输入返回 JSON："
                '{"intent":"...", "active_agent":"..."} '
                f"intent 取值：{sorted(VALID_INTENTS)}；"
                f"active_agent 取值：{sorted(VALID_AGENTS)}。"
                "只输出 JSON，不要解释。"
            )
        )
        resp = llm.invoke([sys, HumanMessage(content=user_text)])
        data = _parse_llm_json(str(resp.content or ""))
        if not data:
            return None
        intent = data.get("intent", "chat")
        agent = data.get("active_agent", "companion")
        if intent not in VALID_INTENTS:
            intent = "chat"
        if agent not in VALID_AGENTS:
            agent = "companion"
        return intent, agent
    except Exception:
        return None


def classify_hybrid(user_text: str) -> Tuple[str, str]:
    """LLM 优先（可配置），规则引擎兜底。"""
    rule_intent = classify_intent(user_text)
    rule_agent = route_to_subagent(user_text)

    llm_result = llm_classify(user_text)
    if llm_result:
        intent, agent = llm_result
        if rule_intent == "emergency":
            return "emergency", "realtime_guard"
        return intent, agent

    if rule_intent in ("route", "nearby", "city_poi") and rule_agent == "companion":
        return rule_intent, "general"
    return rule_intent, rule_agent
