"""Webull account discovery — maps paper and live account IDs per user."""

import structlog
from sqlalchemy import delete

from db.database import get_session
from db.models import (
    UserBrokerAccount, SystemEventType, TradingModeEnum,
)
from services.event_logger import log_event

logger = structlog.get_logger(__name__)


async def discover_and_store_accounts(
    user_id: int,
    connection_id: int,
    app_key: str,
    app_secret: str,
) -> dict:
    """
    Call Webull SDK to discover paper and live accounts,
    store them in user_broker_accounts.
    Returns {"paper": [account_ids], "live": [account_ids]}.
    """
    try:
        from webullsdkcore.client import ApiClient
        from webullsdkcore.common.region import Region
        from webullsdktrade.api import API
    except ImportError as exc:
        logger.error("webull_sdk_missing", error=str(exc))
        return {"paper": [], "live": [], "error": str(exc)}

    try:
        api_client = ApiClient(app_key, app_secret, Region.US.value)
        api = API(api_client)
        resp = api.account.get_app_subscriptions()

        if resp.status_code != 200:
            return {"paper": [], "live": [], "error": f"HTTP {resp.status_code}"}

        subs = resp.json()
        if not isinstance(subs, list):
            subs = subs.get("data", [])

        paper_ids = []
        live_ids = []

        for sub in subs:
            acct_id = str(sub.get("account_id", sub.get("accountId", "")))
            if not acct_id:
                continue

            try:
                pr = api.account.get_account_profile(acct_id)
                acct_type = (
                    pr.json().get("account_type", "").lower()
                    if pr.status_code == 200 else ""
                )
            except Exception:
                acct_type = ""

            if any(kw in acct_type for kw in ("paper", "virtual", "demo", "simulated")):
                paper_ids.append(acct_id)
            else:
                live_ids.append(acct_id)

        # Store in DB — replace existing for this connection
        async with get_session() as db:
            await db.execute(
                delete(UserBrokerAccount).where(
                    UserBrokerAccount.user_id == user_id,
                    UserBrokerAccount.connection_id == connection_id,
                )
            )

            for acct_id in paper_ids:
                db.add(UserBrokerAccount(
                    user_id=user_id,
                    connection_id=connection_id,
                    broker_account_id=acct_id,
                    account_type="paper",
                ))
            for acct_id in live_ids:
                db.add(UserBrokerAccount(
                    user_id=user_id,
                    connection_id=connection_id,
                    broker_account_id=acct_id,
                    account_type="live",
                ))

        await log_event(
            user_id=user_id,
            event_type=SystemEventType.ACCOUNT_SYNC,
            mode=TradingModeEnum.PAPER,
            description=f"Discovered {len(paper_ids)} paper, {len(live_ids)} live accounts",
            metadata={"paper_ids": paper_ids, "live_ids": live_ids},
        )

        logger.info(
            "accounts_discovered",
            user_id=user_id,
            paper=len(paper_ids),
            live=len(live_ids),
        )
        return {"paper": paper_ids, "live": live_ids}

    except Exception as exc:
        logger.error("account_discovery_failed", error=str(exc))
        return {"paper": [], "live": [], "error": str(exc)}
