"""Routine entities — persisted in the ``routines`` and
``routine_runs`` tables.

A :class:`Routine` is a saved, schedulable agent invocation (prompt +
launch context + cron expressions); a :class:`RoutineRun` records one
firing of a routine. This module is the persistence foundation only —
nothing at runtime dispatches these yet.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Routine:
    """
    A routine persisted in the ``routines`` table.

    :param id: Opaque primary key, prefix ``"rt_"``,
        e.g. ``"rt_a1b2c3..."``.
    :param name: Human-readable routine name.
    :param prompt: The prompt sent to the agent on each run.
    :param cron_expressions: List of cron expression strings, e.g.
        ``["0 9 * * 1-5"]``.
    :param target_kind: Where the run executes: ``"sandbox"`` or
        ``"host"``.
    :param agent_id: The agent bound to this routine.
    :param owner_user_id: User ID of the routine owner, e.g.
        ``"alice@example.com"``.
    :param timezone: IANA timezone name the cron expressions are
        evaluated in, e.g. ``"America/New_York"``.
    :param created_at: Unix epoch seconds at row creation.
    :param host_id: Host the run targets when ``target_kind="host"``,
        else ``None``.
    :param workspace: Absolute path on the target where the runner
        starts, or ``None`` when not pinned.
    :param harness_override: Per-routine brain-harness override, or
        ``None`` to use the agent default.
    :param model_override: Per-routine LLM model override, or ``None``
        to use the agent default.
    :param reasoning_effort: Per-routine reasoning-effort hint, or
        ``None`` to use the agent default.
    :param enabled: Whether the scheduler should consult this routine.
        Defaults to ``True``.
    :param last_run_at: Unix epoch seconds of the most recent run, or
        ``None`` if it has never run.
    :param last_run_conversation_id: Conversation ID of the most recent
        run, or ``None`` until the first run.
    :param metadata: Free-form metadata dict, defaults to ``{}``.
    :param updated_at: Unix epoch seconds of the last write, or ``None``
        if the row has never been updated.
    """

    id: str
    name: str
    prompt: str
    cron_expressions: list[str]
    target_kind: str
    agent_id: str
    owner_user_id: str
    timezone: str
    created_at: int
    host_id: str | None = None
    workspace: str | None = None
    harness_override: str | None = None
    model_override: str | None = None
    reasoning_effort: str | None = None
    enabled: bool = True
    last_run_at: int | None = None
    last_run_conversation_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    updated_at: int | None = None


@dataclass
class RoutineRun:
    """
    A single firing of a :class:`Routine`, persisted in the
    ``routine_runs`` table.

    :param id: Opaque primary key, prefix ``"rr_"``,
        e.g. ``"rr_a1b2c3..."``.
    :param routine_id: The routine this run belongs to.
    :param status: Lifecycle state: ``"scheduled"``, ``"running"``,
        ``"succeeded"``, ``"failed"``, or ``"skipped"``.
    :param scheduled_at: Unix epoch seconds of the schedule slot this
        run corresponds to.
    :param conversation_id: Conversation the run drove, or ``None``
        until dispatched.
    :param fired_at: Unix epoch seconds the run started, or ``None`` if
        not yet started.
    :param finished_at: Unix epoch seconds the run finished, or ``None``
        if still in flight.
    :param error: Free-text error detail when ``status="failed"``, else
        ``None``.
    """

    id: str
    routine_id: str
    status: str
    scheduled_at: int
    conversation_id: str | None = None
    fired_at: int | None = None
    finished_at: int | None = None
    error: str | None = None
