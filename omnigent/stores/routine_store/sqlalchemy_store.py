"""SQLAlchemy-backed routine store."""

from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Any

from sqlalchemy import asc, select

from omnigent.db.db_models import SqlRoutine, SqlRoutineRun
from omnigent.db.utils import (
    get_or_create_engine,
    make_managed_session_maker,
    now_epoch,
)
from omnigent.entities import Routine, RoutineRun
from omnigent.stores.routine_store import RoutineStore


def _to_entity(row: SqlRoutine) -> Routine:
    """
    Convert a :class:`SqlRoutine` ORM row to a :class:`Routine` entity.

    :param row: The SQLAlchemy ORM row to convert.
    :returns: A :class:`Routine` dataclass instance.
    """
    return Routine(
        id=row.id,
        name=row.name,
        prompt=row.prompt,
        cron_expressions=json.loads(row.cron_expressions),
        target_kind=row.target_kind,
        agent_id=row.agent_id,
        owner_user_id=row.owner_user_id,
        timezone=row.timezone,
        created_at=row.created_at,
        host_id=row.host_id,
        workspace=row.workspace,
        harness_override=row.harness_override,
        model_override=row.model_override,
        reasoning_effort=row.reasoning_effort,
        enabled=bool(row.enabled),
        last_run_at=row.last_run_at,
        last_run_conversation_id=row.last_run_conversation_id,
        metadata=json.loads(row.routine_metadata) if row.routine_metadata else {},
        updated_at=row.updated_at,
    )


def _run_to_entity(row: SqlRoutineRun) -> RoutineRun:
    """
    Convert a :class:`SqlRoutineRun` ORM row to a :class:`RoutineRun`.

    :param row: The SQLAlchemy ORM row to convert.
    :returns: A :class:`RoutineRun` dataclass instance.
    """
    return RoutineRun(
        id=row.id,
        routine_id=row.routine_id,
        status=row.status,
        scheduled_at=row.scheduled_at,
        conversation_id=row.conversation_id,
        fired_at=row.fired_at,
        finished_at=row.finished_at,
        error=row.error,
    )


