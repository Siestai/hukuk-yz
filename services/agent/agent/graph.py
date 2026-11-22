"""The graph: a fixed sequence of six nodes; `clarify` may stop once more for a follow-up.
The code decides the order, the sources and the checks; the models make small typed decisions
inside the nodes. Postgres holds the state of a thread (the `agent` schema), so that the
clarification can wait for the user."""

from typing import Any

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from agent.nodes import Deps, State, make_nodes

ORDER = ["intake", "clarify", "plan", "retrieve", "holding_map", "draft"]


def build_graph(
    deps: Deps, checkpointer: BaseCheckpointSaver[Any]
) -> CompiledStateGraph[State, None, State, State]:
    builder = StateGraph(State)
    nodes = make_nodes(deps)
    for name in ORDER:
        builder.add_node(name, nodes[name])
    builder.add_edge(START, ORDER[0])
    for before, after in zip(ORDER, ORDER[1:], strict=False):
        if before != "clarify":
            builder.add_edge(before, after)
    # A follow-up clarification (an answer opened a branch) stops at `clarify` once more.
    builder.add_conditional_edges(
        "clarify", lambda state: "clarify" if state.get("clarification") else "plan"
    )
    builder.add_edge(ORDER[-1], END)
    return builder.compile(checkpointer=checkpointer)
