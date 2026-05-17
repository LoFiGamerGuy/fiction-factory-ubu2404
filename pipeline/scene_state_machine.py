"""SceneStateMachine — LangGraph-based scene lifecycle manager.

States: Specced → Writer → Editor → Quality → [Convergence branch] → Final

Convergence branches:
  GO           → Final
  REVISE       → Writer  (increment revise_count)
  RE_PLAN      → ForceResolve (V1 fallback; Phase 11 wires ROMA)
  FORCE_RESOLVE → ForceResolve → Final

SQLite checkpointing: pause/resume across process restarts.
"""

from __future__ import annotations

import logging
from typing import Any, Literal

from langgraph.graph import END, StateGraph
from typing_extensions import TypedDict

from pipeline.agents.agent_models import QualityResult
from pipeline.convergence_controller import ConvergenceController, ConvergenceDecision
from pipeline.core.job_context import JobContext

logger = logging.getLogger(__name__)

# ── Scene state (flat, JSON-serializable for SQLite checkpointing) ────────────


class SceneState(TypedDict):
    # Identity
    job_id: str
    scene_id: str
    book_id: str
    series_id: str
    chapter_id: int
    model_tier: str
    seed: int
    # Scene parameters
    scene_brief: str
    word_count_target: int
    heat_level: int
    # Agent outputs (stored as JSON-compatible dicts)
    writer_output: dict[str, Any]
    editor_output: dict[str, Any]
    quality_output: dict[str, Any]
    # Routing
    convergence_decision: str  # ConvergenceDecision value
    revise_count: int
    # Results
    final_text: str
    force_resolved: bool
    force_resolve_reason: str
    # Continuity (Phase 9)
    bible_contradiction: bool
    overdue_promises: list[str]
    # Error tracking
    error: str


# ── Node implementations ───────────────────────────────────────────────────────

_NodeResult = dict[str, Any]

AgentRegistry = dict[str, Any]  # agent_name → agent instance


def make_writer_node(agents: AgentRegistry, job_context_factory: Any) -> Any:
    def writer_node(state: SceneState) -> _NodeResult:
        jc: JobContext = job_context_factory(state)
        writer = agents["writer_agent"]
        try:
            jc = writer.run(jc)
            return {"writer_output": jc.output_data.get("writer_agent", {})}
        except Exception as exc:
            logger.error("writer_node failed: %s", exc)
            return {"error": str(exc), "writer_output": {}}

    return writer_node


def make_editor_node(agents: AgentRegistry, job_context_factory: Any) -> Any:
    def editor_node(state: SceneState) -> _NodeResult:
        jc: JobContext = job_context_factory(state)
        editor = agents["editor_agent"]
        try:
            jc = editor.run(jc)
            return {"editor_output": jc.output_data.get("editor_agent", {})}
        except Exception as exc:
            logger.error("editor_node failed: %s", exc)
            return {"error": str(exc), "editor_output": {}}

    return editor_node


def make_continuity_node(agents: AgentRegistry, job_context_factory: Any) -> Any:
    def continuity_node(state: SceneState) -> _NodeResult:
        continuity = agents.get("continuity_agent")
        if continuity is None:
            return {}
        jc: JobContext = job_context_factory(state)
        try:
            jc = continuity.run(jc)
            return {
                "bible_contradiction": jc.bible_contradiction,
                "overdue_promises": jc.overdue_promises,
            }
        except Exception as exc:
            logger.error("continuity_node failed: %s", exc)
            return {"error": str(exc)}

    return continuity_node


def make_quality_node(agents: AgentRegistry, job_context_factory: Any) -> Any:
    def quality_node(state: SceneState) -> _NodeResult:
        jc: JobContext = job_context_factory(state)
        quality = agents["quality_agent"]
        try:
            jc = quality.run(jc)
            return {"quality_output": jc.output_data.get("quality_agent", {})}
        except Exception as exc:
            logger.error("quality_node failed: %s", exc)
            return {
                "error": str(exc),
                "quality_output": {"needs_review": True, "tier": "fail"},
            }

    return quality_node


def make_convergence_node(controller: ConvergenceController, job_context_factory: Any) -> Any:
    def convergence_node(state: SceneState) -> _NodeResult:
        jc: JobContext = job_context_factory(state)
        quality_data = state.get("quality_output", {})
        quality_result = QualityResult(**quality_data) if quality_data else QualityResult()
        decision = controller.decide(
            quality_result=quality_result,
            job_context=jc,
            revise_count=state.get("revise_count", 0),
        )
        new_revise = state.get("revise_count", 0)
        if decision == ConvergenceDecision.REVISE:
            new_revise += 1
        return {"convergence_decision": decision.value, "revise_count": new_revise}

    return convergence_node


