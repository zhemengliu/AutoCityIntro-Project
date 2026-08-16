"""LangGraph 状态定义"""
from typing import Annotated, Any, Dict, List, Optional, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class CityAgentState(TypedDict, total=False):
    messages: Annotated[List[BaseMessage], add_messages]
    session_id: str
    device_id: str
    user_text: str
    user_location: str
    user_location_label: str
    profile_summary: str
    intent: str
    active_agent: str
    query_city: str
    subtasks: List[str]
    location_context: str
    tool_result_text: str
    tool_call_history: List[Dict[str, Any]]
    poi_map: Optional[Dict[str, Any]]
    route_map: Optional[Dict[str, Any]]
    traffic_map: Optional[Dict[str, Any]]
    image_url: Optional[str]
    trip_plan: Optional[Dict[str, Any]]
    final_response: str
    error: str
    pending_image_prompt: str
    awaiting_image_confirm: bool
    sse_events: List[Dict[str, Any]]
