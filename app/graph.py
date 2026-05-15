"""
Colored Petri Net (CPN) Graph Engine — deterministic orchestration.

Defines the multi-agent execution graph as a bipartite graph of
Places (system states) and Transitions (agent actions). Routing
decisions are made via pure Python if/else logic — the LLM is
NEVER consulted for graph traversal decisions.

The Master State (the "coloured token") flows through the net.
After each transition fires, the state is checkpointed to SQLite.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Callable, Dict, List, Optional

from app import db
from app.schemas import MasterState
from app.telemetry import trace_operation

logger = logging.getLogger(__name__)


# ── Place & Transition definitions ───────────────────────────────────────────

class Place:
    """A state node in the Petri net (e.g. 'recon_ready', 'exploit_done')."""
    def __init__(self, name: str, description: str = ""):
        self.name = name
        self.description = description

    def __repr__(self) -> str:
        return f"Place({self.name!r})"


class Transition:
    """
    An executable edge in the Petri net.
    
    - source:     the Place this transition departs from
    - targets:    mapping of condition-label → destination Place
    - action:     the function to execute (agent logic)
    - guard:      optional pure-Python predicate that must be True to fire
    """
    def __init__(
        self,
        name: str,
        source: Place,
        targets: Dict[str, Place],
        action: Callable[[MasterState], MasterState],
        guard: Optional[Callable[[MasterState], bool]] = None,
    ):
        self.name = name
        self.source = source
        self.targets = targets
        self.action = action
        self.guard = guard

    def can_fire(self, state: MasterState) -> bool:
        """Check if this transition's guard allows firing."""
        if state.current_node != self.source.name:
            return False
        if self.guard and not self.guard(state):
            return False
        return True

    def fire(self, state: MasterState) -> MasterState:
        """Execute the action and return the updated state."""
        return self.action(state)


# ── The CPN Engine ───────────────────────────────────────────────────────────

class CPNEngine:
    """
    Executes a Colored Petri Net by repeatedly finding and firing
    enabled transitions until the token reaches a terminal place.
    """

    def __init__(self) -> None:
        self.places: Dict[str, Place] = {}
        self.transitions: List[Transition] = []
        self.terminal_places: set[str] = set()

    def add_place(self, name: str, *, terminal: bool = False, description: str = "") -> Place:
        place = Place(name, description)
        self.places[name] = place
        if terminal:
            self.terminal_places.add(name)
        return place

    def add_transition(
        self,
        name: str,
        source: Place,
        targets: Dict[str, Place],
        action: Callable[[MasterState], MasterState],
        guard: Optional[Callable[[MasterState], bool]] = None,
    ) -> Transition:
        t = Transition(name, source, targets, action, guard)
        self.transitions.append(t)
        return t

    def run(self, state: MasterState) -> MasterState:
        """
        Execute the CPN from the current state until a terminal place
        is reached or no transitions can fire.
        """
        with trace_operation(
            "cpn_engine_run",
            attributes={
                "cpn.trace_id": state.trace_id,
                "cpn.start_node": state.current_node,
            },
        ) as engine_span:
            max_steps = 20  # absolute safety limit
            step = 0

            while step < max_steps:
                step += 1

                # Check if we reached a terminal place
                if state.current_node in self.terminal_places:
                    state.completed = True
                    logger.info("CPN reached terminal place: %s", state.current_node)
                    engine_span.set_attribute("cpn.final_node", state.current_node)
                    engine_span.set_attribute("cpn.steps", step)
                    break

                # Find an enabled transition
                fired = False
                for transition in self.transitions:
                    if transition.can_fire(state):
                        logger.info(
                            "Step %d: firing transition '%s' from '%s'",
                            step, transition.name, state.current_node,
                        )

                        with trace_operation(
                            f"transition:{transition.name}",
                            attributes={
                                "cpn.transition": transition.name,
                                "cpn.source": transition.source.name,
                                "cpn.step": step,
                                "cpn.retry_count": state.retry_count,
                            },
                        ):
                            # Fire the transition (execute agent logic)
                            state = transition.fire(state)

                            # Checkpoint to SQLite after every transition
                            db.save_checkpoint(
                                state.trace_id,
                                state.current_node,
                                state.model_dump(mode="json"),
                            )

                        fired = True
                        break

                if not fired:
                    logger.error(
                        "CPN deadlock: no transition can fire from '%s'",
                        state.current_node,
                    )
                    state.error = f"Deadlock at {state.current_node}"
                    state.completed = True
                    break

            if step >= max_steps:
                logger.error("CPN exceeded max steps (%d)", max_steps)
                state.error = f"Exceeded max steps ({max_steps})"
                state.completed = True

            engine_span.set_attribute("cpn.final_node", state.current_node)
            engine_span.set_attribute("cpn.total_steps", step)
            return state