def make_force_resolve_node(job_context_factory: Any) -> Any:
    def force_resolve_node(state: SceneState) -> _NodeResult:
        editor_data = state.get("editor_output", {})
        text = editor_data.get("edited_text", "") or state.get("scene_brief", "")
        logger.warning("force_resolve_node: accepting current draft for %s", state["scene_id"])
        return {
            "final_text": text,
            "force_resolved": True,
            "force_resolve_reason": state.get("convergence_decision", "budget_exhausted"),
        }

    return force_resolve_node


def make_final_node(agents: AgentRegistry, job_context_factory: Any) -> Any:
    def final_node(state: SceneState) -> _NodeResult:
        editor_data = state.get("editor_output", {})
        text = editor_data.get("edited_text", "") or state.get("final_text", "")
        # Update ledgers if quality_agent is available
        quality_agent = agents.get("quality_agent")
        if quality_agent is not None and not state.get("force_resolved", False):
            jc: JobContext = job_context_factory(state)
            try:
                quality_agent.update_ledgers(jc)
            except Exception as exc:
                logger.error("final_node: ledger update failed: %s", exc)
        return {"final_text": text}

    return final_node


# ── Routing edges ─────────────────────────────────────────────────────────────


def _after_convergence(
    state: SceneState,
) -> Literal["writer_node", "final_node", "force_resolve_node"]:
    decision = state.get("convergence_decision", "GO")
    if decision == ConvergenceDecision.REVISE:
        return "writer_node"
    if decision in (ConvergenceDecision.RE_PLAN, ConvergenceDecision.FORCE_RESOLVE):
        return "force_resolve_node"
    return "final_node"


# ── Graph factory ─────────────────────────────────────────────────────────────


class SceneStateMachine:
    """Compiled LangGraph graph for scene generation lifecycle."""

    def __init__(
        self,
        agents: AgentRegistry,
        job_context_factory: Any,
        controller: ConvergenceController | None = None,
        checkpoint_db_path: str | None = None,
    ) -> None:
        self._agents = agents
        self._factory = job_context_factory
        self._controller = controller or ConvergenceController()
        self._checkpoint_db = checkpoint_db_path
        self._graph = self._build()

    def _build(self) -> Any:
        builder: StateGraph[SceneState] = StateGraph(SceneState)

        builder.add_node("writer_node", make_writer_node(self._agents, self._factory))
        builder.add_node("editor_node", make_editor_node(self._agents, self._factory))
        builder.add_node("continuity_node", make_continuity_node(self._agents, self._factory))
        builder.add_node("quality_node", make_quality_node(self._agents, self._factory))
        builder.add_node("convergence_node", make_convergence_node(self._controller, self._factory))
        builder.add_node("force_resolve_node", make_force_resolve_node(self._factory))
        builder.add_node("final_node", make_final_node(self._agents, self._factory))

        builder.set_entry_point("writer_node")
        builder.add_edge("writer_node", "editor_node")
        builder.add_edge("editor_node", "continuity_node")
        builder.add_edge("continuity_node", "quality_node")
        builder.add_edge("quality_node", "convergence_node")
        builder.add_conditional_edges(
            "convergence_node",
            _after_convergence,
            {
                "writer_node": "writer_node",
                "final_node": "final_node",
                "force_resolve_node": "force_resolve_node",
            },
        )
        builder.add_edge("force_resolve_node", "final_node")
        builder.add_edge("final_node", END)

        if self._checkpoint_db:
            from langgraph.checkpoint.sqlite import SqliteSaver

            with SqliteSaver.from_conn_string(self._checkpoint_db) as checkpointer:
                return builder.compile(checkpointer=checkpointer)
        return builder.compile()

    def run(self, initial_state: SceneState) -> SceneState:
        """Execute the graph from the initial state and return the final state."""
        config: dict[str, Any] = {}
        if self._checkpoint_db:
            import uuid

            config = {"configurable": {"thread_id": str(uuid.uuid4())}}
        result: SceneState = self._graph.invoke(initial_state, config=config)
        return result

    def resume(self, thread_id: str) -> SceneState | None:
        """Resume a previously checkpointed run."""
        if not self._checkpoint_db:
            return None
        config: dict[str, Any] = {"configurable": {"thread_id": thread_id}}
        result: SceneState = self._graph.invoke(None, config=config)
        return result
