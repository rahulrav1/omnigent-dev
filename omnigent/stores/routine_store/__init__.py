"""Routine store — manages routines and their runs via a CRUD API.

A routine is a saved, schedulable agent invocation (prompt + launch
context + cron expressions); a routine run records one firing. This is
the persistence foundation only — nothing at runtime dispatches these
rows yet.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence
from typing import Any

from omnigent.entities import Routine, RoutineRun


class RoutineStore(ABC):
    """
    Abstract base for routine persistence.

    Manages the lifecycle of routines (:meth:`create`, :meth:`get`,
    :meth:`list`, :meth:`list_enabled`, :meth:`update`, :meth:`delete`)
    and their runs (:meth:`create_run`, :meth:`update_run`,
    :meth:`list_runs`).

    Mutating helpers use ``None``-means-unchanged semantics: a keyword
    left at its ``None`` default is not written, mirroring the existing
    store convention (see :class:`PolicyStore`).
    """

    def __init__(self, storage_location: str) -> None:
        """
        Initialize the routine store.

        :param storage_location: Backend-specific storage URI,
            e.g. ``"sqlite:///chat.db"`` for SQLAlchemy.
        """
        self.storage_location = storage_location

    # ── Routine methods ──────────────────────────────────────────

    @abstractmethod
    def create(
        self,
        routine_id: str,
        name: str,
        prompt: str,
        cron_expressions: Sequence[str],
        target_kind: str,
        agent_id: str,
        owner_user_id: str,
        timezone: str,
        *,
        host_id: str | None = None,
        workspace: str | None = None,
        harness_override: str | None = None,
        model_override: str | None = None,
        reasoning_effort: str | None = None,
        enabled: bool = True,
        metadata: dict[str, Any] | None = None,
    ) -> Routine:
        """
        Insert a new routine.

        :param routine_id: Pre-generated unique routine identifier,
            e.g. ``"rt_a1b2c3..."``.
        :param name: Human-readable routine name.
        :param prompt: The prompt sent to the agent on each run.
        :param cron_expressions: List of cron expression strings.
        :param target_kind: ``"sandbox"`` or ``"host"``.
        :param agent_id: The agent bound to this routine (FK).
        :param owner_user_id: User ID of the routine owner.
        :param timezone: IANA timezone name for the cron expressions.
        :param host_id: Host to target when ``target_kind="host"``.
        :param workspace: Absolute path the runner starts in.
        :param harness_override: Per-routine brain-harness override.
        :param model_override: Per-routine LLM model override.
        :param reasoning_effort: Per-routine reasoning-effort hint.
        :param enabled: Whether the scheduler consults this routine.
        :param metadata: Free-form metadata dict; defaults to ``{}``.
        :returns: The newly created :class:`Routine`.
        """
        ...

    @abstractmethod
    def get(self, routine_id: str) -> Routine | None:
        """
        Return a routine by ID.

        :param routine_id: Opaque routine identifier.
        :returns: The :class:`Routine` if found, else ``None``.
        """
        ...

    @abstractmethod
    def list(self) -> Sequence[Routine]:
        """
        List all routines, ordered by ``created_at ASC``.

        :returns: List of :class:`Routine` instances.
        """
        ...

    @abstractmethod
    def list_enabled(self) -> Sequence[Routine]:
        """
        List routines with ``enabled=True``, ordered by
        ``created_at ASC``.

        :returns: List of enabled :class:`Routine` instances.
        """
        ...

    @abstractmethod
    def update(
        self,
        routine_id: str,
        *,
        name: str | None = None,
        prompt: str | None = None,
        cron_expressions: Sequence[str] | None = None,
        target_kind: str | None = None,
        host_id: str | None = None,
        workspace: str | None = None,
        harness_override: str | None = None,
        model_override: str | None = None,
        reasoning_effort: str | None = None,
        enabled: bool | None = None,
        owner_user_id: str | None = None,
        timezone: str | None = None,
        last_run_at: int | None = None,
        last_run_conversation_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Routine | None:
        """
        Update mutable fields of a routine.

        Uses ``None``-means-unchanged semantics for every keyword.
        ``agent_id`` is immutable and not accepted here. Returns
        ``None`` if the routine does not exist.

        :param routine_id: Opaque routine identifier.
        :returns: The updated :class:`Routine`, or ``None``.
        """
        ...

    @abstractmethod
    def delete(self, routine_id: str) -> bool:
        """
        Delete a routine (and, by cascade, its runs). Idempotent.

        :param routine_id: Opaque routine identifier.
        :returns: ``True`` if removed; ``False`` if not found.
        """
        ...

    # ── Run methods ──────────────────────────────────────────────

    @abstractmethod
    def create_run(
        self,
        run_id: str,
        routine_id: str,
        status: str,
        scheduled_at: int,
        *,
        conversation_id: str | None = None,
        fired_at: int | None = None,
        finished_at: int | None = None,
        error: str | None = None,
    ) -> RoutineRun:
        """
        Insert a new routine run.

        :param run_id: Pre-generated unique run identifier,
            e.g. ``"rr_a1b2c3..."``.
        :param routine_id: The routine this run belongs to (FK).
        :param status: One of ``"scheduled"``, ``"running"``,
            ``"succeeded"``, ``"failed"``, ``"skipped"``.
        :param scheduled_at: Unix epoch seconds of the schedule slot.
        :param conversation_id: Conversation the run drives, if known.
        :param fired_at: Unix epoch seconds the run started.
        :param finished_at: Unix epoch seconds the run finished.
        :param error: Error detail when ``status="failed"``.
        :returns: The newly created :class:`RoutineRun`.
        """
        ...

    @abstractmethod
    def update_run(
        self,
        run_id: str,
        *,
        status: str | None = None,
        conversation_id: str | None = None,
        fired_at: int | None = None,
        finished_at: int | None = None,
        error: str | None = None,
    ) -> RoutineRun | None:
        """
        Update mutable fields of a run.

        Uses ``None``-means-unchanged semantics. Returns ``None`` if the
        run does not exist.

        :param run_id: Opaque run identifier.
        :returns: The updated :class:`RoutineRun`, or ``None``.
        """
        ...

    @abstractmethod
    def list_runs(self, routine_id: str) -> Sequence[RoutineRun]:
        """
        List runs for a routine, ordered by ``scheduled_at ASC``.

        :param routine_id: The routine whose runs to return.
        :returns: List of :class:`RoutineRun` instances.
        """
        ...
