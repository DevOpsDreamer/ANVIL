"""
Colored Petri Net (CPN) Orchestration Engine.

Implements the formal tuple N = (P, T, F, W, C, G, M0) from AEGIS Paper §3.
All routing decisions are encoded as Python guard predicates —
the LLM never touches the control plane.

Places correspond to pipeline states; transitions correspond to agent
actions.  A single coloured token (MasterState) flows through the net.
After every successful firing the new marking is atomically committed
to SQLite for crash recovery.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import (
    Callable,
    Dict,
    List,
    Optional,
    Tuple,
)

from app.schemas import MasterState, PlaceName

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Tracing — graceful degradation when OpenTelemetry is unavailable
# ---------------------------------------------------------------------------
try:
    from app.telemetry import trace_operation
except ImportError:
    from contextlib import contextmanager

    @contextmanager
    def trace_operation(name, attributes=None, kind=None):  # type: ignore
        yield None


# ═══════════════════════════════════════════════════════════════════════════
#  Core CPN Primitives
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class Place:
    """A named location in the Petri net where a token can reside."""
    name: str
    terminal: bool = False
    description: str = ""

    def __repr__(self) -> str:
        kind = "terminal" if self.terminal else "place"
        return f"<Place {self.name} ({kind})>"


# Type aliases for readability
ActionFn = Callable[[MasterState], Tuple[MasterState, str]]
GuardFn = Callable[[MasterState], bool]


@dataclass
class Transition:
    """
    A transition in the CPN.

    Attributes
    ----------
    name : str
        Human-readable label (e.g. ``t1_recon``).
    source : Place
        The input arc — the token must be here for the transition to be
        considered.
    targets : Dict[str, Place]
        Output arcs keyed by *route key*.  The action function returns
        a ``(state, route_key)`` tuple; the engine looks up
        ``targets[route_key]`` to decide the next place.
    action : ActionFn
        The callable that performs work (agent call) and returns the
        mutated state **plus** a route key selecting the output arc.
    guard : Optional[GuardFn]
        Pure-Python predicate evaluated **before** the action.  If it
        returns ``False`` the transition does not fire.
    """
    name: str
    source: Place
    targets: Dict[str, Place]
    action: ActionFn
    guard: Optional[GuardFn] = None

    def can_fire(self, state: MasterState) -> bool:
        """Check input arc and guard predicate."""
        if state.current_node != self.source.name:
            return False
        if self.guard is not None and not self.guard(state):
            return False
        return True

    def fire(self, state: MasterState) -> Tuple[MasterState, Place]:
        """
        Execute the action and route the token via the targets dict.

        Returns
        -------
        (updated_state, next_place)
        """
        new_state, route_key = self.action(state)
        if route_key not in self.targets:
            raise RuntimeError(
                f"Transition {self.name!r} returned unknown route key "
                f"{route_key!r}.  Valid keys: {list(self.targets.keys())}"
            )
        next_place = self.targets[route_key]
        new_state.current_node = next_place.name
        return new_state, next_place


# ═══════════════════════════════════════════════════════════════════════════
#  CPN Engine
# ═══════════════════════════════════════════════════════════════════════════

class CPNEngine:
    """
    Deterministic Colored Petri Net execution engine.

    The engine repeatedly scans the transition list, fires the first
    enabled transition, commits the new marking to SQLite, and loops
    until a terminal place is reached or the step limit is hit.
    """

    MAX_STEPS = 20

    def __init__(self) -> None:
        self.places: Dict[str, Place] = {}
        self.transitions: List[Transition] = []
        self.terminal_places: set[str] = set()

    # ── Construction helpers ──────────────────────────────────────────

    def add_place(
        self,
        name: str,
        *,
        terminal: bool = False,
        description: str = "",
    ) -> Place:
        if name in self.places:
            raise ValueError(f"Duplicate place name: {name!r}")
        p = Place(name=name, terminal=terminal, description=description)
        self.places[name] = p
        if terminal:
            self.terminal_places.add(name)
        return p

    def add_transition(
        self,
        name: str,
        *,
        source: Place,
        targets: Dict[str, Place],
        action: ActionFn,
        guard: Optional[GuardFn] = None,
    ) -> Transition:
        t = Transition(
            name=name,
            source=source,
            targets=targets,
            action=action,
            guard=guard,
        )
        self.transitions.append(t)
        return t

    # ── Net validation ────────────────────────────────────────────────

    def validate_net(self) -> List[str]:
        """
        Structural validation of the CPN topology.

        Returns a list of warnings/errors.  An empty list means the
        net is well-formed.
        """
        issues: List[str] = []

        # Every non-terminal place must have at least one outgoing transition
        place_has_outgoing = {name: False for name in self.places}
        for t in self.transitions:
            place_has_outgoing[t.source.name] = True
            # All target places must be registered
            for key, target in t.targets.items():
                if target.name not in self.places:
                    issues.append(
                        f"Transition {t.name!r} target {key!r} -> "
                        f"{target.name!r} is not a registered place"
                    )

        for name, has_out in place_has_outgoing.items():
            if not has_out and name not in self.terminal_places:
                issues.append(
                    f"Non-terminal place {name!r} has no outgoing transitions"
                )

        return issues

    # ── Execution ─────────────────────────────────────────────────────

    def run(self, state: MasterState) -> MasterState:
        """
        Execute the CPN from the current marking until a terminal place
        is reached or the step limit is hit.
        """
        from app.db import save_checkpoint  # late import to avoid cycles

        with trace_operation("cpn_engine_run", {"cpn.initial_node": state.current_node}):
            for step in range(1, self.MAX_STEPS + 1):
                # Terminal check
                if state.current_node in self.terminal_places:
                    state.completed = True
                    logger.info(
                        "CPN reached terminal place %r at step %d",
                        state.current_node, step,
                    )
                    break

                # Find the first enabled transition
                fired = False
                for t in self.transitions:
                    if not t.can_fire(state):
                        continue

                    logger.info(
                        "[step %d] Firing %s  (%s → ...)",
                        step, t.name, t.source.name,
                    )

                    with trace_operation(
                        f"transition:{t.name}",
                        {
                            "cpn.transition": t.name,
                            "cpn.step": step,
                            "cpn.source": t.source.name,
                            "cpn.retry_count": state.retry_count,
                        },
                    ):
                        try:
                            state, next_place = t.fire(state)
                        except Exception as exc:
                            logger.exception(
                                "Transition %s raised: %s", t.name, exc,
                            )
                            state.error = f"{t.name}: {exc}"
                            state.current_node = PlaceName.PERROR.value
                            state.completed = True

                    # Atomic checkpoint after every firing
                    try:
                        save_checkpoint(
                            trace_id=state.trace_id,
                            node_id=state.current_node,
                            state=state.model_dump_json(),
                        )
                    except Exception as exc:
                        logger.error("Checkpoint failed: %s", exc)

                    fired = True
                    break  # restart scan from the top

                if not fired:
                    logger.error(
                        "CPN deadlock at place %r — no transition can fire",
                        state.current_node,
                    )
                    state.error = f"Deadlock at {state.current_node}"
                    state.current_node = PlaceName.PERROR.value
                    state.completed = True
                    break
            else:
                # Exhausted MAX_STEPS
                logger.error(
                    "CPN exceeded %d steps — forcing terminal",
                    self.MAX_STEPS,
                )
                state.error = f"Exceeded {self.MAX_STEPS} step limit"
                state.current_node = PlaceName.PERROR.value
                state.completed = True

        return state

    # ── Crash Recovery ────────────────────────────────────────────────

    @staticmethod
    def resume(trace_id: str) -> Optional[MasterState]:
        """
        Load the latest committed marking for *trace_id* from SQLite
        and return a MasterState ready to re-enter `run()`.

        Returns None if no checkpoint exists.
        """
        from app.db import load_latest_checkpoint

        raw = load_latest_checkpoint(trace_id)
        if raw is None:
            return None
        try:
            return MasterState.model_validate_json(raw)
        except Exception as exc:
            logger.error("Failed to deserialize checkpoint: %s", exc)
            return None


# ═══════════════════════════════════════════════════════════════════════════
#  Factory: Web-App Pipeline CPN
# ═══════════════════════════════════════════════════════════════════════════

def build_web_cpn(
    scan_id: str,
    emit_fn: Callable,
    loop,
) -> CPNEngine:
    """
    Construct the CPN for the web-app scan pipeline.

    Places (9):  precon_pending  precon_done  pexploit_ready  pexploit_done
                 pverify_pending  pverify_done  ppatch_ready
                 ppatch_done (terminal)  perror (terminal)

    Transitions (5):  t1_recon  t2_exploit  t3_verify  t4_patch  t5_pr_gen
    """
    import asyncio
    from app.config import SANDBOX_MAX_RETRIES

    engine = CPNEngine()

    # ── Places ────────────────────────────────────────────────────────
    p_precon_pending = engine.add_place(
        PlaceName.PRECON_PENDING.value,
        description="Awaiting reconnaissance",
    )
    p_precon_done = engine.add_place(
        PlaceName.PRECON_DONE.value,
        description="Recon complete, routing decision pending",
    )
    p_exploit_ready = engine.add_place(
        PlaceName.PEXPLOIT_READY.value,
        description="Ready for exploit generation",
    )
    p_exploit_done = engine.add_place(
        PlaceName.PEXPLOIT_DONE.value,
        description="Exploit executed, awaiting verification",
    )

    p_patch_ready = engine.add_place(
        PlaceName.PPATCH_READY.value,
        description="Ready for patch generation",
    )
    p_patch_done = engine.add_place(
        PlaceName.PPATCH_DONE.value,
        terminal=True,
        description="PR created — pipeline success",
    )
    p_error = engine.add_place(
        PlaceName.PERROR.value,
        terminal=True,
        description="Terminal error state",
    )

    # ── SSE bridge ────────────────────────────────────────────────────

    def _emit_sync(stage: str, status: str, message: str, **kw):
        """Bridge sync transition actions to the async SSE emitter."""
        try:
            asyncio.run_coroutine_threadsafe(
                emit_fn(scan_id, stage, status, message, **kw), loop,
            )
        except Exception as exc:
            logger.warning("SSE emit failed: %s", exc)

    # ── Transition Actions ────────────────────────────────────────────

    def _t1_recon(state: MasterState) -> Tuple[MasterState, str]:
        """T1: Run reconnaissance agent on cloned repo."""
        from app.agents.recon import run_recon_source
        from app.github_service import detect_entry_point

        _emit_sync("recon", "running", "Scanning repository for vulnerabilities...")

        recon_output = run_recon_source(
            repo_dir=state.repo_dir,
            repo_url=state.repo_url or "",
        )
        state.recon = recon_output

        vuln_count = len(recon_output.vulnerable_endpoints)
        _emit_sync(
            "recon", "done",
            f"Found {vuln_count} potential vulnerabilities",
            vuln_count=vuln_count,
        )

        if vuln_count > 0:
            return state, "vulns_found"
        else:
            return state, "clean"

    def _t1_guard(state: MasterState) -> bool:
        """Guard: webhook payload must be present."""
        return state.webhook is not None

    def _t2_route_recon(state: MasterState) -> Tuple[MasterState, str]:
        """T2: Route based on recon results — vulns found or clean repo."""
        if state.recon and len(state.recon.vulnerable_endpoints) > 0:
            return state, "vulns_found"
        state.error = None  # clean repos are not errors
        return state, "clean"

    def _t2_guard(state: MasterState) -> bool:
        """Guard: recon output must be present."""
        return state.recon is not None

    def _t3_exploit(state: MasterState) -> Tuple[MasterState, str]:
        """T3: Generate and execute exploit payload."""
        from app.agents.exploiter import run_exploit
        from app.github_service import detect_entry_point

        _emit_sync(
            "exploit", "running",
            f"Generating exploit (attempt {state.retry_count + 1})...",
        )

        entry_point = None
        if state.repo_dir:
            entry_point = detect_entry_point(state.repo_dir)

        exploit_output = run_exploit(
            recon=state.recon,
            repo_dir=state.repo_dir,
            entry_point=entry_point,
        )
        state.exploit = exploit_output
        return state, "ok"

    def _t3_guard(state: MasterState) -> bool:
        """Guard: recon found vulnerabilities."""
        return (
            state.recon is not None
            and len(state.recon.vulnerable_endpoints) > 0
        )

    def _t4_verify(state: MasterState) -> Tuple[MasterState, str]:
        """T4: Deterministic verification of exploit output."""
        from app.agents.verifier import verify_exploit

        _emit_sync("verify", "running", "Verifying exploit (deterministic)...")

        result = verify_exploit(state.exploit)
        state.verification = result

        if result.verified:
            _emit_sync("verify", "done", "Exploit verified — preparing patch")
            return state, "verified"
        else:
            # Record failed attempt for feedback-aware retries
            from app.schemas import AttemptRecord
            state.attempt_history.append(AttemptRecord(
                attempt_number=state.retry_count + 1,
                exploit_code=state.exploit.exploit_payload_used if state.exploit else "",
                sandbox_stdout=state.exploit.sandbox_stdout if state.exploit else "",
                failure_reason=result.reason,
            ))
            state.retry_count += 1

            if state.retry_count >= SANDBOX_MAX_RETRIES:
                _emit_sync(
                    "verify", "error",
                    f"Verification failed after {SANDBOX_MAX_RETRIES} attempts",
                )
                state.error = (
                    f"Exploit verification failed after "
                    f"{SANDBOX_MAX_RETRIES} retries: {result.reason}"
                )
                return state, "exhausted"
            else:
                _emit_sync(
                    "verify", "running",
                    f"Verification failed — retrying ({state.retry_count}/{SANDBOX_MAX_RETRIES})",
                )
                return state, "retry"

    def _t4_guard(state: MasterState) -> bool:
        """Guard: exploit output must be present."""
        return state.exploit is not None

    def _t5_patch(state: MasterState) -> Tuple[MasterState, str]:
        """T5: Generate patch and open GitHub PR."""
        from app.agents.patcher import run_patch_github

        _emit_sync("patch", "running", "Generating security patch...")

        patch_output = run_patch_github(
            recon=state.recon,
            exploit=state.exploit,
            verification=state.verification,
            trace_id=state.trace_id,
            github_token=state.github_token,
            repo_url=state.repo_url,
            repo_dir=state.repo_dir,
            base_branch=state.base_branch,
        )
        state.patch = patch_output

        pr_url = patch_output.pr_url
        _emit_sync(
            "pushing", "done",
            f"Pull request created: {pr_url}" if pr_url else "Patch generated",
            pr_url=pr_url,
        )
        return state, "ok"

    def _t5_guard(state: MasterState) -> bool:
        """Guard: verification must have succeeded."""
        return (
            state.verification is not None
            and state.verification.verified
        )

    # ── Register Transitions ──────────────────────────────────────────

    # T1: precon_pending → precon_done (recon agent)
    engine.add_transition(
        "t1_recon",
        source=p_precon_pending,
        targets={
            "vulns_found": p_precon_done,
            "clean": p_error,  # clean repo → terminal (no vulns = done)
        },
        action=_t1_recon,
        guard=_t1_guard,
    )

    # T2: precon_done → pexploit_ready or perror
    engine.add_transition(
        "t2_route",
        source=p_precon_done,
        targets={
            "vulns_found": p_exploit_ready,
            "clean": p_error,
        },
        action=_t2_route_recon,
        guard=_t2_guard,
    )

    # T3: pexploit_ready → pexploit_done (exploit agent)
    engine.add_transition(
        "t3_exploit",
        source=p_exploit_ready,
        targets={"ok": p_exploit_done},
        action=_t3_exploit,
        guard=_t3_guard,
    )

    # T4: pexploit_done → ppatch_ready / pexploit_ready (retry) / perror
    engine.add_transition(
        "t4_verify",
        source=p_exploit_done,
        targets={
            "verified": p_patch_ready,
            "retry": p_exploit_ready,
            "exhausted": p_error,
        },
        action=_t4_verify,
        guard=_t4_guard,
    )

    # T5: ppatch_ready → ppatch_done (patcher + PR)
    engine.add_transition(
        "t5_patch",
        source=p_patch_ready,
        targets={"ok": p_patch_done},
        action=_t5_patch,
        guard=_t5_guard,
    )

    # ── Validate net structure ────────────────────────────────────────
    issues = engine.validate_net()
    if issues:
        for issue in issues:
            logger.warning("CPN validation: %s", issue)

    return engine


# ═══════════════════════════════════════════════════════════════════════════
#  Factory: CLI / Webhook Pipeline CPN (legacy)
# ═══════════════════════════════════════════════════════════════════════════

def build_red_team_cpn() -> CPNEngine:
    """
    Construct the CPN for the CLI / webhook pipeline (legacy mode).

    Same topology as the web CPN but uses local git operations
    and the HTTP-probing recon agent instead of source-code analysis.
    """
    from app.config import SANDBOX_MAX_RETRIES

    engine = CPNEngine()

    # ── Places ────────────────────────────────────────────────────────
    p_precon_pending = engine.add_place(
        PlaceName.PRECON_PENDING.value,
        description="Awaiting reconnaissance",
    )
    p_precon_done = engine.add_place(
        PlaceName.PRECON_DONE.value,
        description="Recon complete",
    )
    p_exploit_ready = engine.add_place(
        PlaceName.PEXPLOIT_READY.value,
        description="Ready for exploit generation",
    )
    p_exploit_done = engine.add_place(
        PlaceName.PEXPLOIT_DONE.value,
        description="Exploit executed",
    )

    p_patch_ready = engine.add_place(
        PlaceName.PPATCH_READY.value,
        description="Patch ready",
    )
    p_patch_done = engine.add_place(
        PlaceName.PPATCH_DONE.value,
        terminal=True,
        description="Pipeline success",
    )
    p_error = engine.add_place(
        PlaceName.PERROR.value,
        terminal=True,
        description="Terminal error",
    )

    # ── Transition Actions ────────────────────────────────────────────

    def _t1_recon(state: MasterState) -> Tuple[MasterState, str]:
        from app.agents.recon import run_recon
        target_url = state.webhook.target_url if state.webhook else ""
        recon = run_recon(target_url)
        state.recon = recon
        if len(recon.vulnerable_endpoints) > 0:
            return state, "vulns_found"
        return state, "clean"

    def _t2_route(state: MasterState) -> Tuple[MasterState, str]:
        if state.recon and len(state.recon.vulnerable_endpoints) > 0:
            return state, "vulns_found"
        return state, "clean"

    def _t3_exploit(state: MasterState) -> Tuple[MasterState, str]:
        from app.agents.exploiter import run_exploit
        exploit = run_exploit(state.recon)
        state.exploit = exploit
        return state, "ok"

    def _t4_verify(state: MasterState) -> Tuple[MasterState, str]:
        from app.agents.verifier import verify_exploit
        result = verify_exploit(state.exploit)
        state.verification = result
        if result.verified:
            return state, "verified"
        state.retry_count += 1
        if state.retry_count >= SANDBOX_MAX_RETRIES:
            state.error = f"Verification failed after {SANDBOX_MAX_RETRIES} retries"
            return state, "exhausted"
        return state, "retry"

    def _t5_patch(state: MasterState) -> Tuple[MasterState, str]:
        from app.agents.patcher import run_patch
        patch = run_patch(state.recon, state.exploit, state.verification, state.trace_id)
        state.patch = patch
        return state, "ok"

    # ── Register ──────────────────────────────────────────────────────

    engine.add_transition(
        "t1_recon", source=p_precon_pending,
        targets={"vulns_found": p_precon_done, "clean": p_error},
        action=_t1_recon,
        guard=lambda s: s.webhook is not None,
    )
    engine.add_transition(
        "t2_route", source=p_precon_done,
        targets={"vulns_found": p_exploit_ready, "clean": p_error},
        action=_t2_route,
        guard=lambda s: s.recon is not None,
    )
    engine.add_transition(
        "t3_exploit", source=p_exploit_ready,
        targets={"ok": p_exploit_done},
        action=_t3_exploit,
        guard=lambda s: s.recon is not None and len(s.recon.vulnerable_endpoints) > 0,
    )
    engine.add_transition(
        "t4_verify", source=p_exploit_done,
        targets={
            "verified": p_patch_ready,
            "retry": p_exploit_ready,
            "exhausted": p_error,
        },
        action=_t4_verify,
        guard=lambda s: s.exploit is not None,
    )
    engine.add_transition(
        "t5_patch", source=p_patch_ready,
        targets={"ok": p_patch_done},
        action=_t5_patch,
        guard=lambda s: s.verification is not None and s.verification.verified,
    )

    issues = engine.validate_net()
    if issues:
        for issue in issues:
            logger.warning("CPN validation: %s", issue)

    return engine
