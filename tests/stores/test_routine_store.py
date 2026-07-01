"""Tests for :class:`SqlAlchemyRoutineStore`.

Exercises routine CRUD (``create``, ``get``, ``list``, ``list_enabled``,
``update``, ``delete``) and run bookkeeping (``create_run``,
``update_run``, ``list_runs``) against a real SQLite database.
"""

from __future__ import annotations

import pytest
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError

from omnigent.db.utils import get_or_create_engine
from omnigent.stores.agent_store.sqlalchemy_store import SqlAlchemyAgentStore
from omnigent.stores.conversation_store.sqlalchemy_store import (
    SqlAlchemyConversationStore,
)
from omnigent.stores.routine_store.sqlalchemy_store import SqlAlchemyRoutineStore


@pytest.fixture()
def store(db_uri: str) -> SqlAlchemyRoutineStore:
    """A fresh :class:`SqlAlchemyRoutineStore` on the test SQLite DB.

    :param db_uri: Per-test SQLite URI from the root conftest fixture.
    :returns: A ready-to-use :class:`SqlAlchemyRoutineStore` instance.
    """
    return SqlAlchemyRoutineStore(db_uri)


@pytest.fixture()
def agent_id(db_uri: str) -> str:
    """Create a real agent row and return its ID.

    ``routines.agent_id`` has a NOT NULL FK to ``agents.id``, so a bare
    string would fail the FK check.

    :param db_uri: Per-test SQLite URI.
    :returns: An agent ID, e.g. ``"ag_test"``.
    """
    agent_store = SqlAlchemyAgentStore(db_uri)
    return agent_store.create(
        agent_id="ag_test",
        name="routine-agent",
        bundle_location="ag_test/deadbeef",
    ).id


@pytest.fixture()
def conversation_id(db_uri: str) -> str:
    """Create a real conversation row and return its ID.

    Used for the nullable ``last_run_conversation_id`` /
    ``routine_runs.conversation_id`` FKs.

    :param db_uri: Per-test SQLite URI.
    :returns: A conversation ID, e.g. ``"conv_abc123"``.
    """
    conv_store = SqlAlchemyConversationStore(db_uri)
    return conv_store.create_conversation().id


@pytest.fixture()
def host_id(db_uri: str) -> str:
    """Insert a host row directly and return its ``host_id``.

    ``routines.host_id`` has a nullable FK to ``hosts.host_id``; a
    host-target routine needs a real host to reference.

    :param db_uri: Per-test SQLite URI.
    :returns: The host's ``host_id``, e.g. ``"host_abc"``.
    """
    engine = get_or_create_engine(db_uri)
    with engine.begin() as conn:
        conn.execute(
            sa.text(
                "INSERT INTO hosts "
                "(owner, name, host_id, status, created_at, updated_at) "
                "VALUES (:o, :n, :hid, 'online', :ts, :ts)"
            ),
            {"o": "alice@test.com", "n": "laptop", "hid": "host_abc", "ts": 1700000000},
        )
    return "host_abc"


# ── create / get ────────────────────────────────────────────────────────────


def test_create_returns_routine_with_all_fields(
    store: SqlAlchemyRoutineStore,
    agent_id: str,
) -> None:
    """``create`` echoes every field back through the ORM without loss."""
    routine = store.create(
        routine_id="rt_1",
        name="nightly-audit",
        prompt="Audit the dependency tree.",
        cron_expressions=["0 9 * * 1-5", "0 18 * * 5"],
        target_kind="sandbox",
        agent_id=agent_id,
        owner_user_id="alice@example.com",
        timezone="America/New_York",
        harness_override="pi",
        model_override="claude-opus-4-8",
        reasoning_effort="high",
        metadata={"team": "infra"},
    )

    assert routine.id == "rt_1"
    assert routine.name == "nightly-audit"
    assert routine.prompt == "Audit the dependency tree."
    assert routine.cron_expressions == ["0 9 * * 1-5", "0 18 * * 5"]
    assert routine.target_kind == "sandbox"
    assert routine.agent_id == agent_id
    assert routine.owner_user_id == "alice@example.com"
    assert routine.timezone == "America/New_York"
    assert routine.harness_override == "pi"
    assert routine.model_override == "claude-opus-4-8"
    assert routine.reasoning_effort == "high"
    assert routine.metadata == {"team": "infra"}
    assert routine.enabled is True
    assert routine.host_id is None
    assert routine.workspace is None
    assert routine.last_run_at is None
    assert routine.last_run_conversation_id is None
    assert routine.created_at > 0
    assert routine.updated_at is None


