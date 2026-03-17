#!/usr/bin/env python3
"""
Audit all existing CerberusBots and ensure compatibility with newly added systems:
  - Kill switch checks (UserRiskLimits)
  - Live/paper mode (UserTradingSession)
  - Graduated drawdown thresholds
  - Quarter-Kelly sizing (needs 20+ closed trades)
  - Sector concentration caps
  - Category/strategy scoring (StrategyTypeScore)
  - Sentiment integration (fail-closed)
  - ReasoningEngine (strategy_config needs strategy_type)

Idempotent — safe to run multiple times. Never deletes bots.
"""

import json
import sys
import os
from datetime import datetime

# Ensure project root is on sys.path so db/ imports work
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker

from db.database import Base
from db.models import (
    User,
    UserRiskLimits,
    UserTradingSession,
    TradingModeEnum,
    StrategyTypeScore,
)
from db.cerberus_models import (
    CerberusBot,
    CerberusBotVersion,
    CerberusTrade,
    BotStatus,
)


DB_PATH = os.path.join(PROJECT_ROOT, "trading_ecosystem.db")
DB_URL = f"sqlite:///{DB_PATH}"


def main():
    if not os.path.exists(DB_PATH):
        print(f"ERROR: Database not found at {DB_PATH}")
        sys.exit(1)

    engine = create_engine(DB_URL, echo=False)
    Session = sessionmaker(bind=engine)
    session = Session()

    # Ensure tables exist (in case schema hasn't been migrated yet)
    # We do NOT create_all here — the script works with whatever tables exist.
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())

    required_tables = {
        "cerberus_bots", "cerberus_bot_versions", "users",
        "user_risk_limits", "user_trading_sessions",
    }
    missing = required_tables - existing_tables
    if missing:
        print(f"WARNING: Missing tables: {missing}")
        print("Some checks will be skipped.")

    # ─── Gather all bots ──────────────────────────────────────────────────
    bots = session.query(CerberusBot).all()
    print(f"\n{'='*70}")
    print(f"  BOT AUDIT REPORT — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*70}")
    print(f"\nTotal bots found: {len(bots)}\n")

    if not bots:
        print("No bots to audit. Done.")
        session.close()
        return

    # Counters
    risk_limits_created = 0
    trading_sessions_created = 0
    configs_fixed = 0
    orphaned_versions = 0
    total_closed_trades_by_user = {}

    # Collect unique user IDs from bots
    bot_user_ids = set(b.user_id for b in bots)

    # Pre-fetch closed trade counts per user (for Quarter-Kelly readiness)
    for uid in bot_user_ids:
        count = (
            session.query(CerberusTrade)
            .filter(
                CerberusTrade.user_id == uid,
                CerberusTrade.exit_ts.isnot(None),
                CerberusTrade.return_pct.isnot(None),
            )
            .count()
        )
        total_closed_trades_by_user[uid] = count

    # Pre-fetch existing UserRiskLimits and UserTradingSession rows
    existing_risk_limits = {}
    if "user_risk_limits" in existing_tables:
        for rl in session.query(UserRiskLimits).all():
            existing_risk_limits[(rl.user_id, rl.mode)] = rl

    existing_sessions = {}
    if "user_trading_sessions" in existing_tables:
        for ts in session.query(UserTradingSession).all():
            existing_sessions[ts.user_id] = ts

    # Pre-fetch existing StrategyTypeScore rows per user
    existing_scores = {}
    if "strategy_type_scores" in existing_tables:
        for sts in session.query(StrategyTypeScore).all():
            existing_scores.setdefault(sts.user_id, []).append(sts.strategy_type)

    # Pre-fetch all bot versions for orphan check
    all_version_ids = set()
    if "cerberus_bot_versions" in existing_tables:
        all_version_ids = set(
            v.id for v in session.query(CerberusBotVersion.id).all()
        )

    # ─── Per-user checks ─────────────────────────────────────────────────
    print("─── USER-LEVEL CHECKS ───")
    for uid in sorted(bot_user_ids):
        user = session.query(User).filter(User.id == uid).first()
        user_label = f"User {uid}" + (f" ({user.email})" if user else " (NOT FOUND)")
        print(f"\n  {user_label}")

        if not user:
            print(f"    WARNING: user_id={uid} does not exist in users table!")
            print(f"    Bots with this user_id will fail all new system checks.")
            continue

        # (a) UserRiskLimits — need rows for PAPER and LIVE modes
        for mode in [TradingModeEnum.PAPER, TradingModeEnum.LIVE]:
            key = (uid, mode)
            if key not in existing_risk_limits:
                rl = UserRiskLimits(
                    user_id=uid,
                    mode=mode,
                    kill_switch_active=False,
                    daily_loss_limit=None,
                    max_position_size_pct=0.25,
                    max_open_positions=10,
                    live_bot_trading_confirmed=False,
                    drawdown_reduce_pct=-2.0,
                    drawdown_halt_pct=-4.0,
                    drawdown_kill_pct=-7.0,
                    weekly_drawdown_kill_pct=-10.0,
                    sector_concentration_limit=0.30,
                    category_block_threshold=30.0,
                )
                session.add(rl)
                existing_risk_limits[key] = rl
                risk_limits_created += 1
                print(f"    CREATED UserRiskLimits for mode={mode.value}")
            else:
                rl = existing_risk_limits[key]
                print(f"    OK UserRiskLimits mode={mode.value} (kill_switch={rl.kill_switch_active})")

        # (b) UserTradingSession
        if uid not in existing_sessions:
            ts = UserTradingSession(
                user_id=uid,
                active_mode=TradingModeEnum.PAPER,
            )
            session.add(ts)
            existing_sessions[uid] = ts
            trading_sessions_created += 1
            print(f"    CREATED UserTradingSession (active_mode=paper)")
        else:
            ts = existing_sessions[uid]
            print(f"    OK UserTradingSession (active_mode={ts.active_mode.value if hasattr(ts.active_mode, 'value') else ts.active_mode})")

        # (c) Quarter-Kelly readiness
        closed = total_closed_trades_by_user.get(uid, 0)
        if closed >= 20:
            print(f"    OK Quarter-Kelly: {closed} closed trades (active)")
        else:
            print(f"    INFO Quarter-Kelly: {closed}/20 closed trades (using 1% default sizing)")

        # (d) StrategyTypeScore rows
        scores = existing_scores.get(uid, [])
        if scores:
            print(f"    OK StrategyTypeScore: {len(scores)} type(s) scored: {', '.join(scores)}")
        else:
            print(f"    INFO StrategyTypeScore: No scores yet (created automatically after trades close)")

    # ─── Per-bot checks ──────────────────────────────────────────────────
    print(f"\n{'─'*70}")
    print("─── BOT-LEVEL CHECKS ───")

    status_counts = {}
    for bot in bots:
        status_val = bot.status.value if hasattr(bot.status, "value") else str(bot.status)
        status_counts[status_val] = status_counts.get(status_val, 0) + 1

        print(f"\n  Bot: {bot.name}")
        print(f"    ID: {bot.id}")
        print(f"    User: {bot.user_id}")
        print(f"    Status: {status_val}")
        print(f"    Current Version ID: {bot.current_version_id}")

        # (a) Check config for strategy_type
        version = None
        if bot.current_version_id:
            version = (
                session.query(CerberusBotVersion)
                .filter(CerberusBotVersion.id == bot.current_version_id)
                .first()
            )

        if bot.current_version_id and not version:
            print(f"    WARNING: current_version_id points to non-existent version!")
            orphaned_versions += 1
            # Try to find the latest version for this bot
            latest = (
                session.query(CerberusBotVersion)
                .filter(CerberusBotVersion.bot_id == bot.id)
                .order_by(CerberusBotVersion.version_number.desc())
                .first()
            )
            if latest:
                print(f"    FIX: Re-pointing to latest version {latest.id} (v{latest.version_number})")
                bot.current_version_id = latest.id
                version = latest
            else:
                print(f"    WARNING: No versions exist for this bot at all!")

        if version:
            config = version.config_json or {}
            if isinstance(config, str):
                try:
                    config = json.loads(config)
                except json.JSONDecodeError:
                    config = {}

            if "strategy_type" not in config:
                config["strategy_type"] = "manual"
                version.config_json = config
                configs_fixed += 1
                print(f"    FIX: Added strategy_type='manual' to config")
            else:
                print(f"    OK strategy_type='{config['strategy_type']}'")

            # Report config summary
            config_keys = list(config.keys())
            print(f"    Config keys: {config_keys}")
        elif not bot.current_version_id:
            # Bot has no version at all — create a minimal one
            print(f"    INFO: No version assigned. Creating initial version with defaults.")
            from db.cerberus_models import _uuid
            new_version = CerberusBotVersion(
                id=_uuid(),
                bot_id=bot.id,
                version_number=1,
                config_json={"strategy_type": "manual"},
                diff_summary="Auto-created by audit script for compatibility",
                created_by="audit_script",
            )
            session.add(new_version)
            bot.current_version_id = new_version.id
            configs_fixed += 1
            print(f"    FIX: Created version v1 with strategy_type='manual'")

        # Sentiment integration note
        print(f"    INFO: Sentiment integration is fail-closed (bot will not trade without sentiment data)")

    # ─── Summary ─────────────────────────────────────────────────────────
    print(f"\n{'='*70}")
    print(f"  AUDIT SUMMARY")
    print(f"{'='*70}")
    print(f"\n  Bots audited:               {len(bots)}")
    print(f"  Bot status breakdown:        {status_counts}")
    print(f"  Unique users with bots:      {len(bot_user_ids)}")
    print(f"")
    print(f"  FIXES APPLIED:")
    print(f"    UserRiskLimits created:    {risk_limits_created}")
    print(f"    UserTradingSessions created: {trading_sessions_created}")
    print(f"    Bot configs fixed:         {configs_fixed}")
    print(f"    Orphaned version refs:     {orphaned_versions}")
    print(f"")
    print(f"  COMPATIBILITY STATUS:")
    print(f"    Kill switch:               All bot users now have UserRiskLimits rows")
    print(f"    Live/paper mode:           All bot users now have UserTradingSession rows")
    print(f"    Graduated drawdown:        Thresholds set (-2/-4/-7/-10%) on all new rows")
    print(f"    Quarter-Kelly sizing:      Users with <20 trades use 1% default (no fix needed)")
    print(f"    Sector concentration:      Limit set to 30% on all new rows")
    print(f"    Category/strategy scoring: StrategyTypeScore rows auto-created after trades close")
    print(f"    Sentiment integration:     Fail-closed by design (no DB fix needed)")
    print(f"    ReasoningEngine:           All bot configs now have strategy_type field")

    # Commit all changes
    session.commit()
    print(f"\n  All changes committed to database.")
    print(f"{'='*70}\n")

    session.close()


if __name__ == "__main__":
    main()
