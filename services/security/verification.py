"""
Transaction verification — compare broker order history against local audit log.
Flags missing orders, quantity mismatches, and status discrepancies.
"""

from datetime import datetime
from typing import Optional

import structlog

from services.security.audit import AuditLogger

logger = structlog.get_logger(__name__)


class TransactionVerifier:
    """
    Compares broker-reported orders against the local trade audit log.
    Returns a verification report flagging any discrepancies.
    """

    def __init__(self, audit_logger: Optional[AuditLogger] = None):
        self._audit = audit_logger or AuditLogger()

    def verify_execution(self, executor) -> dict:
        """
        Pull order history from the broker via executor and compare
        against the local audit log.

        Returns a report dict with:
          - verified_at: timestamp
          - total_broker_orders: count from broker
          - total_local_trades: count from audit log
          - matched: number of orders that match
          - discrepancies: list of flagged issues
          - status: "clean" | "discrepancies_found"
        """
        # Fetch broker orders (closed = filled/cancelled)
        try:
            broker_orders = executor.get_orders(status="closed")
        except Exception as e:
            logger.error("verification_broker_fetch_failed", error=str(e))
            return {
                "verified_at": datetime.utcnow().isoformat(),
                "status": "error",
                "error": f"Failed to fetch broker orders: {e}",
            }

        # Load local audit log (all submitted entries)
        local_entries = self._audit.get_log(limit=10_000)
        submitted_entries = [e for e in local_entries if e.get("status") == "submitted"]

        # Index local entries by order_id for fast lookup
        local_by_order_id = {}
        for entry in submitted_entries:
            oid = entry.get("order_id", "")
            if oid:
                local_by_order_id[oid] = entry

        # Index broker orders by id
        broker_by_id = {}
        for order in broker_orders:
            oid = order.get("id", "")
            if oid:
                broker_by_id[oid] = order

        discrepancies = []
        matched = 0

        # Check each broker order against local log
        for oid, broker_order in broker_by_id.items():
            local = local_by_order_id.get(oid)
            if local is None:
                discrepancies.append({
                    "type": "missing_local",
                    "order_id": oid,
                    "detail": f"Broker order {oid} ({broker_order.get('symbol')}) not found in local audit log",
                    "broker_order": broker_order,
                })
                continue

            # Compare quantities
            broker_qty = float(broker_order.get("qty", 0))
            local_qty = float(local.get("quantity", 0))
            if broker_qty != local_qty:
                discrepancies.append({
                    "type": "quantity_mismatch",
                    "order_id": oid,
                    "detail": f"Broker qty={broker_qty}, local qty={local_qty}",
                    "broker_order": broker_order,
                    "local_entry": local,
                })
            else:
                matched += 1

        # Check for local entries with no matching broker order
        for oid, local_entry in local_by_order_id.items():
            if oid not in broker_by_id:
                discrepancies.append({
                    "type": "missing_broker",
                    "order_id": oid,
                    "detail": f"Local order {oid} ({local_entry.get('symbol')}) not found in broker history",
                    "local_entry": local_entry,
                })

        status = "clean" if not discrepancies else "discrepancies_found"

        report = {
            "verified_at": datetime.utcnow().isoformat(),
            "total_broker_orders": len(broker_orders),
            "total_local_trades": len(submitted_entries),
            "matched": matched,
            "discrepancies": discrepancies,
            "status": status,
        }

        logger.info(
            "verification_complete",
            status=status,
            matched=matched,
            discrepancies=len(discrepancies),
        )

        return report