def test_create_defaults(
    store: SqlAlchemyRoutineStore,
    agent_id: str,
) -> None:
    """Omitting optionals yields enabled=True, empty metadata, no overrides."""
    routine = store.create(
        routine_id="rt_defaults",
        name="minimal",
        prompt="hi",
        cron_expressions=[],
        target_kind="sandbox",
        agent_id=agent_id,
        owner_user_id="bob@example.com",
        timezone="UTC",
    )
    assert routine.enabled is True
    assert routine.metadata == {}
    assert routine.cron_expressions == []
    assert routine.harness_override is None
    assert routine.model_override is None
    assert routine.reasoning_effort is None


def test_create_host_target_routine(
    store: SqlAlchemyRoutineStore,
    agent_id: str,
    host_id: str,
) -> None:
    """A ``host`` target routine persists its ``host_id`` and workspace."""
    routine = store.create(
        routine_id="rt_host",
        name="on-host",
        prompt="run here",
        cron_expressions=["0 * * * *"],
        target_kind="host",
        agent_id=agent_id,
        owner_user_id="alice@example.com",
        timezone="UTC",
        host_id=host_id,
        workspace="/home/alice/project",
    )
    assert routine.target_kind == "host"
    assert routine.host_id == host_id
    assert routine.workspace == "/home/alice/project"


def test_create_rejects_bad_target_kind(
    store: SqlAlchemyRoutineStore,
    agent_id: str,
) -> None:
    """The ``ck_routines_target_kind`` check blocks unknown target kinds."""
    with pytest.raises(IntegrityError):
        store.create(
            routine_id="rt_bad",
            name="bad",
            prompt="x",
            cron_expressions=[],
            target_kind="martian",
            agent_id=agent_id,
            owner_user_id="alice@example.com",
            timezone="UTC",
        )


def test_create_rejects_unknown_agent(store: SqlAlchemyRoutineStore) -> None:
    """The ``agent_id`` FK rejects a routine bound to a missing agent."""
    with pytest.raises(IntegrityError):
        store.create(
            routine_id="rt_noagent",
            name="orphan",
            prompt="x",
            cron_expressions=[],
            target_kind="sandbox",
            agent_id="ag_does_not_exist",
            owner_user_id="alice@example.com",
            timezone="UTC",
        )


def test_get_returns_none_for_missing(store: SqlAlchemyRoutineStore) -> None:
    """``get`` returns ``None`` for an unknown id."""
    assert store.get("rt_missing") is None


def test_get_round_trips(store: SqlAlchemyRoutineStore, agent_id: str) -> None:
    """A created routine is retrievable by id with matching fields."""
    store.create(
        routine_id="rt_rt",
        name="round-trip",
        prompt="p",
        cron_expressions=["*/5 * * * *"],
        target_kind="sandbox",
        agent_id=agent_id,
        owner_user_id="alice@example.com",
        timezone="UTC",
    )
    got = store.get("rt_rt")
    assert got is not None
    assert got.name == "round-trip"
    assert got.cron_expressions == ["*/5 * * * *"]


# ── list / list_enabled ──────────────────────────────────────────────────────


def _make(store: SqlAlchemyRoutineStore, agent_id: str, rid: str, name: str) -> None:
    """Create a minimal sandbox routine (test helper)."""
    store.create(
        routine_id=rid,
        name=name,
        prompt="p",
        cron_expressions=[],
        target_kind="sandbox",
        agent_id=agent_id,
        owner_user_id="alice@example.com",
        timezone="UTC",
    )


def test_list_returns_all_ordered(
    store: SqlAlchemyRoutineStore,
    agent_id: str,
) -> None:
    """``list`` returns every routine ordered by (created_at, id)."""
    _make(store, agent_id, "rt_a", "a")
    _make(store, agent_id, "rt_b", "b")
    _make(store, agent_id, "rt_c", "c")
    ids = [r.id for r in store.list()]
    assert ids == ["rt_a", "rt_b", "rt_c"]


