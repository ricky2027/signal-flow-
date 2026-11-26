from typing import TypedDict
from langgraph.graph import StateGraph, START, END
from app.agents import research, signals, writing


class State(TypedDict, total=False):
    input: dict
    research: dict
    pages: list[dict]
    page_extractions: dict[str, dict]
    extraction_repairs: list[str]
    evidence: dict
    signals: list[dict]
    evaluation_state: str
    draft: dict
    findings: list[str]
    generation_attempts: int
    instructions: str | None
    followup: bool
    needs_followup: bool
    outcome_reason: str | None
    outcome: str | None


# Context owns provider and persistence; graph nodes remain independently testable.
def build_graph(ctx, regenerate=False):
    graph = StateGraph(State)

    def wrap(stage, fn):
        async def execute(state):
            ctx.event("stage.started", stage)
            update = await fn(state, ctx)
            ctx.event("stage.completed", stage, {
                "evaluation_state": update["evaluation_state"],
                "outcome": update.get("outcome"),
            } if stage == "evaluate_signals" else None)
            return update

        return execute

    graph.add_node("research", wrap("research", research.research))
    graph.add_node("extract", wrap("qualify_evidence", research.extract))
    graph.add_node("evaluate", wrap("evaluate_signals", signals.evaluate))
    graph.add_node("generate", wrap("draft", writing.generate))
    graph.add_node("quality", wrap("validate_draft", writing.validate))
    graph.add_edge(START, "evaluate" if regenerate else "research")
    graph.add_edge("research", "extract")
    graph.add_conditional_edges(
        "extract",
        lambda s: "followup" if s.get("needs_followup") else "evaluate",
        {"followup": "research", "evaluate": "evaluate"},
    )
    graph.add_conditional_edges(
        "evaluate",
        lambda s: "stop" if s.get("outcome") else "draft",
        {"stop": END, "draft": "generate"},
    )
    graph.add_edge("generate", "quality")
    graph.add_conditional_edges(
        "quality",
        lambda s: "repair" if s.get("findings") and not s.get("outcome") else "stop",
        {"repair": "generate", "stop": END},
    )
    return graph.compile()