class SqlAlchemyRoutineStore(RoutineStore):
    """
    SQLAlchemy-backed implementation of :class:`RoutineStore`.

    Persists routines and their runs in a relational database via the
    SQLAlchemy ORM. ``cron_expressions`` and ``metadata`` are stored as
    JSON-encoded ``Text`` for SQLite compatibility.
    """

    def __init__(self, storage_location: str) -> None:
        """
        Initialize the SQLAlchemy routine store.

        Creates or reuses a SQLAlchemy engine and session factory for
        the given database URI.

        :param storage_location: SQLAlchemy database URI,
            e.g. ``"sqlite:///chat.db"``.
        """
        super().__init__(storage_location)
        self._engine = get_or_create_engine(storage_location)
        self._session = make_managed_session_maker(self._engine)

    # ── Routine methods ──────────────────────────────────────────

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
        """Insert a new routine.

        Raises ``IntegrityError`` if ``agent_id`` (or ``host_id``, when
        set) references a row that does not exist.
        """
        row = SqlRoutine(
            id=routine_id,
            name=name,
            prompt=prompt,
            cron_expressions=json.dumps(list(cron_expressions)),
            target_kind=target_kind,
            host_id=host_id,
            workspace=workspace,
            agent_id=agent_id,
            harness_override=harness_override,
            model_override=model_override,
            reasoning_effort=reasoning_effort,
            enabled=enabled,
            owner_user_id=owner_user_id,
            timezone=timezone,
            last_run_at=None,
            last_run_conversation_id=None,
            routine_metadata=json.dumps(metadata if metadata is not None else {}),
            created_at=now_epoch(),
            updated_at=None,
        )
        with self._session() as session:
            session.add(row)
            session.flush()
            return _to_entity(row)

    def get(self, routine_id: str) -> Routine | None:
        """Return the routine by ID, or ``None`` if not found."""
        with self._session() as session:
            row = session.get(SqlRoutine, routine_id)
            if row is None:
                return None
            return _to_entity(row)

    def list(self) -> Sequence[Routine]:
        """List all routines ordered by ``created_at ASC``."""
        with self._session() as session:
            stmt = select(SqlRoutine).order_by(asc(SqlRoutine.created_at), asc(SqlRoutine.id))
            rows = session.execute(stmt).scalars().all()
            return [_to_entity(r) for r in rows]

    def list_enabled(self) -> Sequence[Routine]:
        """List enabled routines ordered by ``created_at ASC``."""
        with self._session() as session:
            stmt = (
                select(SqlRoutine)
                .where(SqlRoutine.enabled.is_(True))
                .order_by(asc(SqlRoutine.created_at), asc(SqlRoutine.id))
            )
            rows = session.execute(stmt).scalars().all()
            return [_to_entity(r) for r in rows]

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
        """Update mutable fields. Returns ``None`` if not found.

        Uses ``None``-means-unchanged semantics for every keyword.
        """
        with self._session() as session:
            row = session.get(SqlRoutine, routine_id)
            if row is None:
                return None
            changed = False
            if name is not None and row.name != name:
                row.name = name
                changed = True
            if prompt is not None and row.prompt != prompt:
                row.prompt = prompt
                changed = True
            if cron_expressions is not None:
                encoded = json.dumps(list(cron_expressions))
                if row.cron_expressions != encoded:
                    row.cron_expressions = encoded
                    changed = True
            if target_kind is not None and row.target_kind != target_kind:
                row.target_kind = target_kind
                changed = True
            if host_id is not None and row.host_id != host_id:
                row.host_id = host_id
                changed = True
            if workspace is not None and row.workspace != workspace:
                row.workspace = workspace
                changed = True
            if harness_override is not None and row.harness_override != harness_override:
                row.harness_override = harness_override
                changed = True
            if model_override is not None and row.model_override != model_override:
                row.model_override = model_override
                changed = True
            if reasoning_effort is not None and row.reasoning_effort != reasoning_effort:
                row.reasoning_effort = reasoning_effort
                changed = True
            if enabled is not None and bool(row.enabled) != enabled:
                row.enabled = enabled
                changed = True
            if owner_user_id is not None and row.owner_user_id != owner_user_id:
                row.owner_user_id = owner_user_id
                changed = True
            if timezone is not None and row.timezone != timezone:
                row.timezone = timezone
                changed = True
            if last_run_at is not None and row.last_run_at != last_run_at:
                row.last_run_at = last_run_at
                changed = True
            if (
                last_run_conversation_id is not None
                and row.last_run_conversation_id != last_run_conversation_id
            ):
                row.last_run_conversation_id = last_run_conversation_id
                changed = True
            if metadata is not None:
                encoded = json.dumps(metadata)
                if row.routine_metadata != encoded:
                    row.routine_metadata = encoded
                    changed = True
            if changed:
                row.updated_at = now_epoch()
            session.flush()
            return _to_entity(row)

    def delete(self, routine_id: str) -> bool:
        """Delete a routine. Idempotent: returns ``False`` if not found."""
        with self._session() as session:
            row = session.get(SqlRoutine, routine_id)
            if row is None:
                return False
            session.delete(row)
            return True

    # ── Run methods ──────────────────────────────────────────────

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
        """Insert a new routine run.

        Raises ``IntegrityError`` if ``routine_id`` references a
        routine that does not exist.
        """
        row = SqlRoutineRun(
            id=run_id,
            routine_id=routine_id,
            conversation_id=conversation_id,
            status=status,
            scheduled_at=scheduled_at,
            fired_at=fired_at,
            finished_at=finished_at,
            error=error,
        )
        with self._session() as session:
            session.add(row)
            session.flush()
            return _run_to_entity(row)

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
        """Update mutable fields of a run. Returns ``None`` if not found.

        Uses ``None``-means-unchanged semantics for every keyword.
        """
        with self._session() as session:
            row = session.get(SqlRoutineRun, run_id)
            if row is None:
                return None
            if status is not None:
                row.status = status
            if conversation_id is not None:
                row.conversation_id = conversation_id
            if fired_at is not None:
                row.fired_at = fired_at
            if finished_at is not None:
                row.finished_at = finished_at
            if error is not None:
                row.error = error
            session.flush()
            return _run_to_entity(row)

    def list_runs(self, routine_id: str) -> Sequence[RoutineRun]:
        """List runs for a routine ordered by ``scheduled_at ASC``."""
        with self._session() as session:
            stmt = (
                select(SqlRoutineRun)
                .where(SqlRoutineRun.routine_id == routine_id)
                .order_by(asc(SqlRoutineRun.scheduled_at), asc(SqlRoutineRun.id))
            )
            rows = session.execute(stmt).scalars().all()
            return [_run_to_entity(r) for r in rows]