def test_list_enabled_filters_disabled(
    store: SqlAlchemyRoutineStore,
    agent_id: str,
) -> None:
    """``list_enabled`` returns only enabled routines; ``list`` returns all."""
    _make(store, agent_id, "rt_on1", "on1")
    _make(store, agent_id, "rt_off", "off")
    _make(store, agent_id, "rt_on2", "on2")

    store.update("rt_off", enabled=False)

    all_ids = {r.id for r in store.list()}
    enabled_ids = {r.id for r in store.list_enabled()}

    assert all_ids == {"rt_on1", "rt_off", "rt_on2"}
    assert enabled_ids == {"rt_on1", "rt_on2"}
    assert "rt_off" not in enabled_ids
    assert all(r.enabled for r in store.list_enabled())


def test_list_empty(store: SqlAlchemyRoutineStore) -> None:
    """Both listings return an empty list when nothing is stored."""
    assert store.list() == []
    assert store.list_enabled() == []


# ── update ───────────────────────────────────────────────────────────────────


def test_update_mutates_fields_and_stamps_updated_at(
    store: SqlAlchemyRoutineStore,
    agent_id: str,
) -> None:
    """``update`` writes changed fields and stamps ``updated_at``."""
    store.create(
        routine_id="rt_u",
        name="before",
        prompt="before-prompt",
        cron_expressions=["0 0 * * *"],
        target_kind="sandbox",
        agent_id=agent_id,
        owner_user_id="alice@example.com",
        timezone="UTC",
    )
    updated = store.update(
        "rt_u",
        name="after",
        prompt="after-prompt",
        cron_expressions=["0 12 * * *"],
        timezone="America/Los_Angeles",
        metadata={"k": "v"},
    )
    assert updated is not None
    assert updated.name == "after"
    assert updated.prompt == "after-prompt"
    assert updated.cron_expressions == ["0 12 * * *"]
    assert updated.timezone == "America/Los_Angeles"
    assert updated.metadata == {"k": "v"}
    assert updated.updated_at is not None


def test_update_none_means_unchanged(
    store: SqlAlchemyRoutineStore,
    agent_id: str,
) -> None:
    """Omitted keywords leave fields (and ``updated_at``) untouched."""
    store.create(
        routine_id="rt_noop",
        name="keep",
        prompt="keep",
        cron_expressions=["0 0 * * *"],
        target_kind="sandbox",
        agent_id=agent_id,
        owner_user_id="alice@example.com",
        timezone="UTC",
    )
    result = store.update("rt_noop")
    assert result is not None
    assert result.name == "keep"
    assert result.updated_at is None


def test_update_records_last_run(
    store: SqlAlchemyRoutineStore,
    agent_id: str,
    conversation_id: str,
) -> None:
    """``last_run_at`` / ``last_run_conversation_id`` persist via update."""
    store.create(
        routine_id="rt_lr",
        name="lr",
        prompt="p",
        cron_expressions=[],
        target_kind="sandbox",
        agent_id=agent_id,
        owner_user_id="alice@example.com",
        timezone="UTC",
    )
    updated = store.update(
        "rt_lr",
        last_run_at=1700001234,
        last_run_conversation_id=conversation_id,
    )
    assert updated is not None
    assert updated.last_run_at == 1700001234
    assert updated.last_run_conversation_id == conversation_id


def test_update_returns_none_for_missing(store: SqlAlchemyRoutineStore) -> None:
    """``update`` on an unknown id returns ``None``."""
    assert store.update("rt_missing", name="x") is None


# ── delete ───────────────────────────────────────────────────────────────────


def test_delete_removes_routine(store: SqlAlchemyRoutineStore, agent_id: str) -> None:
    """``delete`` removes the routine and is idempotent."""
    _make(store, agent_id, "rt_del", "del")
    assert store.delete("rt_del") is True
    assert store.get("rt_del") is None
    assert store.delete("rt_del") is False


