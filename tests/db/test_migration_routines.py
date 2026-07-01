"""Tests for the ``routines`` / ``routine_runs`` migration.

Drives Alembic directly on a fresh temp SQLite database — ``upgrade
head`` must create both tables, and downgrading one step must drop
them again. This exercises both legs of the migration
(``o1a2b3c4d5e6``) independently of the ``get_or_create_engine``
fixtures elsewhere, which only ever run ``upgrade head``.
"""

from __future__ import annotations

import warnings
from pathlib import Path

import sqlalchemy as sa
from alembic import command
from alembic.config import Config

import omnigent.db

_ROUTINE_TABLES = {"routines", "routine_runs"}


def _alembic_config(uri: str) -> Config:
    """Build an Alembic config pointed at the real script tree + *uri*.

    :param uri: SQLite URL the migrations run against.
    :returns: A configured :class:`alembic.config.Config`.
    """
    config = Config()
    config.set_main_option(
        "script_location", str(Path(omnigent.db.__file__).parent / "migrations")
    )
    config.set_main_option("sqlalchemy.url", uri)
    return config


def test_upgrade_creates_then_downgrade_drops(tmp_path: Path) -> None:
    """``upgrade head`` creates both tables; ``downgrade -1`` drops them.

    A failure on the upgrade leg means the tables never landed — every
    routine read/write would crash. A failure on the downgrade leg means
    the migration is irreversible, which blocks a clean rollback.
    """
    uri = f"sqlite:///{tmp_path / 'routines.db'}"
    config = _alembic_config(uri)

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        command.upgrade(config, "head")

    engine = sa.create_engine(uri)
    try:
        tables = set(sa.inspect(engine).get_table_names())
        assert tables >= _ROUTINE_TABLES, (
            f"upgrade head did not create {_ROUTINE_TABLES - tables}; "
            f"tables present: {sorted(tables)}"
        )

        # Columns and indexes match what the store/ORM expect.
        routine_cols = {c["name"] for c in sa.inspect(engine).get_columns("routines")}
        assert {"id", "cron_expressions", "target_kind", "agent_id", "metadata"} <= (
            routine_cols
        ), f"routines missing expected columns; got {sorted(routine_cols)}"
        run_cols = {c["name"] for c in sa.inspect(engine).get_columns("routine_runs")}
        assert {"id", "routine_id", "status", "scheduled_at"} <= run_cols, (
            f"routine_runs missing expected columns; got {sorted(run_cols)}"
        )
        run_index_names = {ix["name"] for ix in sa.inspect(engine).get_indexes("routine_runs")}
        assert "ix_routine_runs_routine_id" in run_index_names, (
            f"expected ix_routine_runs_routine_id; got {sorted(run_index_names)}"
        )
    finally:
        engine.dispose()

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        command.downgrade(config, "-1")

    engine = sa.create_engine(uri)
    try:
        tables = set(sa.inspect(engine).get_table_names())
        assert not (_ROUTINE_TABLES & tables), (
            f"downgrade should have dropped {_ROUTINE_TABLES}; "
            f"still present: {_ROUTINE_TABLES & tables}"
        )
    finally:
        engine.dispose()


def test_full_chain_round_trips_with_routines(tmp_path: Path) -> None:
    """The whole chain reaches head and ``routines`` survives at head.

    Complements the single-step test by proving the new revision slots
    into the existing chain (``upgrade head`` → ``downgrade base`` →
    ``upgrade head``) without breaking reversibility.
    """
    uri = f"sqlite:///{tmp_path / 'chain.db'}"
    config = _alembic_config(uri)

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        command.upgrade(config, "head")
        command.downgrade(config, "base")
        command.upgrade(config, "head")

    engine = sa.create_engine(uri)
    try:
        tables = set(sa.inspect(engine).get_table_names())
        assert tables >= _ROUTINE_TABLES, (
            f"routines tables missing after chain round-trip; present: {sorted(tables)}"
        )
    finally:
        engine.dispose()
