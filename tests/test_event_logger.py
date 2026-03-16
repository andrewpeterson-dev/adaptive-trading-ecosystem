"""Tests for system event logger."""
import pytest
from unittest.mock import AsyncMock, patch
from db.models import SystemEventType, TradingModeEnum


@pytest.mark.asyncio
async def test_log_event_creates_record():
    from services.event_logger import log_event

    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    with patch("services.event_logger.get_session", return_value=mock_session):
        await log_event(
            user_id=1,
            event_type=SystemEventType.MODE_SWITCH,
            mode=TradingModeEnum.LIVE,
            description="Switched to live",
        )
        mock_session.add.assert_called_once()
        added = mock_session.add.call_args[0][0]
        assert added.user_id == 1
        assert added.event_type == SystemEventType.MODE_SWITCH
        assert added.mode == TradingModeEnum.LIVE
        assert added.severity == "info"


@pytest.mark.asyncio
async def test_log_event_does_not_crash_on_error():
    from services.event_logger import log_event

    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)
    mock_session.add.side_effect = Exception("DB down")

    with patch("services.event_logger.get_session", return_value=mock_session):
        # Should not raise
        await log_event(
            user_id=1,
            event_type=SystemEventType.TRADE_FAILED,
            mode=TradingModeEnum.PAPER,
        )


@pytest.mark.asyncio
async def test_log_event_with_metadata():
    from services.event_logger import log_event

    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    with patch("services.event_logger.get_session", return_value=mock_session):
        await log_event(
            user_id=2,
            event_type=SystemEventType.STRATEGY_PROMOTED,
            mode=TradingModeEnum.LIVE,
            description="Promoted momentum bot",
            severity="info",
            metadata={"paper_id": 5, "live_id": 12},
        )
        added = mock_session.add.call_args[0][0]
        assert added.metadata_json == {"paper_id": 5, "live_id": 12}