def test_delete_cascades_runs(store: SqlAlchemyRoutineStore, agent_id: str) -> None:
    """Deleting a routine cascades to its runs (FK ON DELETE CASCADE)."""
    _make(store, agent_id, "rt_casc", "casc")
    store.create_run("rr_c1", "rt_casc", status="scheduled", scheduled_at=1700000000)
    assert len(store.list_runs("rt_casc")) == 1

    assert store.delete("rt_casc") is True
    assert store.list_runs("rt_casc") == []


# ── runs ─────────────────────────────────────────────────────────────────────


def test_create_run_returns_fields(
    store: SqlAlchemyRoutineStore,
    agent_id: str,
) -> None:
    """``create_run`` echoes its fields back."""
    _make(store, agent_id, "rt_run", "run")
    run = store.create_run(
        "rr_1",
        "rt_run",
        status="scheduled",
        scheduled_at=1700000000,
    )
    assert run.id == "rr_1"
    assert run.routine_id == "rt_run"
    assert run.status == "scheduled"
    assert run.scheduled_at == 1700000000
    assert run.conversation_id is None
    assert run.fired_at is None
    assert run.finished_at is None
    assert run.error is None


def test_create_run_rejects_bad_status(
    store: SqlAlchemyRoutineStore,
    agent_id: str,
) -> None:
    """The ``ck_routine_runs_status`` check blocks unknown statuses."""
    _make(store, agent_id, "rt_badrun", "badrun")
    with pytest.raises(IntegrityError):
        store.create_run(
            "rr_bad",
            "rt_badrun",
            status="exploded",
            scheduled_at=1700000000,
        )


def test_create_run_rejects_unknown_routine(store: SqlAlchemyRoutineStore) -> None:
    """The ``routine_id`` FK rejects a run for a missing routine."""
    with pytest.raises(IntegrityError):
        store.create_run(
            "rr_orphan",
            "rt_missing",
            status="scheduled",
            scheduled_at=1700000000,
        )


def test_update_run_lifecycle(
    store: SqlAlchemyRoutineStore,
    agent_id: str,
    conversation_id: str,
) -> None:
    """``update_run`` advances status and records timestamps/conversation."""
    _make(store, agent_id, "rt_life", "life")
    store.create_run("rr_life", "rt_life", status="scheduled", scheduled_at=1700000000)

    running = store.update_run(
        "rr_life",
        status="running",
        conversation_id=conversation_id,
        fired_at=1700000001,
    )
    assert running is not None
    assert running.status == "running"
    assert running.conversation_id == conversation_id
    assert running.fired_at == 1700000001

    done = store.update_run("rr_life", status="succeeded", finished_at=1700000050)
    assert done is not None
    assert done.status == "succeeded"
    assert done.finished_at == 1700000050
    # Earlier-set fields are untouched by the second update.
    assert done.conversation_id == conversation_id
    assert done.fired_at == 1700000001


def test_update_run_returns_none_for_missing(store: SqlAlchemyRoutineStore) -> None:
    """``update_run`` on an unknown id returns ``None``."""
    assert store.update_run("rr_missing", status="failed") is None


def test_list_runs_orders_by_scheduled_at(
    store: SqlAlchemyRoutineStore,
    agent_id: str,
) -> None:
    """``list_runs`` returns a routine's runs ordered by ``scheduled_at``."""
    _make(store, agent_id, "rt_lst", "lst")
    _make(store, agent_id, "rt_other", "other")
    store.create_run("rr_b", "rt_lst", status="scheduled", scheduled_at=200)
    store.create_run("rr_a", "rt_lst", status="scheduled", scheduled_at=100)
    store.create_run("rr_c", "rt_lst", status="scheduled", scheduled_at=300)
    # A run on a different routine must not leak into the listing.
    store.create_run("rr_x", "rt_other", status="scheduled", scheduled_at=150)

    ids = [r.id for r in store.list_runs("rt_lst")]
    assert ids == ["rr_a", "rr_b", "rr_c"]


def test_list_runs_empty_for_routine_without_runs(
    store: SqlAlchemyRoutineStore,
    agent_id: str,
) -> None:
    """``list_runs`` returns an empty list when the routine has no runs."""
    _make(store, agent_id, "rt_norun", "norun")
    assert store.list_runs("rt_norun") == []