# ── Build the Red-Team CPN ───────────────────────────────────────────────────

def build_red_team_cpn() -> CPNEngine:
    """
    Construct the full Red-Team CPN with all places, transitions,
    and deterministic routing logic.
    """
    from app.agents.exploiter import run_exploit
    from app.agents.patcher import run_patch
    from app.agents.recon import run_recon
    from app.agents.verifier import verify_exploit
    from app.config import SANDBOX_MAX_RETRIES

    engine = CPNEngine()

    # ── Places ────────────────────────────────────────────────────────────
    p_ingress       = engine.add_place("ingress", description="Webhook received")
    p_recon_ready   = engine.add_place("recon_ready", description="Ready to scan target")
    p_recon_done    = engine.add_place("recon_done", description="Recon complete")
    p_exploit_ready = engine.add_place("exploit_ready", description="Ready to exploit")
    p_exploit_done  = engine.add_place("exploit_done", description="Exploit complete")
    p_verified      = engine.add_place("verified", description="Exploit verified")
    p_patch_ready   = engine.add_place("patch_ready", description="Ready to patch")
    p_patch_done    = engine.add_place("patch_done", terminal=True, description="Patch committed")
    p_end_safe      = engine.add_place("end_safe", terminal=True, description="No vulnerability found")
    p_end_error     = engine.add_place("end_error", terminal=True, description="Pipeline failed")

    # ── Transitions ───────────────────────────────────────────────────────

    # T1: Ingress → Recon Ready
    def t1_action(state: MasterState) -> MasterState:
        state.current_node = "recon_ready"
        return state

    engine.add_transition(
        "t1_start_recon", p_ingress,
        {"default": p_recon_ready},
        t1_action,
    )

    # T2: Recon Ready → Recon Done (runs the Recon Agent)
    def t2_action(state: MasterState) -> MasterState:
        try:
            result = run_recon(state.webhook.target_url)
            state.recon = result
            if result.vulnerable_endpoints:
                state.current_node = "exploit_ready"
            else:
                state.current_node = "end_safe"
        except Exception as exc:
            logger.error("Recon failed: %s", exc)
            state.error = str(exc)
            state.current_node = "end_error"
        return state

    engine.add_transition(
        "t2_run_recon", p_recon_ready,
        {"has_vulns": p_exploit_ready, "no_vulns": p_end_safe, "error": p_end_error},
        t2_action,
    )

    # T3: Exploit Ready → Exploit Done (runs the Exploiter Agent)
    def t3_action(state: MasterState) -> MasterState:
        try:
            result = run_exploit(state.recon)
            state.exploit = result
            state.current_node = "exploit_done"
        except Exception as exc:
            logger.error("Exploit failed: %s", exc)
            state.error = str(exc)
            state.current_node = "end_error"
        return state

    engine.add_transition(
        "t3_run_exploit", p_exploit_ready,
        {"done": p_exploit_done, "error": p_end_error},
        t3_action,
    )

    # T4: Exploit Done → Verified (runs the Verifier)
    def t4_action(state: MasterState) -> MasterState:
        result = verify_exploit(state.exploit)
        state.verification = result

        if result.verified:
            state.current_node = "patch_ready"
        else:
            # Retry logic with circuit breaker
            state.retry_count += 1
            if state.retry_count > SANDBOX_MAX_RETRIES:
                logger.error("Max retries exceeded at verification")
                state.error = f"Verification failed after {state.retry_count} retries: {result.reason}"
                state.current_node = "end_error"
            else:
                logger.warning(
                    "Verification failed (attempt %d/%d): %s — retrying exploit",
                    state.retry_count, SANDBOX_MAX_RETRIES, result.reason,
                )
                state.current_node = "exploit_ready"
        return state

    engine.add_transition(
        "t4_verify", p_exploit_done,
        {"verified": p_patch_ready, "retry": p_exploit_ready, "fail": p_end_error},
        t4_action,
    )

    # T5: Patch Ready → Patch Done (runs the Patcher Agent)
    def t5_action(state: MasterState) -> MasterState:
        try:
            result = run_patch(
                state.recon,
                state.exploit,
                state.verification,
                state.trace_id,
            )
            state.patch = result
            state.current_node = "patch_done"
        except Exception as exc:
            logger.error("Patch failed: %s", exc)
            state.error = str(exc)
            state.current_node = "end_error"
        return state

    engine.add_transition(
        "t5_run_patch", p_patch_ready,
        {"done": p_patch_done, "error": p_end_error},
        t5_action,
    )

    return engine
