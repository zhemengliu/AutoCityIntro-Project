"""主状态图编译（Supervisor + 子 Agent 子图）"""
from langgraph.graph import END, START, StateGraph

from graph.checkpoints import get_checkpointer
from graph.nodes import (
    after_subgraph,
    classify_intent_node,
    finalize_node,
    load_context,
    prefetch_node,
    resume_image_generation,
    route_to_subgraph,
    supervisor_dispatch,
)
from graph.state import CityAgentState
from graph.subgraphs import (
    get_companion_graph,
    get_general_graph,
    get_realtime_guard_graph,
    get_trip_planner_graph,
)


def build_city_graph(*, with_checkpoint: bool = True):
    builder = StateGraph(CityAgentState)

    # 共享前置节点
    builder.add_node("load_context", load_context)
    builder.add_node("classify", classify_intent_node)
    builder.add_node("prefetch", prefetch_node)
    builder.add_node("supervisor", supervisor_dispatch)

    # 独立 LangGraph 子图（各含 agent ↔ tools ReAct 循环）
    builder.add_node("trip_planner", get_trip_planner_graph())
    builder.add_node("realtime_guard", get_realtime_guard_graph())
    builder.add_node("companion", get_companion_graph())
    builder.add_node("general", get_general_graph())

    builder.add_node("finalize", finalize_node)
    builder.add_node("resume_image", resume_image_generation)

    builder.add_edge(START, "load_context")
    builder.add_edge("load_context", "classify")
    builder.add_edge("classify", "prefetch")
    builder.add_edge("prefetch", "supervisor")
    builder.add_conditional_edges(
        "supervisor",
        route_to_subgraph,
        {
            "trip_planner": "trip_planner",
            "realtime_guard": "realtime_guard",
            "companion": "companion",
            "general": "general",
        },
    )

    for sub in ("trip_planner", "realtime_guard", "companion", "general"):
        builder.add_conditional_edges(
            sub,
            after_subgraph,
            {"finalize": "finalize", "interrupt": END},
        )

    builder.add_edge("finalize", END)
    builder.add_edge("resume_image", END)

    if with_checkpoint:
        return builder.compile(checkpointer=get_checkpointer())
    return builder.compile()


_compiled = None


def get_city_graph():
    global _compiled
    if _compiled is None:
        _compiled = build_city_graph(with_checkpoint=True)
    return _compiled
