"""Compatibility checks for repairing older SQLite schemas in place."""

from __future__ import annotations

import sqlite3

import pytest
from sqlalchemy.ext.asyncio import create_async_engine

import db.database as database


@pytest.mark.anyio
async def test_ensure_ai_strategy_schema_repairs_existing_sqlite_db(tmp_path):
    db_path = tmp_path / "legacy-ai-schema.db"
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(
            """
            CREATE TABLE strategies (
                id INTEGER PRIMARY KEY,
                name VARCHAR(255)
            );

            CREATE TABLE strategy_templates (
                id INTEGER PRIMARY KEY,
                name VARCHAR(255)
            );

            CREATE TABLE cerberus_bots (
                id VARCHAR(36) PRIMARY KEY,
                user_id INTEGER,
                name VARCHAR(255)
            );
            """
        )
        conn.commit()
    finally:
        conn.close()

    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")
    old_engine = database._engine
    old_factory = database._async_session_factory
    database._engine = engine
    database._async_session_factory = None

    try:
        await database._ensure_ai_strategy_schema()
    finally:
        database._engine = old_engine
        database._async_session_factory = old_factory
        await engine.dispose()

    conn = sqlite3.connect(db_path)
    try:
        strategy_columns = {
            row[1] for row in conn.execute("PRAGMA table_info(strategies)").fetchall()
        }
        template_columns = {
            row[1] for row in conn.execute("PRAGMA table_info(strategy_templates)").fetchall()
        }
        bot_columns = {
            row[1] for row in conn.execute("PRAGMA table_info(cerberus_bots)").fetchall()
        }
        optimization_table = conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'cerberus_bot_optimization_runs'"
        ).fetchone()
    finally:
        conn.close()

    assert {"strategy_type", "source_prompt", "ai_context"} <= strategy_columns
    assert {"strategy_type", "source_prompt", "ai_context"} <= template_columns
    assert {"learning_enabled", "learning_status_json", "last_optimization_at"} <= bot_columns
    assert optimization_table is not None
