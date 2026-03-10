import asyncio, pytest, sys
sys.path.insert(0, '.')

pytestmark = pytest.mark.asyncio

async def test_webull_has_supports_options_false():
    from db.database import get_session, init_db
    from db.models import ApiProvider
    from sqlalchemy import select
    await init_db()
    async with get_session() as db:
        r = await db.execute(select(ApiProvider).where(ApiProvider.slug == "webull"))
        p = r.scalar_one_or_none()
        assert p is not None
        assert p.supports_options is False
        assert p.supports_stocks is True
        assert p.supports_order_placement is True

async def test_tradier_has_supports_options_true():
    from db.database import get_session
    from db.models import ApiProvider
    from sqlalchemy import select
    async with get_session() as db:
        r = await db.execute(select(ApiProvider).where(ApiProvider.slug == "tradier"))
        p = r.scalar_one_or_none()
        assert p is not None
        assert p.supports_options is True
        assert p.supports_stocks is True

async def test_no_provider_has_null_capability_flags():
    from db.database import get_session
    from db.models import ApiProvider
    from sqlalchemy import select
    async with get_session() as db:
        r = await db.execute(select(ApiProvider))
        providers = r.scalars().all()
        for p in providers:
            assert p.supports_stocks is not None, f"{p.slug} has null supports_stocks"
            assert p.supports_order_placement is not None
            assert p.supports_positions_streaming is not None

async def test_option_sim_trade_model_exists():
    from db.models import OptionSimTrade
    from db.database import get_session
    from sqlalchemy import select
    async with get_session() as db:
        r = await db.execute(select(OptionSimTrade).limit(1))
        assert r is not None
