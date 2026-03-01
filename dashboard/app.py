"""
Adaptive Trading Ecosystem — Production Dashboard
Runs in two modes:
  - Standalone: uses local model layer with synthetic data (default, for dev/demo)
  - API mode:   connects to FastAPI backend (for production with live trading)

Launch: streamlit run dashboard/app.py
"""

import sys
from pathlib import Path

# Ensure project root is importable
sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta
import streamlit as st

try:
    from dashboard.auth import render_auth_page, logout, init_session_state
    from dashboard.broker_settings import render_broker_settings
    from dashboard.admin import render_admin_dashboard
    _has_auth = True
except ImportError:
    _has_auth = False

try:
    from dashboard.market_data import get_watchlist_quotes, get_historical_bars, get_current_price, DEFAULT_WATCHLIST
    from dashboard.paper_engine import get_portfolio_summary, execute_buy, execute_sell, get_trade_history, get_or_create_portfolio
    _has_paper = True
except ImportError:
    _has_paper = False

# ── Page Config ──────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Adaptive Trading Ecosystem",
    page_icon=None,
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Perf: Lightweight loading skeleton (renders before heavy computation) ──
_loading_placeholder = st.empty()
_loading_placeholder.markdown("""
<div style="display:flex;align-items:center;justify-content:center;height:60vh;flex-direction:column">
<div style="color:#3f3f46;font-size:0.85rem;font-weight:500;letter-spacing:0.04em">LOADING</div>
<div style="width:120px;height:2px;background:#18181b;margin-top:12px;border-radius:1px;overflow:hidden">
<div style="width:40px;height:2px;background:#52525b;border-radius:1px;animation:slide 1.2s ease-in-out infinite"></div>
</div>
<style>@keyframes slide{0%{transform:translateX(-40px)}100%{transform:translateX(120px)}}</style>
</div>
""", unsafe_allow_html=True)

# ── Auth Gate (optional — requires asyncpg/postgres) ──────────────────
if _has_auth:
    init_session_state()
    if not render_auth_page():
        st.stop()
    if not st.session_state.get("email_verified"):
        st.warning("Please verify your email address. Check your inbox for a verification link.")

# ── SEO / Accessibility / Performance Meta ───────────────────────────────

st.markdown("""
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="description" content="Adaptive Trading Ecosystem — multi-model algorithmic trading dashboard with regime detection, capital allocation, and real-time strategy analytics.">
""", unsafe_allow_html=True)

# ── Custom CSS ───────────────────────────────────────────────────────────

st.markdown("""
<style>
    /* ═══ PRODUCTION UI — Robinhood density + Apple polish ═══ */
    * { font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Display', 'Helvetica Neue', 'Inter', sans-serif !important; }

    /* ── A11y: Fix font-display for Streamlit fonts ────────── */
    @font-face { font-display: swap !important; }

    /* ── A11y: Fix MainMenu ARIA — hide broken element ─────── */
    span#MainMenu { display: none !important; }

    /* ── Perf: Reserve space for metric cards to prevent CLS ─ */
    [data-testid="stMetric"] { min-height: 72px; }

    /* ── Core surfaces ───────────────────────────────────────── */
    .stApp { background-color: #09090b; }
    [data-testid="stHeader"] { background-color: #09090b; border-bottom: 1px solid #18181b; }

    /* ── Sidebar — dense, functional ─────────────────────────── */
    [data-testid="stSidebar"] {
        background: #09090b;
        border-right: 1px solid #18181b;
        padding-top: 0.5rem;
    }
    [data-testid="stSidebar"] [data-testid="stMarkdown"] p { font-size: 0.82rem; margin-bottom: 0.2rem; }

    /* Hide sidebar collapse & branding */
    [data-testid="stSidebarCollapsedControl"],
    [data-testid="stSidebarCollapseButton"],
    button[kind="header"],
    #MainMenu, footer { display: none !important; visibility: hidden; }

    /* ── Metric cards — Robinhood-style ──────────────────────── */
    [data-testid="stMetric"] {
        background: #111113;
        border: 1px solid #1e1e22;
        border-radius: 10px;
        padding: 14px 18px;
        transition: border-color 0.2s ease;
    }
    [data-testid="stMetric"]:hover { border-color: #333338; }
    [data-testid="stMetricLabel"] {
        color: #71717a;
        font-size: 0.65rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.1em;
    }
    [data-testid="stMetricValue"] { color: #fafafa; font-size: 1.4rem; font-weight: 600; }
    [data-testid="stMetricDelta"] { font-weight: 500; font-size: 0.75rem; }

    /* ── Typography — tight hierarchy ────────────────────────── */
    h1 { color: #fafafa !important; font-weight: 700; font-size: 1.6rem !important; letter-spacing: -0.03em; margin-bottom: 0 !important; }
    h2 { color: #fafafa !important; font-weight: 600; font-size: 1.1rem !important; letter-spacing: -0.02em; border: none !important; padding-bottom: 0 !important; margin-top: 0.5rem !important; }
    h3 { color: #a1a1aa !important; font-weight: 600; font-size: 0.85rem !important; letter-spacing: -0.01em; border: none !important; padding-bottom: 0 !important; text-transform: uppercase; }
    h4 { color: #71717a !important; font-weight: 600; font-size: 0.78rem !important; letter-spacing: 0.02em; text-transform: uppercase; }
    p, span, li { letter-spacing: -0.01em; line-height: 1.5; }

    /* ── Tables ───────────────────────────────────────────────── */
    .stDataFrame { border-radius: 10px; overflow: hidden; border: 1px solid #1e1e22; }

    /* ── Buttons — crisp, interactive ────────────────────────── */
    .stButton > button {
        background-color: #111113;
        border: 1px solid #27272a;
        border-radius: 8px;
        color: #fafafa;
        font-size: 0.78rem;
        font-weight: 500;
        letter-spacing: 0.01em;
        padding: 0.4rem 1rem;
        transition: all 0.15s ease;
    }
    .stButton > button:hover { background-color: #1e1e22; border-color: #3f3f46; }
    .stButton > button:active { transform: scale(0.98); }
    .stButton > button[kind="primary"] { background-color: #fafafa; border-color: #fafafa; color: #09090b; font-weight: 600; }
    .stButton > button[kind="primary"]:hover { background-color: #d4d4d8; border-color: #d4d4d8; }

    /* ── Inputs ───────────────────────────────────────────────── */
    [data-baseweb="select"], [data-baseweb="input"] { border-radius: 8px !important; }

    /* ── Dividers — subtle ───────────────────────────────────── */
    hr { border-color: #18181b !important; margin: 0.5rem 0 !important; }

    /* ── Scrollbar ────────────────────────────────────────────── */
    ::-webkit-scrollbar { width: 5px; }
    ::-webkit-scrollbar-track { background: transparent; }
    ::-webkit-scrollbar-thumb { background: #27272a; border-radius: 3px; }
    ::-webkit-scrollbar-thumb:hover { background: #3f3f46; }

    /* ── Sidebar navigation radio ────────────────────────────── */
    div[data-testid="stRadio"] > div { gap: 0 !important; }
    div[data-testid="stRadio"] > div > label {
        padding: 7px 14px 7px 16px !important;
        border-radius: 0 !important;
        border-left: 3px solid transparent !important;
        font-size: 0.8rem !important;
        font-weight: 500 !important;
        color: #a1a1aa !important;
        transition: all 0.12s ease !important;
        margin: 0 !important;
    }
    div[data-testid="stRadio"] > div > label:hover {
        background: #111113 !important;
        color: #fafafa !important;
    }
    div[data-testid="stRadio"] > div > label:has(input:checked) {
        background: #111113 !important;
        border-left: 3px solid #fafafa !important;
        color: #fafafa !important;
        font-weight: 600 !important;
    }

    /* ── Alerts ───────────────────────────────────────────────── */
    [data-testid="stAlert"] { border-radius: 8px; font-size: 0.82rem; }

    /* ── Expander ─────────────────────────────────────────────── */
    [data-testid="stExpander"] { border: 1px solid #1e1e22 !important; border-radius: 10px !important; }
    [data-testid="stExpander"] summary { font-size: 0.8rem; font-weight: 600; color: #a1a1aa; }

    /* ── Card container helper ────────────────────────────────── */
    div.card-container {
        background: #111113;
        border: 1px solid #1e1e22;
        border-radius: 10px;
        padding: 16px;
        transition: border-color 0.2s ease;
    }
    div.card-container:hover { border-color: #333338; }

    /* ── Mode banners ────────────────────────────────────────── */
    .mode-banner-paper, .sidebar-mode-paper {
        background: #111113; border: 1px solid #27272a; border-radius: 8px;
        padding: 8px 14px; text-align: center; font-weight: 600; font-size: 0.78rem; color: #fafafa; letter-spacing: 0.03em;
    }
    .mode-banner-live, .sidebar-mode-live {
        background: #111113; border: 1px solid #fafafa; border-radius: 8px;
        padding: 8px 14px; text-align: center; font-weight: 700; font-size: 0.78rem; color: #fafafa; letter-spacing: 0.03em;
    }

    /* ── Reduce Streamlit default padding/gaps ───────────────── */
    .block-container { padding-top: 1rem !important; padding-bottom: 0.5rem !important; }
    [data-testid="stVerticalBlock"] > div { gap: 0.4rem; }
    [data-testid="column"] { padding: 0 0.25rem; }

    /* ── Plotly toolbar — only show on hover ─────────────────── */
    .js-plotly-plot .modebar { opacity: 0; transition: opacity 0.2s ease; }
    .js-plotly-plot:hover .modebar { opacity: 1; }

    /* ── Dataframe cells — tighter ─────────────────────────────── */
    [data-testid="stDataFrame"] th { font-size: 0.7rem !important; font-weight: 600; text-transform: uppercase; letter-spacing: 0.04em; color: #71717a; }
    [data-testid="stDataFrame"] td { font-size: 0.78rem !important; }

    /* ── Metric delta text ─────────────────────────────────────── */
    [data-testid="stMetricDelta"] svg { width: 12px; height: 12px; }

    /* ── Multiselect tags — compact ────────────────────────────── */
    [data-baseweb="tag"] { font-size: 0.7rem !important; padding: 2px 6px !important; }

    /* ── Sidebar section spacing ───────────────────────────────── */
    [data-testid="stSidebar"] hr { margin: 0.4rem 0 !important; }
    [data-testid="stSidebar"] [data-testid="stVerticalBlock"] > div { gap: 0.25rem; }

    /* ── Caption text — muted ──────────────────────────────────── */
    [data-testid="stCaptionContainer"] { color: #52525b !important; font-size: 0.7rem !important; }
</style>
""", unsafe_allow_html=True)

# ── Theme toggle state ──────────────────────────────────────────────────
if "theme" not in st.session_state:
    st.session_state.theme = "dark"


# ═══════════════════════════════════════════════════════════════════════════
# DATA LAYER — Generates realistic synthetic data & runs actual models
# ═══════════════════════════════════════════════════════════════════════════

@st.cache_data(ttl=300)
def generate_market_data(symbol: str = "SPY", days: int = 500) -> pd.DataFrame:
    """Generate realistic synthetic OHLCV data."""
    np.random.seed(42)
    dates = pd.bdate_range(end=datetime.now(), periods=days)
    base_price = 450.0
    returns = np.random.normal(0.0003, 0.015, days)

    # Embed diverse regime shifts to exercise all model types
    returns[50:80] += 0.004     # Bull trend (momentum)
    returns[100:150] -= 0.005   # Bear period (momentum short)
    returns[180:200] += 0.006   # Strong bull breakout
    returns[250:280] -= 0.003   # Mild correction
    returns[300:320] *= 0.3     # Low vol squeeze (vol model)
    returns[350:400] *= 2.0     # High vol expansion (vol model)
    returns[420:440] += 0.003   # Recovery trend

    # Inject earnings-like events (quarterly gaps + volume spikes)
    earnings_bars = list(range(63, days, 63))
    for eb in earnings_bars:
        if eb < days:
            gap_dir = np.random.choice([-1, 1])
            returns[eb] += gap_dir * np.random.uniform(0.02, 0.05)

    close = base_price * np.exp(np.cumsum(returns))
    high = close * (1 + np.abs(np.random.normal(0, 0.008, days)))
    low = close * (1 - np.abs(np.random.normal(0, 0.008, days)))
    open_ = close * (1 + np.random.normal(0, 0.003, days))
    volume = np.random.randint(50_000_000, 200_000_000, days)

    # Spike volume around earnings events
    for eb in earnings_bars:
        if eb < days:
            volume[eb] = int(volume[eb] * np.random.uniform(2.0, 3.5))
            for offset in [-2, -1, 1, 2]:
                idx = eb + offset
                if 0 <= idx < days:
                    volume[idx] = int(volume[idx] * np.random.uniform(1.3, 1.8))

    return pd.DataFrame({
        "timestamp": dates,
        "symbol": symbol,
        "open": open_,
        "high": high,
        "low": low,
        "close": close,
        "volume": volume.astype(float),
    })


@st.cache_data(ttl=300)
def generate_paired_data(days: int = 500) -> pd.DataFrame:
    """Generate QQQ data correlated ~0.85 to SPY for pairs trading."""
    spy_df = generate_market_data("SPY", days)
    np.random.seed(99)

    spy_log_rets = np.log(spy_df["close"] / spy_df["close"].shift(1)).fillna(0).values

    correlation = 0.85
    idio = np.random.normal(0, 0.015, days)
    qqq_rets = correlation * spy_log_rets + np.sqrt(1 - correlation**2) * idio
    qqq_rets += 0.0001

    base = 380.0
    qqq_close = base * np.exp(np.cumsum(qqq_rets))
    qqq_high = qqq_close * (1 + np.abs(np.random.normal(0, 0.009, days)))
    qqq_low = qqq_close * (1 - np.abs(np.random.normal(0, 0.009, days)))
    qqq_open = qqq_close * (1 + np.random.normal(0, 0.003, days))
    qqq_vol = np.random.randint(40_000_000, 160_000_000, days).astype(float)

    return pd.DataFrame({
        "timestamp": spy_df["timestamp"].values,
        "symbol": "QQQ",
        "open": qqq_open,
        "high": qqq_high,
        "low": qqq_low,
        "close": qqq_close,
        "volume": qqq_vol,
    })


# ── Strategy Catalog ─────────────────────────────────────────────────────

STRATEGY_CATALOG = {
    "Momentum Fast": {
        "category": "Trend Following",
        "description": "Fast trend-following with 5/20 MA crossover, RSI confirmation, and MACD histogram.",
    },
    "Momentum Slow": {
        "category": "Trend Following",
        "description": "Slow trend-following with 20/100 MA crossover for capturing major trends.",
    },
    "Mean Rev Tight": {
        "category": "Mean Reversion",
        "description": "Tight mean reversion trading z-score deviations with 15-bar lookback and 1.5 sigma entry.",
    },
    "Mean Rev Wide": {
        "category": "Mean Reversion",
        "description": "Wide mean reversion with 30-bar lookback and 2.2 sigma entry for larger moves.",
    },
    "Vol Squeeze": {
        "category": "Volatility",
        "description": "Volatility squeeze breakout using BB compression, ATR breakouts, and range expansion.",
    },
    "Earnings Momentum": {
        "category": "Event-Driven",
        "description": "Trades pre-earnings drift and post-earnings reactions. Fades overextended gaps, rides confirmed breakouts.",
    },
    "IV Crush": {
        "category": "Volatility",
        "description": "Exploits implied volatility collapse. Uses BB width / ATR as IV proxy. Profits from vol contraction.",
    },
    "Pairs StatArb": {
        "category": "Statistical Arbitrage",
        "description": "SPY/QQQ spread z-score mean reversion. Enters at deviation extremes, exits at mean reversion.",
    },
    "Breakout S/R": {
        "category": "Breakout",
        "description": "Support/resistance breakout using rolling channel highs/lows. Volume-confirmed entries, trailing stops.",
    },
}


@st.cache_resource
def run_models(selected_strategies: tuple = None):
    """Train selected models and run backtests."""
    from models.momentum import MomentumModel
    from models.mean_reversion import MeanReversionModel
    from models.volatility import VolatilityModel
    from models.ensemble import EnsembleMetaModel
    from models.breakout import BreakoutModel
    from models.iv_crush import IVCrushModel
    from models.earnings import EarningsMomentumModel
    from models.pairs import PairsModel
    from allocation.capital import CapitalAllocator
    from intelligence.regime import RegimeDetector
    from risk.manager import RiskManager

    if selected_strategies is None:
        selected_strategies = tuple(STRATEGY_CATALOG.keys())
    selected_set = set(selected_strategies)

    df = generate_market_data()
    qqq_df = generate_paired_data()
    split = int(len(df) * 0.7)
    train_df = df.iloc[:split]
    test_df = df.iloc[split:]
    qqq_train = qqq_df.iloc[:split]

    # Build model instances from selection
    ALL_MODELS = {
        "Momentum Fast": lambda: MomentumModel(name="Momentum Fast", fast_window=5, slow_window=20),
        "Momentum Slow": lambda: MomentumModel(name="Momentum Slow", fast_window=20, slow_window=100),
        "Mean Rev Tight": lambda: MeanReversionModel(name="Mean Rev Tight", lookback=15, entry_z=1.5),
        "Mean Rev Wide": lambda: MeanReversionModel(name="Mean Rev Wide", lookback=30, entry_z=2.2),
        "Vol Squeeze": lambda: VolatilityModel(name="Vol Squeeze"),
        "Earnings Momentum": lambda: EarningsMomentumModel(name="Earnings Momentum"),
        "IV Crush": lambda: IVCrushModel(name="IV Crush"),
        "Pairs StatArb": lambda: PairsModel(name="Pairs StatArb"),
        "Breakout S/R": lambda: BreakoutModel(name="Breakout S/R"),
    }

    models = [factory() for name, factory in ALL_MODELS.items() if name in selected_set]

    # Train and evaluate — PairsModel needs paired data
    for model in models:
        if isinstance(model, PairsModel):
            model.train(train_df, paired_df=qqq_train)
        else:
            model.train(train_df)
        model.evaluate(test_df)

    # Build ensemble
    ensemble = EnsembleMetaModel(name="Ensemble Meta")
    for m in models:
        ensemble.register_model(m)
    ensemble.train(train_df)
    ensemble.evaluate(test_df)

    # Capital allocation
    allocator = CapitalAllocator(total_capital=100_000)
    allocator.min_weight = 0.05
    allocator.max_weight = 0.60
    weights = allocator.compute_weights(models)

    # Regime detection
    detector = RegimeDetector()
    regime = detector.detect(df)

    # Risk manager
    risk = RiskManager()

    # Generate equity curves for each model on test data
    equity_curves = {}
    for model in models:
        positions = []
        for i in range(len(test_df)):
            window = df.iloc[:split + i + 1]
            sigs = model.predict(window)
            if sigs and sigs[0].direction == "long":
                positions.append(sigs[0].strength)
            elif sigs and sigs[0].direction == "short":
                positions.append(-sigs[0].strength)
            else:
                positions.append(0.0)

        pos_series = pd.Series(positions, index=test_df.index)
        rets = test_df["close"].pct_change().fillna(0) * pos_series.shift(1).fillna(0)
        capital = allocator.get_allocation(model.name)
        equity = capital * (1 + rets).cumprod()
        equity_curves[model.name] = equity

    # Combined portfolio equity
    combined = sum(equity_curves.values())

    # Generate trade log
    trade_log = []
    for model in models:
        for i in range(0, len(test_df), 5):
            sigs = model.predict(df.iloc[:split + i + 1])
            if sigs:
                s = sigs[0]
                trade_log.append({
                    "Time": test_df["timestamp"].iloc[i],
                    "Model": model.name,
                    "Symbol": "SPY",
                    "Direction": s.direction.upper(),
                    "Strength": round(s.strength, 3),
                    "Status": "Filled",
                })

    # Regime history (simulate detection over time)
    regime_history = []
    for i in range(0, len(df), 20):
        if i + 60 < len(df):
            r = detector.detect(df.iloc[:i + 60])
            regime_history.append({
                "Date": df["timestamp"].iloc[i + 59],
                "Regime": r["regime"].value if hasattr(r["regime"], "value") else str(r["regime"]),
                "Confidence": r["confidence"],
                "Volatility": r["volatility_20d"],
                "Trend": r["trend_strength"],
            })

    return {
        "models": models,
        "ensemble": ensemble,
        "allocator": allocator,
        "regime": regime,
        "risk": risk,
        "equity_curves": equity_curves,
        "combined_equity": combined,
        "test_df": test_df,
        "full_df": df,
        "trade_log": trade_log,
        "regime_history": regime_history,
        "weights": weights,
    }


# ═══════════════════════════════════════════════════════════════════════════
# SIDEBAR
# ═══════════════════════════════════════════════════════════════════════════

_display_name = st.session_state.get("user_display_name", "Trader")
st.sidebar.markdown(f"### {_display_name}")
st.sidebar.caption("Adaptive Trading Ecosystem")

# Paper mode detection
_user_id = st.session_state.get("user_id")
_has_broker = False
if _has_auth and _has_paper and _user_id:
    from dashboard.auth import get_db as _get_db
    from db.models import BrokerCredential as _BC
    from sqlalchemy import select as _select
    _db = _get_db()
    try:
        _has_broker = _db.execute(
            _select(_BC).where(_BC.user_id == _user_id).limit(1)
        ).scalar_one_or_none() is not None
    finally:
        _db.close()

    if _has_broker:
        st.sidebar.success("**Live Mode** — Broker connected")
    else:
        st.sidebar.info("**Paper Mode** — $1M virtual portfolio")
        get_or_create_portfolio(_user_id)
elif _has_paper:
    _user_id = None

# Data source toggle — default to Webull Live if user has broker creds
_default_source_idx = 1 if _has_broker else 0
data_source = st.sidebar.radio(
    "Data Source",
    ["Synthetic", "Webull Live"],
    index=_default_source_idx,
    horizontal=True,
    key="data_source",
)
use_webull = data_source == "Webull Live"

# Webull connection panel with Paper/Live mode isolation
_wb_client = None
_trading_mode_str = "PAPER"  # safe default

if use_webull:
    # ── Paper/Live mode selector (LOCKED after connection) ──
    if "wb_connected" not in st.session_state:
        st.session_state.wb_connected = False

    if not st.session_state.wb_connected:
        # Allow mode selection BEFORE connecting
        _trading_mode_str = st.sidebar.radio(
            "Trading Mode",
            ["PAPER", "LIVE"],
            index=0,
            horizontal=True,
            key="wb_trading_mode",
            help="PAPER: simulated trades, no real money. LIVE: real money trades.",
        )
    else:
        # Mode is LOCKED after connection — show indicator only
        _trading_mode_str = st.session_state.get("wb_trading_mode", "PAPER")
        if _trading_mode_str == "PAPER":
            st.sidebar.markdown('<div class="sidebar-mode-paper">PAPER TRADING</div>', unsafe_allow_html=True)
        else:
            st.sidebar.markdown('<div class="sidebar-mode-live">LIVE TRADING - REAL MONEY</div>', unsafe_allow_html=True)

    # ── Create or restore the correct client class ──
    try:
        from data.webull_client import WebullPaperClient, WebullLiveClient, TradingMode

        # Key changes if mode switches (forces new client)
        client_key = f"wb_client_{_trading_mode_str}"
        if client_key not in st.session_state:
            if _trading_mode_str == "LIVE":
                st.session_state[client_key] = WebullLiveClient()
            else:
                st.session_state[client_key] = WebullPaperClient()

            # Auto-load creds from DB if user is logged in with broker creds
            _client = st.session_state[client_key]
            _loaded_from_db = False
            if _has_broker and _user_id:
                try:
                    from db.encryption import decrypt_value
                    _db2 = _get_db()
                    _cred = _db2.execute(
                        _select(_BC).where(_BC.user_id == _user_id, _BC.broker_type == "webull")
                    ).scalar_one_or_none()
                    _db2.close()
                    if _cred:
                        _client._app_key = decrypt_value(_cred.encrypted_api_key)
                        _client._app_secret = decrypt_value(_cred.encrypted_api_secret)
                        result = _client.connect()
                        if result.get("success"):
                            _loaded_from_db = True
                except Exception:
                    pass

            # Fallback to PeteBot config / saved config
            if not _loaded_from_db and not _client.is_connected:
                _client.try_restore()

            if _client.is_connected:
                st.session_state.wb_connected = True

        _wb_client = st.session_state[client_key]
    except ImportError:
        st.sidebar.error("Webull SDK not installed")
        _wb_client = None

    # ── Live mode warning BEFORE connection ──
    if _trading_mode_str == "LIVE" and _wb_client and not _wb_client.is_connected:
        st.sidebar.warning(
            "LIVE MODE uses REAL MONEY. "
            "Orders placed will execute on your actual brokerage account."
        )

    # ── Credentials panel ──
    if _wb_client and not _wb_client.is_connected:
        with st.sidebar.expander("Webull API Credentials", expanded=True):
            st.markdown(
                "From [developer.webull.com](https://developer.webull.com) > "
                "API Keys Management > View"
            )
            wb_key = st.text_input("App Key", key="wb_app_key", type="password")
            wb_secret = st.text_input("App Secret", key="wb_app_secret", type="password")

            if st.button("Connect", key="wb_connect"):
                if wb_key and wb_secret:
                    _wb_client._app_key = wb_key
                    _wb_client._app_secret = wb_secret
                    result = _wb_client.connect()
                    if result.get("success"):
                        st.session_state.wb_connected = True
                        st.success(f"Connected [{_trading_mode_str}] (Account: {result.get('account_id', 'OK')})")
                        st.rerun()
                    else:
                        st.error(result.get("error", "Connection failed"))
                else:
                    st.warning("Both App Key and App Secret are required")

    elif _wb_client and _wb_client.is_connected:
        mode_color = "#ffffff" if _wb_client.is_paper else "#888888"
        st.sidebar.markdown(
            f"**Webull:** <span style='color:{mode_color}'>{_wb_client.mode_label} Mode</span>",
            unsafe_allow_html=True,
        )
        acct = _wb_client.get_account_summary()
        if acct:
            st.sidebar.markdown(f"**Account:** {acct['account_id']}")
            st.sidebar.markdown(f"**Net Liq:** ${acct['net_liquidation']:,.2f}")
            st.sidebar.markdown(f"**Buying Power:** ${acct['buying_power']:,.2f}")
        if st.sidebar.button("Disconnect"):
            _wb_client.disconnect()
            st.session_state.wb_connected = False
            st.rerun()

mode_label = f"Webull {_trading_mode_str}" if use_webull else "Standalone"
st.sidebar.caption(f"v1.0.0 | {mode_label} Mode")
st.sidebar.divider()

# ── Active Models ────────────────────────────────────────────────────────
st.sidebar.markdown("#### Active Models")

if "selected_strategies" not in st.session_state:
    st.session_state.selected_strategies = set(STRATEGY_CATALOG.keys())

all_names = list(STRATEGY_CATALOG.keys())
selected_list = st.sidebar.multiselect(
    "Ensemble strategies",
    options=all_names,
    default=[s for s in all_names if s in st.session_state.selected_strategies],
    key="strat_multiselect",
    label_visibility="collapsed",
)
st.session_state.selected_strategies = set(selected_list)
selected_tuple = tuple(sorted(st.session_state.selected_strategies))

st.sidebar.caption(f"{len(selected_list)} of {len(all_names)} active")
st.sidebar.divider()

# ── Load Models ─────────────────────────────────────────────────────────
with st.spinner("Loading models..."):
    data = run_models(selected_tuple)
_loading_placeholder.empty()

# ── Status ──────────────────────────────────────────────────────────────
regime = data["regime"]
regime_label = regime["regime"].value if hasattr(regime["regime"], "value") else str(regime["regime"])
st.sidebar.caption(f"Regime: {regime_label} ({regime['confidence']:.0%}) | Vol: {regime['volatility_20d']:.1%} | {len(data['models'])} models")

if st.sidebar.button("Retrain", key="retrain_btn"):
    st.cache_resource.clear()
    st.rerun()

st.sidebar.divider()

# ── Account & Logout ────────────────────────────────────────────────────
if _has_auth:
    _email = st.session_state.get("user_email", "")
    if _email:
        st.sidebar.caption(f"Signed in as {_email}")
    if st.sidebar.button("Logout", key="settings_logout", use_container_width=True):
        logout()
        st.rerun()

# ═══════════════════════════════════════════════════════════════════════════
# MAIN CONTENT
# ═══════════════════════════════════════════════════════════════════════════

# ── Key Metrics Row ──────────────────────────────────────────────────────

combined_eq = data["combined_equity"]
final_equity = combined_eq.iloc[-1]
initial_equity = combined_eq.iloc[0]
total_return = (final_equity / initial_equity - 1) * 100
peak = combined_eq.cummax()
drawdown = ((combined_eq - peak) / peak).min() * 100

col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("Portfolio Value", f"${final_equity:,.0f}", f"{total_return:+.1f}%")
col2.metric("Total Return", f"{total_return:.2f}%")
col3.metric("Max Drawdown", f"{drawdown:.2f}%")

# Best model Sharpe
best = max(data["models"], key=lambda m: m.metrics.sharpe_ratio)
col4.metric("Best Sharpe", f"{best.metrics.sharpe_ratio:.3f}", best.name)

# Trading status
halted = data["risk"].is_halted
col5.metric("Status", "HALTED" if halted else "ACTIVE", delta="System OK" if not halted else "Risk Breach", delta_color="normal" if not halted else "inverse")

# ── Page Navigation (sidebar) ─────────────────────────────────────────────

_is_admin = st.session_state.get("is_admin", False)

_page_names = [
    # ── Dashboard ──
    "Overview",
    # ── Trading ──
    "Paper Trading",
    "Trades",
    # ── Models & Strategy ──
    "Models",
    "Strategy Catalog",
    "Strategy Builder",
    "Competition",
    # ── Analysis ──
    "AI Intelligence",
    "Allocation",
    "Risk",
    "Regime",
    # ── Account ──
    "Broker Settings",
]
if use_webull:
    _page_names.insert(_page_names.index("Trades") + 1, "Live Trading")
if _is_admin:
    _page_names.append("Admin")

if "current_page" not in st.session_state:
    st.session_state.current_page = "Overview"

st.sidebar.divider()

_page_icons = {
    "Overview": "📊",
    "Paper Trading": "💵",
    "Trades": "📋",
    "Live Trading": "⚡",
    "Models": "🧠",
    "Strategy Catalog": "📚",
    "Strategy Builder": "🔧",
    "Competition": "🏆",
    "AI Intelligence": "🤖",
    "Allocation": "⚖️",
    "Risk": "🛡️",
    "Regime": "🌡️",
    "Broker Settings": "🔑",
    "Admin": "⚙️",
}

selected_page = st.sidebar.radio(
    "Navigation",
    _page_names,
    index=_page_names.index(st.session_state.current_page) if st.session_state.current_page in _page_names else 0,
    key="nav_radio",
    label_visibility="collapsed",
    format_func=lambda x: f"{_page_icons.get(x, '•')}  {x}",
)
st.session_state.current_page = selected_page

# ═══════════════════════════════════════════════════════════════════════════
# TAB 1: OVERVIEW
# ═══════════════════════════════════════════════════════════════════════════

if selected_page == "Overview":

    # ── Hero: Portfolio Equity Curve ─────────────────────────────────────
    fig = go.Figure()
    for name, eq in data["equity_curves"].items():
        fig.add_trace(go.Scatter(
            x=data["test_df"]["timestamp"], y=eq,
            name=name, line=dict(width=1), opacity=0.35,
        ))
    fig.add_trace(go.Scatter(
        x=data["test_df"]["timestamp"], y=combined_eq,
        name="Portfolio", line=dict(color="#fafafa", width=2.5),
    ))
    fig.update_layout(
        height=300, template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(gridcolor="#1e1e22", title=""),
        yaxis=dict(gridcolor="#1e1e22", title="", tickprefix="$"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", font=dict(size=10)),
        margin=dict(l=50, r=10, t=10, b=25),
        hovermode="x unified",
    )
    st.plotly_chart(fig, use_container_width=True)

    # ── Three-column dense strip ─────────────────────────────────────────
    col_dd, col_price, col_perf = st.columns(3)

    with col_dd:
        st.markdown("#### Drawdown")
        dd_series = (combined_eq - combined_eq.cummax()) / combined_eq.cummax() * 100
        fig_dd = go.Figure()
        fig_dd.add_trace(go.Scatter(
            x=data["test_df"]["timestamp"], y=dd_series,
            fill="tozeroy", fillcolor="rgba(161,161,170,0.06)",
            line=dict(color="#71717a", width=1), name="DD",
        ))
        fig_dd.update_layout(
            height=180, template="plotly_dark",
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            yaxis=dict(gridcolor="#1e1e22", ticksuffix="%", title=""),
            xaxis=dict(gridcolor="#1e1e22", showticklabels=False),
            margin=dict(l=35, r=5, t=5, b=5), showlegend=False,
        )
        st.plotly_chart(fig_dd, use_container_width=True)

    with col_price:
        st.markdown("#### SPY Price")
        fig_price = go.Figure()
        fig_price.add_trace(go.Candlestick(
            x=data["test_df"]["timestamp"],
            open=data["test_df"]["open"], high=data["test_df"]["high"],
            low=data["test_df"]["low"], close=data["test_df"]["close"],
            name="SPY",
        ))
        fig_price.update_layout(
            height=180, template="plotly_dark",
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            xaxis=dict(gridcolor="#1e1e22", rangeslider=dict(visible=False), showticklabels=False),
            yaxis=dict(gridcolor="#1e1e22", tickprefix="$", title=""),
            margin=dict(l=35, r=5, t=5, b=5), showlegend=False,
        )
        st.plotly_chart(fig_price, use_container_width=True)

    with col_perf:
        st.markdown("#### Model Rankings")
        _ov_rows = []
        for m in sorted(data["models"], key=lambda x: x.metrics.sharpe_ratio, reverse=True):
            met = m.metrics
            eq = data["equity_curves"].get(m.name)
            eq_ret = ((eq.iloc[-1] / eq.iloc[0]) - 1) * 100 if eq is not None and len(eq) > 0 else 0
            _ov_rows.append({
                "Model": m.name,
                "Sharpe": round(met.sharpe_ratio, 2),
                "Ret": f"{eq_ret:+.1f}%",
                "WR": f"{met.win_rate:.0%}",
                "Wt": f"{data['weights'].get(m.name, 0):.0%}",
            })
        st.dataframe(pd.DataFrame(_ov_rows), width="stretch", hide_index=True, height=180)

    # ── Regime + Recent Signals row ──────────────────────────────────────
    col_regime, col_signals = st.columns([1, 2])

    with col_regime:
        st.markdown("#### Regime")
        _regime_names = {
            "low_vol_bull": "Low Vol Bull", "high_vol_bull": "High Vol Bull",
            "low_vol_bear": "Low Vol Bear", "high_vol_bear": "High Vol Bear",
            "sideways": "Sideways",
        }
        st.markdown(f"**{_regime_names.get(regime_label, regime_label)}** — {regime['confidence']:.0%}")
        st.caption(f"Vol: {regime['volatility_20d']:.2%} | Trend: {regime['trend_strength']:.4f}")
        if data["regime_history"]:
            rh = data["regime_history"][-12:]
            rh_conf = [r["Confidence"] for r in rh]
            fig_rh = go.Figure()
            fig_rh.add_trace(go.Scatter(
                y=rh_conf, mode="lines+markers",
                line=dict(color="#71717a", width=1.5),
                marker=dict(size=3, color="#a1a1aa"),
            ))
            fig_rh.update_layout(
                height=70, template="plotly_dark",
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                xaxis=dict(visible=False), yaxis=dict(visible=False, range=[0, 1.1]),
                margin=dict(l=0, r=0, t=0, b=0), showlegend=False,
            )
            st.plotly_chart(fig_rh, use_container_width=True, key="regime_spark")

    with col_signals:
        st.markdown("#### Recent Signals")
        if data["trade_log"]:
            recent = data["trade_log"][-15:]
            sig_df = pd.DataFrame(recent)
            sig_df["Time"] = pd.to_datetime(sig_df["Time"]).dt.strftime("%m/%d %H:%M")
            sig_df = sig_df[["Time", "Model", "Direction", "Strength"]]
            st.dataframe(sig_df, width="stretch", hide_index=True, height=180)


# ═══════════════════════════════════════════════════════════════════════════
# TAB 2: MODEL PERFORMANCE
# ═══════════════════════════════════════════════════════════════════════════

if selected_page == "Models":
    st.markdown("#### Performance Comparison")

    perf_rows = []
    for m in data["models"]:
        met = m.metrics
        perf_rows.append({
            "Model": m.name,
            "Sharpe": round(met.sharpe_ratio, 3),
            "Sortino": round(met.sortino_ratio, 3),
            "Win Rate": f"{met.win_rate:.1%}",
            "PF": round(met.profit_factor, 2) if met.profit_factor != float("inf") else "---",
            "Max DD": f"{met.max_drawdown:.2%}",
            "Return": f"{met.total_return:.2%}",
            "Trades": met.num_trades,
            "Wt": f"{data['weights'].get(m.name, 0):.1%}",
        })

    perf_df = pd.DataFrame(perf_rows)
    st.dataframe(perf_df, width="stretch", hide_index=True, height=220)

    col_sharpe, col_wr = st.columns(2)

    with col_sharpe:
        st.markdown("#### Sharpe Ratio")
        names = [m.name for m in data["models"]]
        sharpes = [m.metrics.sharpe_ratio for m in data["models"]]
        colors = ["#ffffff" if s > 0 else "#555555" for s in sharpes]

        fig_sharpe = go.Figure(data=[go.Bar(
            x=names, y=sharpes,
            marker_color=colors,
            text=[f"{s:.3f}" for s in sharpes],
            textposition="outside",
        )])
        fig_sharpe.update_layout(
            height=280,
            template="plotly_dark",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            yaxis=dict(title="Sharpe Ratio", gridcolor="#1e1e22"),
            xaxis=dict(gridcolor="#1e1e22"),
            margin=dict(l=60, r=20, t=20, b=80),
        )
        st.plotly_chart(fig_sharpe, use_container_width=True)

    with col_wr:
        st.markdown("#### Win Rate & Profit Factor")
        win_rates = [m.metrics.win_rate * 100 for m in data["models"]]
        pf = [min(m.metrics.profit_factor, 5) for m in data["models"]]

        fig_wr = go.Figure()
        fig_wr.add_trace(go.Bar(
            name="Win Rate %", x=names, y=win_rates,
            marker_color="#ffffff",
            text=[f"{w:.1f}%" for w in win_rates],
            textposition="outside",
        ))
        fig_wr.add_trace(go.Scatter(
            name="Profit Factor", x=names, y=[p * 20 for p in pf],
            mode="markers+lines",
            marker=dict(size=12, color="#888888"),
            yaxis="y2",
        ))
        fig_wr.update_layout(
            height=280,
            template="plotly_dark",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            yaxis=dict(title="Win Rate %", gridcolor="#1e1e22"),
            yaxis2=dict(title="Profit Factor", overlaying="y", side="right", showgrid=False),
            xaxis=dict(gridcolor="#1e1e22"),
            margin=dict(l=60, r=60, t=20, b=80),
            legend=dict(orientation="h", yanchor="bottom", y=1.02),
        )
        st.plotly_chart(fig_wr, use_container_width=True)

    st.markdown("#### Individual Equity Curves")
    fig_ind = go.Figure()
    colors_list = ["#ffffff", "#cccccc", "#aaaaaa", "#888888", "#666666", "#555555", "#444444", "#333333", "#bbbbbb"]
    for i, (name, eq) in enumerate(data["equity_curves"].items()):
        fig_ind.add_trace(go.Scatter(
            x=data["test_df"]["timestamp"],
            y=eq,
            name=name,
            line=dict(color=colors_list[i % len(colors_list)], width=2),
        ))
    fig_ind.update_layout(
        height=300,
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        yaxis=dict(title="Equity ($)", gridcolor="#1e1e22", tickprefix="$"),
        xaxis=dict(gridcolor="#1e1e22"),
        margin=dict(l=60, r=20, t=20, b=40),
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        hovermode="x unified",
    )
    st.plotly_chart(fig_ind, use_container_width=True)


# ═══════════════════════════════════════════════════════════════════════════
# TAB 3: STRATEGY CATALOG
# ═══════════════════════════════════════════════════════════════════════════

if selected_page == "Strategy Catalog":
    st.markdown("#### Strategy Catalog")

    for model in data["models"]:
        name = model.name
        info = STRATEGY_CATALOG.get(name, {})
        met = model.metrics

        st.markdown("---")

        col_info, col_metrics, col_chart = st.columns([2, 1.5, 2])

        with col_info:
            st.markdown(f"#### {name}")
            st.markdown(f"**Category:** {info.get('category', 'General')}")
            st.markdown(info.get("description", ""))

        with col_metrics:
            st.markdown("**Performance**")
            sharpe_color = "#ffffff" if met.sharpe_ratio > 0 else "#555555"
            st.markdown(f"Sharpe: **<span style='color:{sharpe_color}'>{met.sharpe_ratio:.3f}</span>**", unsafe_allow_html=True)
            ret_color = "#ffffff" if met.total_return > 0 else "#555555"
            st.markdown(f"Return: **<span style='color:{ret_color}'>{met.total_return:.2%}</span>**", unsafe_allow_html=True)
            st.markdown(f"Win Rate: **{met.win_rate:.1%}**")
            st.markdown(f"Max DD: **{met.max_drawdown:.2%}**")
            st.markdown(f"Trades: **{met.num_trades}**")
            st.markdown(f"Weight: **{data['weights'].get(name, 0):.1%}**")

        with col_chart:
            if name in data["equity_curves"]:
                eq = data["equity_curves"][name]
                fig_mini = go.Figure()
                eq_color = "#ffffff" if eq.iloc[-1] > eq.iloc[0] else "#555555"
                fig_mini.add_trace(go.Scatter(
                    x=data["test_df"]["timestamp"],
                    y=eq,
                    mode="lines",
                    line=dict(color=eq_color, width=1.5),
                    fill="tozeroy",
                    fillcolor=eq_color.replace(")", ", 0.08)").replace("rgb", "rgba") if "rgb" in eq_color else f"rgba({int(eq_color[1:3],16)},{int(eq_color[3:5],16)},{int(eq_color[5:7],16)},0.08)",
                ))
                fig_mini.update_layout(
                    height=100,
                    margin=dict(l=0, r=0, t=5, b=5),
                    template="plotly_dark",
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    xaxis=dict(visible=False),
                    yaxis=dict(visible=False),
                    showlegend=False,
                )
                st.plotly_chart(fig_mini, use_container_width=True, key=f"mini_eq_{name}")
            else:
                st.caption("No equity data")



# ═══════════════════════════════════════════════════════════════════════════
# TAB: AI INTELLIGENCE
# ═══════════════════════════════════════════════════════════════════════════

if selected_page == "AI Intelligence":
    st.subheader("AI Market Intelligence")
    st.markdown("LLM-powered market analysis that feeds into regime detection and model weighting.")

    # Initialize LLM analyst in session state
    if "llm_analyst" not in st.session_state:
        from intelligence.llm_analyst import LLMAnalyst
        st.session_state.llm_analyst = LLMAnalyst()

    analyst = st.session_state.llm_analyst

    # Check if API key is configured
    from config.settings import get_settings as _get_ai_settings
    _ai_settings = _get_ai_settings()
    has_api_key = bool(_ai_settings.anthropic_api_key or _ai_settings.openai_api_key)

    if not has_api_key:
        st.warning(
            "No LLM API key configured. Add `ANTHROPIC_API_KEY=sk-ant-...` or "
            "`OPENAI_API_KEY=sk-...` to your `.env` file in the project root."
        )
        st.code(
            "# Create .env in project root:\n"
            "ANTHROPIC_API_KEY=sk-ant-api03-...\n"
            "# OR\n"
            "OPENAI_API_KEY=sk-...\n"
            "LLM_PROVIDER=anthropic  # or openai\n"
            "LLM_MODEL=claude-sonnet-4-20250514  # or gpt-4o",
            language="bash",
        )

    col_run, col_status = st.columns([1, 2])

    with col_run:
        run_analysis = st.button(
            "Run AI Analysis",
            type="primary",
            width="stretch",
            disabled=not has_api_key,
        )
        st.caption(f"Provider: **{_ai_settings.llm_provider}** | Model: **{_ai_settings.llm_model}**")

    with col_status:
        latest = analyst.get_latest()
        if latest:
            st.markdown(
                f"Last analysis: **{latest.timestamp[:19]}** | "
                f"Latency: **{latest.latency_ms}ms** | "
                f"Model: **{latest.model_used}**"
            )
        else:
            st.markdown("No analysis run yet.")

    # Run analysis on button click
    if run_analysis and has_api_key:
        with st.spinner("Running LLM analysis..."):
            model_perf = [
                {
                    "name": m.name,
                    "sharpe": m.metrics.sharpe_ratio,
                    "win_rate": m.metrics.win_rate,
                    "max_drawdown": m.metrics.max_drawdown,
                    "weight": data["weights"].get(m.name, 0),
                }
                for m in data["models"]
            ]
            try:
                analysis_result = analyst.analyze(
                    df=data["full_df"],
                    regime_data=data["regime"],
                    model_performance=model_perf,
                )
                st.session_state.latest_analysis = analysis_result
                st.success(f"Analysis complete in {analysis_result.latency_ms}ms")
            except Exception as e:
                st.error(f"Analysis failed: {e}")

    # Display latest analysis
    display_analysis = st.session_state.get("latest_analysis") or analyst.get_latest()

    if display_analysis:
        st.divider()

        # Key metrics row
        ai_c1, ai_c2, ai_c3, ai_c4 = st.columns(4)

        ai_c1.metric(
            "AI Regime",
            display_analysis.regime_assessment.upper(),
            f"{display_analysis.confidence:.0%} confidence",
        )
        ai_c2.metric(
            "Market Bias",
            display_analysis.bias.upper(),
            f"Strength: {display_analysis.bias_strength:.0%}",
        )
        ai_c3.metric("Risk Level", display_analysis.risk_level.upper())
        ai_c4.metric("Latency", f"{display_analysis.latency_ms}ms", display_analysis.model_used)

        # Two-column layout: factors + adjustments
        col_factors, col_adj = st.columns(2)

        with col_factors:
            st.markdown("#### Key Factors")
            for i, factor in enumerate(display_analysis.key_factors, 1):
                st.markdown(f"**{i}.** {factor}")

            st.markdown("#### Reasoning")
            st.markdown(f"_{display_analysis.reasoning}_")

        with col_adj:
            st.markdown("#### Recommended Weight Adjustments")
            if display_analysis.recommended_adjustments:
                adj_rows = []
                for category, multiplier in display_analysis.recommended_adjustments.items():
                    direction = "increase" if multiplier > 1.01 else "decrease" if multiplier < 0.99 else "hold"
                    change_pct = (multiplier - 1.0) * 100
                    adj_rows.append({
                        "Category": category.replace("_", " ").title(),
                        "Multiplier": f"{multiplier:.2f}x",
                        "Change": f"{change_pct:+.1f}%",
                        "Signal": {"increase": "Overweight", "decrease": "Underweight", "hold": "Neutral"}[direction],
                    })
                st.dataframe(pd.DataFrame(adj_rows), width="stretch", hide_index=True)

                # Show adjusted vs current weights
                st.markdown("#### Weight Impact Preview")
                current_w = data["weights"]
                adjusted_w = analyst.apply_adjustments_to_weights(current_w, display_analysis)

                impact_rows = []
                for model_name in current_w:
                    cur = current_w[model_name]
                    adj_val = adjusted_w.get(model_name, cur)
                    impact_rows.append({
                        "Model": model_name,
                        "Current": f"{cur:.1%}",
                        "Adjusted": f"{adj_val:.1%}",
                        "Delta": f"{(adj_val - cur) * 100:+.1f}pp",
                    })
                st.dataframe(pd.DataFrame(impact_rows), width="stretch", hide_index=True)
            else:
                st.info("No adjustments recommended (neutral stance).")

            # Sector rotation
            if display_analysis.sector_rotation:
                st.markdown("#### Strategy Type Rotation")
                for sector, sentiment in display_analysis.sector_rotation.items():
                    icon = {"overweight": "^", "underweight": "v", "neutral": "-"}.get(sentiment, "-")
                    color = {"overweight": "#ffffff", "underweight": "#555555", "neutral": "#777777"}.get(sentiment, "#777777")
                    st.markdown(
                        f"<span style='color:{color}'>{icon}</span> **{sector.replace('_', ' ').title()}**: {sentiment}",
                        unsafe_allow_html=True,
                    )

        # Analysis history
        ai_history = analyst.get_history(limit=10)
        if len(ai_history) > 1:
            st.divider()
            st.markdown("#### Analysis History")

            hist_rows = []
            for h in reversed(ai_history):
                hist_rows.append({
                    "Time": h["timestamp"][:19],
                    "Regime": h["regime_assessment"],
                    "Confidence": f"{h['confidence']:.0%}",
                    "Bias": h["bias"],
                    "Risk": h["risk_level"],
                    "Model": h["model_used"],
                    "Latency": f"{h['latency_ms']}ms",
                })
            st.dataframe(pd.DataFrame(hist_rows), width="stretch", hide_index=True)

    else:
        st.info("Click **Run AI Analysis** to generate an LLM-powered market assessment.")


# ═══════════════════════════════════════════════════════════════════════════
# TAB: COMPETITION — Head-to-Head Model Arena
# ═══════════════════════════════════════════════════════════════════════════

if selected_page == "Competition":
    st.markdown("#### Model Competition Arena")

    models_list = data["models"]
    equity_curves = data["equity_curves"]
    weights = data["weights"]
    test_df = data["test_df"]

    # ── Leaderboard ──────────────────────────────────────────────────────
    st.markdown("#### Leaderboard")

    # Compute composite score: 30% Sharpe + 25% Sortino + 20% Win Rate + 15% Return - 10% |DD|
    leaderboard = []
    for m in models_list:
        met = m.metrics
        score = (
            0.30 * max(met.sharpe_ratio, -2) / 2  # Normalize: -2 to 2 → -0.3 to 0.3
            + 0.25 * max(met.sortino_ratio, -2) / 2
            + 0.20 * met.win_rate
            + 0.15 * min(max(met.total_return, -0.5), 0.5) / 0.5  # Clamp to [-50%, 50%]
            - 0.10 * abs(met.max_drawdown) / 0.2  # Normalize DD by 20%
        ) * 100  # Scale to 0-100ish

        # Get equity curve stats
        eq = equity_curves.get(m.name)
        final_eq = eq.iloc[-1] if eq is not None else 0
        start_eq = eq.iloc[0] if eq is not None else 0
        eq_return = (final_eq / start_eq - 1) * 100 if start_eq > 0 else 0

        leaderboard.append({
            "model": m,
            "name": m.name,
            "score": score,
            "sharpe": met.sharpe_ratio,
            "sortino": met.sortino_ratio,
            "win_rate": met.win_rate,
            "return": eq_return,
            "max_dd": met.max_drawdown,
            "trades": met.num_trades,
            "weight": weights.get(m.name, 0),
            "pf": met.profit_factor,
        })

    leaderboard.sort(key=lambda x: x["score"], reverse=True)

    lb_rows = []
    for rank, entry in enumerate(leaderboard, 1):
        medal = {1: "1st", 2: "2nd", 3: "3rd"}.get(rank, f"{rank}th")
        lb_rows.append({
            "Rank": medal,
            "Model": entry["name"],
            "Score": f"{entry['score']:.1f}",
            "Sharpe": f"{entry['sharpe']:.3f}",
            "Sortino": f"{entry['sortino']:.3f}",
            "Win Rate": f"{entry['win_rate']:.1%}",
            "Return": f"{entry['return']:+.2f}%",
            "Max DD": f"{entry['max_dd']:.2%}",
            "Trades": entry["trades"],
            "Weight": f"{entry['weight']:.1%}",
            "PF": f"{min(entry['pf'], 10):.2f}",
        })
    st.dataframe(pd.DataFrame(lb_rows), width="stretch", hide_index=True, height=min(400, 40 + 35 * len(lb_rows)))

    # ── Score Visualization ──────────────────────────────────────────────
    col_score, col_radar = st.columns(2)

    with col_score:
        st.markdown("#### Composite Score Ranking")
        names = [e["name"] for e in leaderboard]
        scores = [e["score"] for e in leaderboard]
        colors = ["#ffffff" if s > 0 else "#555555" for s in scores]

        fig_score = go.Figure(data=[go.Bar(
            x=scores, y=names,
            orientation="h",
            marker_color=colors,
            text=[f"{s:.1f}" for s in scores],
            textposition="outside",
        )])
        fig_score.update_layout(
            height=max(220, 32 * len(names)),
            template="plotly_dark",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            xaxis=dict(title="Composite Score", gridcolor="#1e1e22"),
            yaxis=dict(gridcolor="#1e1e22", autorange="reversed"),
            margin=dict(l=120, r=60, t=20, b=40),
        )
        st.plotly_chart(fig_score, use_container_width=True)

    with col_radar:
        st.markdown("#### Top 3 Model Comparison")
        top3 = leaderboard[:3]
        categories = ["Sharpe", "Win Rate", "Return", "Low DD", "Profit Factor"]

        fig_radar = go.Figure()
        radar_colors = ["#ffffff", "#999999", "#555555"]

        for i, entry in enumerate(top3):
            # Normalize each metric to 0-1 for radar
            sharpe_norm = min(max((entry["sharpe"] + 1) / 3, 0), 1)
            wr_norm = entry["win_rate"]
            ret_norm = min(max((entry["return"] + 20) / 40, 0), 1)
            dd_norm = 1 - min(abs(entry["max_dd"]) / 0.2, 1)
            pf_norm = min(entry["pf"] / 3, 1)

            values = [sharpe_norm, wr_norm, ret_norm, dd_norm, pf_norm]
            values.append(values[0])  # Close the polygon
            cats = categories + [categories[0]]

            fig_radar.add_trace(go.Scatterpolar(
                r=values, theta=cats,
                name=entry["name"],
                line=dict(color=radar_colors[i], width=2),
                fill="toself",
                fillcolor=radar_colors[i].replace(")", ", 0.1)").replace("rgb", "rgba")
                    if "rgb" in radar_colors[i]
                    else f"rgba({int(radar_colors[i][1:3],16)},{int(radar_colors[i][3:5],16)},{int(radar_colors[i][5:7],16)},0.1)",
            ))

        fig_radar.update_layout(
            height=300,
            template="plotly_dark",
            paper_bgcolor="rgba(0,0,0,0)",
            polar=dict(
                bgcolor="#000000",
                radialaxis=dict(visible=True, range=[0, 1], gridcolor="#1e1e22"),
                angularaxis=dict(gridcolor="#1e1e22"),
            ),
            margin=dict(l=60, r=60, t=30, b=30),
            legend=dict(orientation="h", yanchor="bottom", y=-0.15),
        )
        st.plotly_chart(fig_radar, use_container_width=True)

    # ── Head-to-Head Comparison ──────────────────────────────────────────
    st.divider()
    st.markdown("#### Head-to-Head Comparison")

    h2h_options = [m.name for m in models_list]
    col_m1, col_m2 = st.columns(2)
    with col_m1:
        model_a = st.selectbox("Model A", h2h_options, index=0, key="h2h_a")
    with col_m2:
        default_b = min(1, len(h2h_options) - 1)
        model_b = st.selectbox("Model B", h2h_options, index=default_b, key="h2h_b")

    if model_a != model_b:
        eq_a = equity_curves.get(model_a)
        eq_b = equity_curves.get(model_b)

        if eq_a is not None and eq_b is not None:
            # Equity comparison
            fig_h2h = go.Figure()
            fig_h2h.add_trace(go.Scatter(
                x=test_df["timestamp"], y=eq_a,
                name=model_a, line=dict(color="#ffffff", width=2),
            ))
            fig_h2h.add_trace(go.Scatter(
                x=test_df["timestamp"], y=eq_b,
                name=model_b, line=dict(color="#888888", width=2),
            ))
            fig_h2h.update_layout(
                height=280,
                template="plotly_dark",
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                yaxis=dict(title="Equity ($)", gridcolor="#1e1e22", tickprefix="$"),
                xaxis=dict(gridcolor="#1e1e22"),
                margin=dict(l=60, r=20, t=20, b=40),
                legend=dict(orientation="h", yanchor="bottom", y=1.02),
                hovermode="x unified",
            )
            st.plotly_chart(fig_h2h, use_container_width=True)

            # Rolling relative performance
            rel_perf = (eq_a / eq_a.iloc[0]) / (eq_b / eq_b.iloc[0]) * 100 - 100
            fig_rel = go.Figure()
            fig_rel.add_trace(go.Scatter(
                x=test_df["timestamp"], y=rel_perf,
                fill="tozeroy",
                fillcolor="rgba(255, 255, 255, 0.06)",
                line=dict(color="#ffffff", width=1.5),
                name=f"{model_a} vs {model_b}",
            ))
            fig_rel.add_hline(y=0, line_dash="dash", line_color="#27272a")
            fig_rel.update_layout(
                height=200,
                template="plotly_dark",
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                yaxis=dict(title="Relative Performance (%)", gridcolor="#1e1e22", ticksuffix="%"),
                xaxis=dict(gridcolor="#1e1e22"),
                margin=dict(l=60, r=20, t=20, b=40),
                showlegend=False,
            )
            st.plotly_chart(fig_rel, use_container_width=True)

            # Metrics comparison table
            ma_entry = next((e for e in leaderboard if e["name"] == model_a), None)
            mb_entry = next((e for e in leaderboard if e["name"] == model_b), None)
            if ma_entry and mb_entry:
                comp_rows = []
                metrics_compare = [
                    ("Composite Score", "score", ".1f", ""),
                    ("Sharpe Ratio", "sharpe", ".3f", ""),
                    ("Win Rate", "win_rate", ".1%", ""),
                    ("Return", "return", "+.2f", "%"),
                    ("Max Drawdown", "max_dd", ".2%", ""),
                    ("Profit Factor", "pf", ".2f", ""),
                    ("Trades", "trades", "d", ""),
                    ("Weight", "weight", ".1%", ""),
                ]
                for label, key, fmt, suffix in metrics_compare:
                    va = ma_entry[key]
                    vb = mb_entry[key]
                    # Determine winner (higher is better for most, lower for dd)
                    if key == "max_dd":
                        winner = model_a if abs(va) < abs(vb) else model_b if abs(vb) < abs(va) else "Tie"
                    else:
                        winner = model_a if va > vb else model_b if vb > va else "Tie"
                    comp_rows.append({
                        "Metric": label,
                        model_a: f"{va:{fmt}}{suffix}",
                        model_b: f"{vb:{fmt}}{suffix}",
                        "Winner": winner,
                    })
                st.dataframe(pd.DataFrame(comp_rows), width="stretch", hide_index=True)
    else:
        st.info("Select two different models to compare.")


# ═══════════════════════════════════════════════════════════════════════════
# TAB 4: CAPITAL ALLOCATION
# ═══════════════════════════════════════════════════════════════════════════

if selected_page == "Allocation":
    st.markdown("#### Capital Allocation")

    col_pie, col_bar = st.columns(2)

    with col_pie:
        st.markdown("#### Weight Distribution")
        w = data["weights"]
        fig_pie = go.Figure(data=[go.Pie(
            labels=list(w.keys()),
            values=list(w.values()),
            hole=0.45,
            marker=dict(colors=["#ffffff", "#dddddd", "#bbbbbb", "#999999", "#777777", "#555555", "#444444", "#333333", "#aaaaaa"]),
            textinfo="label+percent",
            textfont=dict(size=11),
        )])
        fig_pie.update_layout(
            height=320,
            template="plotly_dark",
            paper_bgcolor="rgba(0,0,0,0)",
            margin=dict(l=20, r=20, t=30, b=20),
            showlegend=False,
        )
        st.plotly_chart(fig_pie, use_container_width=True)

    with col_bar:
        st.markdown("#### Dollar Allocation")
        alloc = data["allocator"]
        cap = alloc.capital_map
        fig_alloc = go.Figure(data=[go.Bar(
            x=list(cap.keys()),
            y=list(cap.values()),
            marker_color=["#ffffff", "#dddddd", "#bbbbbb", "#999999", "#777777", "#555555", "#444444", "#333333", "#aaaaaa"][:len(cap)],
            text=[f"${v:,.0f}" for v in cap.values()],
            textposition="outside",
        )])
        fig_alloc.update_layout(
            height=320,
            template="plotly_dark",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            yaxis=dict(title="Allocation ($)", gridcolor="#1e1e22", tickprefix="$"),
            xaxis=dict(gridcolor="#1e1e22"),
            margin=dict(l=60, r=20, t=30, b=80),
        )
        st.plotly_chart(fig_alloc, use_container_width=True)

    st.markdown("#### Scoring Breakdown")
    st.markdown("""
    **Scoring Formula:** `score = 0.35 × Sharpe + 0.25 × Sortino − 0.25 × |MaxDD| + 0.15 × ProfitFactor`

    Models with fewer than 10 trades receive a 50% penalty. Weights are constrained between 5% and 60%.
    """)

    score_rows = []
    for m in data["models"]:
        met = m.metrics
        score = (
            0.35 * max(met.sharpe_ratio, 0)
            + 0.25 * max(met.sortino_ratio, 0)
            - 0.25 * abs(met.max_drawdown)
            + 0.15 * min(met.profit_factor, 5.0)
        )
        if met.num_trades < 10:
            score *= 0.5
        score_rows.append({
            "Model": m.name,
            "Sharpe Contrib": round(0.35 * max(met.sharpe_ratio, 0), 4),
            "Sortino Contrib": round(0.25 * max(met.sortino_ratio, 0), 4),
            "DD Penalty": round(-0.25 * abs(met.max_drawdown), 4),
            "PF Contrib": round(0.15 * min(met.profit_factor, 5.0), 4),
            "Raw Score": round(score, 4),
            "Final Weight": f"{data['weights'].get(m.name, 0):.1%}",
        })
    st.dataframe(pd.DataFrame(score_rows), width="stretch", hide_index=True)


# ═══════════════════════════════════════════════════════════════════════════
# TAB 4: RISK MANAGEMENT
# ═══════════════════════════════════════════════════════════════════════════

if selected_page == "Risk":
    st.markdown("#### Risk Management")

    # Risk status cards
    col_r1, col_r2, col_r3, col_r4 = st.columns(4)

    risk_mgr = data["risk"]
    portfolio_dd = abs(drawdown)

    col_r1.metric("System Status", "ACTIVE" if not risk_mgr.is_halted else "HALTED")
    col_r2.metric("Current Drawdown", f"{portfolio_dd:.2f}%", delta="Within Limits" if portfolio_dd < 15 else "BREACH", delta_color="normal" if portfolio_dd < 15 else "inverse")
    col_r3.metric("DD Limit", "15.0%")
    col_r4.metric("Open Positions", "0 (Demo)")

    st.divider()

    # Risk parameters
    col_params, col_gauge = st.columns(2)

    with col_params:
        st.markdown("#### Risk Parameters")
        risk_params = pd.DataFrame([
            {"Parameter": "Max Position Size", "Value": "10%", "Status": "OK"},
            {"Parameter": "Max Portfolio Exposure", "Value": "80%", "Status": "OK"},
            {"Parameter": "Max Drawdown Shutdown", "Value": "15%", "Status": "OK" if portfolio_dd < 15 else "BREACH"},
            {"Parameter": "Per-Position Stop Loss", "Value": "3%", "Status": "OK"},
            {"Parameter": "Trade Frequency Limit", "Value": "20/hr", "Status": "OK"},
        ])
        st.dataframe(risk_params, width="stretch", hide_index=True, height=220)

    with col_gauge:
        st.markdown("#### Drawdown Gauge")
        fig_gauge = go.Figure(go.Indicator(
            mode="gauge+number",
            value=portfolio_dd,
            domain=dict(x=[0, 1], y=[0, 1]),
            gauge=dict(
                axis=dict(range=[0, 20], ticksuffix="%"),
                bar=dict(color="#ffffff"),
                bgcolor="#09090b",
                steps=[
                    dict(range=[0, 5], color="#111113"),
                    dict(range=[5, 10], color="#18181b"),
                    dict(range=[10, 15], color="#1e1e22"),
                    dict(range=[15, 20], color="#27272a"),
                ],
                threshold=dict(line=dict(color="#ffffff", width=4), thickness=0.8, value=15),
            ),
            number=dict(suffix="%", font=dict(size=36)),
            title=dict(text="Portfolio Drawdown", font=dict(size=14)),
        ))
        fig_gauge.update_layout(
            height=240,
            template="plotly_dark",
            paper_bgcolor="rgba(0,0,0,0)",
            margin=dict(l=20, r=20, t=40, b=20),
        )
        st.plotly_chart(fig_gauge, use_container_width=True)

    st.markdown("#### Model-Level Risk")
    risk_rows = []
    for m in data["models"]:
        met = m.metrics
        risk_rows.append({
            "Model": m.name,
            "Max Drawdown": f"{met.max_drawdown:.2%}",
            "Sharpe": round(met.sharpe_ratio, 3),
            "Win Rate": f"{met.win_rate:.1%}",
            "Allocation": f"${data['allocator'].get_allocation(m.name):,.0f}",
            "Risk Rating": "Low" if abs(met.max_drawdown) < 0.05 else "Medium" if abs(met.max_drawdown) < 0.10 else "High",
        })
    st.dataframe(pd.DataFrame(risk_rows), width="stretch", hide_index=True)

    st.markdown("#### Signal Quality Gates")
    st.markdown(
        "Signals must pass these gates before execution. "
        "Weak, unproven, or low-consensus signals are rejected automatically."
    )
    gate_params = pd.DataFrame([
        {"Gate": "Minimum Signal Strength", "Threshold": f"{risk_mgr.MIN_SIGNAL_STRENGTH:.2f}", "Purpose": "Reject ambiguous/weak signals"},
        {"Gate": "Minimum Model Trades", "Threshold": str(risk_mgr.MIN_TRADES_FOR_TRUST), "Purpose": "Model must have track record"},
        {"Gate": "Minimum Model Sharpe", "Threshold": f"{risk_mgr.MIN_MODEL_SHARPE:.1f}", "Purpose": "Reject consistently losing models"},
        {"Gate": "Minimum Weight to Signal", "Threshold": f"{risk_mgr.MIN_WEIGHT_TO_SIGNAL:.2f}", "Purpose": "Near-zero weight models can't trade"},
        {"Gate": "Minimum Consensus Ratio", "Threshold": f"{risk_mgr.MIN_CONSENSUS_RATIO:.0%}", "Purpose": "Ensemble must agree on direction"},
    ])
    st.dataframe(gate_params, width="stretch", hide_index=True)

    # Run quality gate simulation on current signals
    st.markdown("#### Quality Gate Simulation (Current Signals)")
    gate_results = []
    for m in data["models"]:
        # Get latest signal from each model
        sigs = m.predict(data["full_df"])
        if sigs:
            sig = sigs[0]
            passed, reason = risk_mgr.validate_signal_quality(
                signal=sig,
                model_metrics=m.metrics.to_dict(),
                model_weight=data["weights"].get(m.name, 0),
            )
            gate_results.append({
                "Model": m.name,
                "Signal": f"{sig.direction.upper()} ({sig.strength:.3f})",
                "Weight": f"{data['weights'].get(m.name, 0):.1%}",
                "Status": "PASS" if passed else "REJECTED",
                "Reason": reason if not passed else "-",
            })
    if gate_results:
        gate_df = pd.DataFrame(gate_results)
        st.dataframe(gate_df, width="stretch", hide_index=True)
        passed_count = sum(1 for g in gate_results if g["Status"] == "PASS")
        st.caption(f"{passed_count}/{len(gate_results)} signals passed quality gates")


# ═══════════════════════════════════════════════════════════════════════════
# TAB 5: REGIME DETECTION
# ═══════════════════════════════════════════════════════════════════════════

if selected_page == "Regime":
    st.markdown("#### Market Regime")

    # Current regime
    col_curr, col_hist = st.columns([1, 2])

    with col_curr:
        st.markdown("#### Current Regime")
        regime_display = {
            "low_vol_bull": ("Low Vol Bull", "Trending up with low volatility. Momentum strategies favored."),
            "high_vol_bull": ("High Vol Bull", "Trending up but volatile. Reduced position sizes recommended."),
            "low_vol_bear": ("Low Vol Bear", "Trending down steadily. Mean reversion opportunities limited."),
            "high_vol_bear": ("High Vol Bear", "Sharp selloff. Risk management critical."),
            "sideways": ("Sideways", "Range-bound. Mean reversion strategies may outperform."),
        }
        info = regime_display.get(regime_label, ("Unknown", ""))
        st.markdown(f"### {info[0]}")
        st.markdown(info[1])
        st.markdown(f"**Confidence:** {regime['confidence']:.0%}")
        st.markdown(f"**20d Volatility:** {regime['volatility_20d']:.2%}")
        st.markdown(f"**Trend Strength:** {regime['trend_strength']:.6f}")

    with col_hist:
        st.markdown("#### Regime History")
        if data["regime_history"]:
            rh_df = pd.DataFrame(data["regime_history"])
            st.dataframe(rh_df, width="stretch", hide_index=True, height=300)

    st.markdown("#### Rolling Volatility")
    full_df = data["full_df"]
    log_ret = np.log(full_df["close"] / full_df["close"].shift(1))
    vol_20 = log_ret.rolling(20).std() * np.sqrt(252) * 100
    vol_60 = log_ret.rolling(60).std() * np.sqrt(252) * 100

    fig_vol = go.Figure()
    fig_vol.add_trace(go.Scatter(
        x=full_df["timestamp"], y=vol_20,
        name="20-day Vol", line=dict(color="#ffffff", width=2),
    ))
    fig_vol.add_trace(go.Scatter(
        x=full_df["timestamp"], y=vol_60,
        name="60-day Vol", line=dict(color="#888888", width=2),
    ))
    fig_vol.add_hline(y=vol_20.median(), line_dash="dash", line_color="#27272a",
                      annotation_text="Median Vol")
    fig_vol.update_layout(
        height=280,
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        yaxis=dict(title="Annualized Volatility %", gridcolor="#1e1e22", ticksuffix="%"),
        xaxis=dict(gridcolor="#1e1e22"),
        margin=dict(l=60, r=20, t=20, b=40),
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
    )
    st.plotly_chart(fig_vol, use_container_width=True)


# ═══════════════════════════════════════════════════════════════════════════
# TAB: STRATEGY BUILDER
# ═══════════════════════════════════════════════════════════════════════════

if selected_page == "Strategy Builder":
    st.markdown("#### Strategy Builder")

    # ── Strategy Type Selector ──
    builder_col1, builder_col2 = st.columns([1, 2])

    with builder_col1:
        strategy_type = st.selectbox(
            "Strategy Type",
            ["Momentum", "Mean Reversion", "Breakout", "Volatility Squeeze"],
            key="builder_strategy_type",
        )

        st.markdown("---")
        st.markdown("#### Parameters")

        # Dynamic parameter sliders based on strategy type
        if strategy_type == "Momentum":
            b_fast = st.slider("Fast MA Window", 3, 30, 10, key="b_fast")
            b_slow = st.slider("Slow MA Window", 15, 200, 50, key="b_slow")
            b_rsi = st.slider("RSI Period", 5, 30, 14, key="b_rsi")
            b_rsi_upper = st.slider("RSI Upper", 55.0, 80.0, 65.0, step=1.0, key="b_rsi_upper")
            b_rsi_lower = st.slider("RSI Lower", 20.0, 45.0, 35.0, step=1.0, key="b_rsi_lower")
            b_trend = st.slider("Trend Filter Window", 50, 200, 100, key="b_trend")

        elif strategy_type == "Mean Reversion":
            b_lookback = st.slider("Lookback Window", 5, 60, 20, key="b_lookback")
            b_entry_z = st.slider("Entry Z-Score", 0.8, 3.5, 1.8, step=0.1, key="b_entry_z")
            b_exit_z = st.slider("Exit Z-Score", 0.1, 1.5, 0.3, step=0.1, key="b_exit_z")
            b_mr_rsi = st.slider("RSI Period", 5, 30, 14, key="b_mr_rsi")
            b_rsi_ext = st.slider("RSI Extreme", 15.0, 40.0, 25.0, step=1.0, key="b_rsi_ext")

        elif strategy_type == "Breakout":
            b_channel = st.slider("Channel Window", 10, 50, 20, key="b_channel")
            b_vol_mult = st.slider("Volume Multiplier", 1.0, 3.0, 1.5, step=0.1, key="b_vol_mult")
            b_atr_stop = st.slider("ATR Stop Multiplier", 1.0, 4.0, 2.0, step=0.25, key="b_atr_stop")

        elif strategy_type == "Volatility Squeeze":
            b_bb_win = st.slider("Bollinger Window", 10, 40, 20, key="b_bb_win")
            b_bb_std = st.slider("Bollinger Std Dev", 1.0, 3.0, 2.0, step=0.1, key="b_bb_std")
            b_atr_per = st.slider("ATR Period", 7, 28, 14, key="b_atr_per")
            b_mom_win = st.slider("Momentum Window", 5, 30, 12, key="b_mom_win")

        st.markdown("---")
        b_train_ratio = st.slider("Train/Test Split", 0.5, 0.9, 0.7, step=0.05, key="b_train_ratio")
        run_backtest = st.button("Run Backtest", type="primary", width="stretch", key="run_builder_bt")

    with builder_col2:
        if run_backtest:
            with st.spinner("Building and backtesting strategy..."):
                from models.momentum import MomentumModel
                from models.mean_reversion import MeanReversionModel
                from models.breakout import BreakoutModel
                from models.volatility import VolatilityModel
                from engine.backtester import BacktestEngine

                # Build model from parameters
                if strategy_type == "Momentum":
                    if b_fast >= b_slow - 5:
                        st.error(f"Fast window ({b_fast}) must be at least 6 less than slow window ({b_slow}).")
                    else:
                        custom_model = MomentumModel(
                            name="Custom Momentum",
                            fast_window=b_fast,
                            slow_window=b_slow,
                            rsi_period=b_rsi,
                            rsi_upper=b_rsi_upper,
                            rsi_lower=b_rsi_lower,
                            trend_filter_window=b_trend,
                        )
                elif strategy_type == "Mean Reversion":
                    if b_exit_z >= b_entry_z:
                        st.error("Exit Z must be less than Entry Z.")
                        custom_model = None
                    else:
                        custom_model = MeanReversionModel(
                            name="Custom Mean Reversion",
                            lookback=b_lookback,
                            entry_z=b_entry_z,
                            exit_z=b_exit_z,
                            rsi_period=b_mr_rsi,
                            rsi_extreme=b_rsi_ext,
                        )
                elif strategy_type == "Breakout":
                    custom_model = BreakoutModel(
                        name="Custom Breakout",
                        channel_window=b_channel,
                        volume_mult=b_vol_mult,
                        atr_stop_mult=b_atr_stop,
                    )
                elif strategy_type == "Volatility Squeeze":
                    custom_model = VolatilityModel(
                        name="Custom Vol Squeeze",
                        bb_window=b_bb_win,
                        bb_std=b_bb_std,
                        atr_period=b_atr_per,
                        momentum_window=b_mom_win,
                    )
                else:
                    custom_model = None

                if custom_model is not None:
                    # Use real market data from the dashboard
                    full_df = data["full_df"]
                    split_idx = int(len(full_df) * b_train_ratio)
                    train_df = full_df.iloc[:split_idx]
                    test_df = full_df.iloc[split_idx:]

                    # Train with grid search (the model's actual train method)
                    custom_model.train(train_df)
                    custom_model.evaluate(test_df)

                    # Generate equity curve bar-by-bar
                    positions = []
                    for i in range(len(test_df)):
                        window = full_df.iloc[:split_idx + i + 1]
                        sigs = custom_model.predict(window)
                        if sigs and sigs[0].direction == "long":
                            positions.append(sigs[0].strength)
                        elif sigs and sigs[0].direction == "short":
                            positions.append(-sigs[0].strength)
                        else:
                            positions.append(0.0)

                    pos_series = pd.Series(positions, index=test_df.index)
                    price_rets = test_df["close"].pct_change().fillna(0)
                    strat_rets = pos_series.shift(1).fillna(0) * price_rets
                    custom_equity = 100_000 * (1 + strat_rets).cumprod()

                    # ── Results Display ──
                    st.markdown("### Backtest Results")
                    m = custom_model.metrics

                    # Metrics row
                    mc1, mc2, mc3, mc4, mc5 = st.columns(5)
                    mc1.metric("Sharpe", f"{m.sharpe_ratio:.3f}")
                    mc2.metric("Sortino", f"{m.sortino_ratio:.3f}")
                    mc3.metric("Win Rate", f"{m.win_rate:.1%}")
                    mc4.metric("Max DD", f"{m.max_drawdown:.2%}")
                    mc5.metric("Return", f"{m.total_return:.2%}")

                    # Equity curve
                    fig_eq = go.Figure()
                    fig_eq.add_trace(go.Scatter(
                        x=test_df["timestamp"] if "timestamp" in test_df.columns else test_df.index,
                        y=custom_equity,
                        mode="lines",
                        name=custom_model.name,
                        line=dict(color="#ffffff", width=2),
                    ))

                    # Overlay combined portfolio for comparison
                    combined_eq = data["combined_equity"]
                    fig_eq.add_trace(go.Scatter(
                        x=data["test_df"]["timestamp"] if "timestamp" in data["test_df"].columns else data["test_df"].index,
                        y=combined_eq,
                        mode="lines",
                        name="Portfolio (Existing)",
                        line=dict(color="#555555", width=1, dash="dash"),
                    ))

                    fig_eq.update_layout(
                        height=350,
                        template="plotly_dark",
                        paper_bgcolor="rgba(0,0,0,0)",
                        plot_bgcolor="rgba(0,0,0,0)",
                        xaxis=dict(gridcolor="#1e1e22"),
                        yaxis=dict(gridcolor="#1e1e22", tickprefix="$"),
                        margin=dict(l=60, r=20, t=30, b=40),
                        legend=dict(orientation="h", y=1.12),
                    )
                    st.plotly_chart(fig_eq, use_container_width=True, key="builder_equity_chart")

                    # Position heatmap
                    st.markdown("#### Position Over Time")
                    fig_pos = go.Figure()
                    fig_pos.add_trace(go.Bar(
                        x=test_df["timestamp"] if "timestamp" in test_df.columns else test_df.index,
                        y=pos_series,
                        marker_color=[
                            "#ffffff" if p > 0 else "#555555" if p < 0 else "#1a1a1a"
                            for p in pos_series
                        ],
                    ))
                    fig_pos.update_layout(
                        height=200,
                        template="plotly_dark",
                        paper_bgcolor="rgba(0,0,0,0)",
                        plot_bgcolor="rgba(0,0,0,0)",
                        xaxis=dict(gridcolor="#1e1e22"),
                        yaxis=dict(gridcolor="#1e1e22", title="Position Size"),
                        margin=dict(l=60, r=20, t=10, b=40),
                        showlegend=False,
                    )
                    st.plotly_chart(fig_pos, use_container_width=True, key="builder_pos_chart")

                    # Comparison table against all existing models
                    st.markdown("#### vs. Existing Models")
                    compare_rows = []
                    for em in data["models"]:
                        compare_rows.append({
                            "Model": em.name,
                            "Sharpe": round(em.metrics.sharpe_ratio, 3),
                            "Sortino": round(em.metrics.sortino_ratio, 3),
                            "Win Rate": f"{em.metrics.win_rate:.1%}",
                            "Return": f"{em.metrics.total_return:.2%}",
                            "Max DD": f"{em.metrics.max_drawdown:.2%}",
                        })
                    compare_rows.insert(0, {
                        "Model": f"{custom_model.name}",
                        "Sharpe": round(m.sharpe_ratio, 3),
                        "Sortino": round(m.sortino_ratio, 3),
                        "Win Rate": f"{m.win_rate:.1%}",
                        "Return": f"{m.total_return:.2%}",
                        "Max DD": f"{m.max_drawdown:.2%}",
                    })
                    compare_df = pd.DataFrame(compare_rows)

                    # Highlight custom row
                    def highlight_custom(row):
                        if row["Model"].startswith("Custom"):
                            return ["background-color: #111111; font-weight: bold"] * len(row)
                        return [""] * len(row)

                    st.dataframe(
                        compare_df.style.apply(highlight_custom, axis=1),
                        width="stretch",
                        hide_index=True,
                    )

                    # Trained parameters (what grid search found)
                    if custom_model._artifact:
                        st.markdown("#### Optimized Parameters")
                        st.json(custom_model._artifact)

                    # Trade statistics
                    st.markdown("#### Trade Statistics")
                    total_bars = len(test_df)
                    active_bars = (pos_series != 0).sum()
                    long_bars = (pos_series > 0).sum()
                    short_bars = (pos_series < 0).sum()
                    ts1, ts2, ts3, ts4 = st.columns(4)
                    ts1.metric("Total Bars", f"{total_bars}")
                    ts2.metric("Active Bars", f"{active_bars}", f"{active_bars/total_bars:.0%}")
                    ts3.metric("Long Bars", f"{long_bars}")
                    ts4.metric("Short Bars", f"{short_bars}")

        else:
            # Default state: show strategy descriptions and parameter guides
            st.markdown("### Strategy Types")

            st.markdown("""
**Momentum** — Trend-following with adaptive MA crossovers, RSI confirmation, and MACD histogram.
Enters when fast MA crosses above slow MA with RSI and MACD confirming. Best in trending markets.

**Mean Reversion** — Trades statistical deviations from equilibrium using z-scores and Bollinger Bands.
Enters at extreme z-scores when RSI confirms oversold/overbought. Best in range-bound markets.

**Breakout** — Rolling channel breakout with volume surge confirmation and ATR trailing stops.
Enters when price breaks resistance/support with above-average volume. Best at regime transitions.

**Volatility Squeeze** — Exploits Bollinger Band compression and subsequent expansion.
Enters when volatility compresses below historical norms, then expands directionally. Best pre-breakout.
""")

            st.markdown("### How It Works")
            st.markdown("""
1. **Select** a strategy type and tune parameters with the sliders
2. **Click Run Backtest** — the model trains on real data using grid search optimization
3. **Compare** your custom strategy's metrics against all 9 existing models
4. **Iterate** — adjust parameters and re-run to improve performance
""")

            # Show current model performance as reference
            st.markdown("### Current Model Leaderboard (Reference)")
            ref_rows = sorted(
                [{"Model": m.name, "Sharpe": m.metrics.sharpe_ratio, "Return": m.metrics.total_return}
                 for m in data["models"]],
                key=lambda x: x["Sharpe"],
                reverse=True,
            )
            ref_df = pd.DataFrame(ref_rows)
            ref_df["Sharpe"] = ref_df["Sharpe"].round(3)
            ref_df["Return"] = ref_df["Return"].apply(lambda x: f"{x:.2%}")
            st.dataframe(ref_df, width="stretch", hide_index=True)


# ═══════════════════════════════════════════════════════════════════════════
# TAB 6: TRADE LOG
# ═══════════════════════════════════════════════════════════════════════════

if selected_page == "Trades":
    st.markdown("#### Trade Log")

    if data["trade_log"]:
        tl_df = pd.DataFrame(data["trade_log"])

        # Filters
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            model_filter = st.multiselect("Filter by Model", options=tl_df["Model"].unique(), default=tl_df["Model"].unique())
        with col_f2:
            direction_filter = st.multiselect("Filter by Direction", options=tl_df["Direction"].unique(), default=tl_df["Direction"].unique())

        filtered = tl_df[(tl_df["Model"].isin(model_filter)) & (tl_df["Direction"].isin(direction_filter))]
        st.dataframe(filtered, width="stretch", hide_index=True, height=400)

        # Trade distribution
        col_td1, col_td2 = st.columns(2)

        with col_td1:
            st.markdown("#### Trades by Model")
            trade_counts = filtered["Model"].value_counts()
            fig_tc = go.Figure(data=[go.Bar(
                x=trade_counts.index, y=trade_counts.values,
                marker_color=px.colors.qualitative.Set2[:len(trade_counts)],
            )])
            fig_tc.update_layout(
                height=300, template="plotly_dark", paper_bgcolor="#000000",
                plot_bgcolor="rgba(0,0,0,0)",
                yaxis=dict(title="Count", gridcolor="#1e1e22"),
                xaxis=dict(gridcolor="#1e1e22"),
                margin=dict(l=60, r=20, t=20, b=80),
            )
            st.plotly_chart(fig_tc, use_container_width=True)

        with col_td2:
            st.markdown("#### Direction Distribution")
            dir_counts = filtered["Direction"].value_counts()
            fig_dir = go.Figure(data=[go.Pie(
                labels=dir_counts.index, values=dir_counts.values,
                marker=dict(colors=["#ffffff", "#555555", "#777777"]),
                hole=0.4,
            )])
            fig_dir.update_layout(
                height=300, template="plotly_dark", paper_bgcolor="#000000",
                margin=dict(l=20, r=20, t=20, b=20),
            )
            st.plotly_chart(fig_dir, use_container_width=True)

    else:
        st.info("No trades recorded yet.")


# ═══════════════════════════════════════════════════════════════════════════
# TAB: LIVE TRADING (Webull)
# ═══════════════════════════════════════════════════════════════════════════

if selected_page == "Live Trading":
    if not use_webull or _wb_client is None:
        st.info("Switch to Webull Live mode in the sidebar to enable live trading.")
    elif not _wb_client.is_connected:
        st.warning("Not connected to Webull. Use the sidebar login panel to connect.")
    else:
        # ── Mode banner — always visible at top ─────────────────────
        _is_paper = _wb_client.is_paper
        _is_live = _wb_client.is_live

        if _is_paper:
            st.markdown(
                '<div class="mode-banner-paper">'
                'PAPER TRADING MODE -- Simulated orders only, no real money'
                '</div>',
                unsafe_allow_html=True,
            )
            st.subheader("Paper Trading Console")
        else:
            st.markdown(
                '<div class="mode-banner-live">'
                'LIVE TRADING MODE -- REAL MONEY -- All orders execute on your brokerage account'
                '</div>',
                unsafe_allow_html=True,
            )
            st.subheader("Live Trading Console")

            # Live mode requires explicit enable
            from data.webull_client import WebullLiveClient
            if isinstance(_wb_client, WebullLiveClient) and not _wb_client.live_enabled:
                st.error(
                    "Live trading is LOCKED. You must enable it below before placing orders."
                )
                st.markdown("Type the exact confirmation phrase to unlock live order execution:")
                live_confirm = st.text_input(
                    "Type: I UNDERSTAND THIS USES REAL MONEY",
                    key="live_confirm_input",
                )
                if st.button("Enable Live Trading", key="enable_live_btn"):
                    if _wb_client.enable_live_trading(live_confirm):
                        st.success("Live trading enabled.")
                        st.rerun()
                    else:
                        st.error("Confirmation phrase does not match. Type it exactly.")

        # Connection status bar
        trade_status = "READY" if _wb_client.is_trade_ready else "CONNECTED (view only)"
        trade_color = "#ffffff" if _wb_client.is_trade_ready else "#888888"
        mode_tag = f'<span style="color:{"#ffffff" if _is_paper else "#888888"}; font-weight:700">[{_wb_client.mode_label}]</span>'
        st.markdown(
            f"**Status:** <span style='color:{trade_color}'>{trade_status}</span> "
            f"| **Mode:** {mode_tag} "
            f"| **API:** Official OpenAPI",
            unsafe_allow_html=True,
        )

        # ── Live Quotes ─────────────────────────────────────────────
        st.markdown("---")
        st.markdown("#### Market Watchlist")

        watchlist_input = st.text_input(
            "Symbols (comma-separated)",
            value="SPY, QQQ, AAPL, TSLA, NVDA, MSFT, AMZN, META",
            key="watchlist_symbols",
        )
        watchlist_symbols = [s.strip().upper() for s in watchlist_input.split(",") if s.strip()]

        if st.button("Refresh Quotes", key="refresh_quotes_btn"):
            st.cache_data.clear()

        quotes_df = _wb_client.get_watchlist_quotes(watchlist_symbols)
        if not quotes_df.empty:
            def _color_change(val):
                if isinstance(val, (int, float)):
                    color = "#ffffff" if val > 0 else "#555555" if val < 0 else "#777777"
                    return f"color: {color}"
                return ""

            styled = quotes_df.style.applymap(
                _color_change, subset=["Change", "Change %"]
            ).format({
                "Price": "${:.2f}",
                "Change": "{:+.2f}",
                "Change %": "{:+.2f}%",
                "Volume": "{:,.0f}",
                "Bid": "${:.2f}",
                "Ask": "${:.2f}",
            })
            st.dataframe(styled, width="stretch", hide_index=True, height=340)
        else:
            st.info("No quote data available. Check connection or try again.")

        # ── Account Overview ────────────────────────────────────────
        st.markdown("---")
        col_acct, col_positions = st.columns(2)

        with col_acct:
            acct_label = "Paper Account" if _is_paper else "Live Account"
            st.markdown(f"#### {acct_label} Summary")
            acct = _wb_client.get_account_summary()
            if acct:
                a1, a2 = st.columns(2)
                a1.metric("Net Liquidation", f"${acct['net_liquidation']:,.2f}")
                a2.metric("Buying Power", f"${acct['buying_power']:,.2f}")
                a3, a4 = st.columns(2)
                a3.metric("Cash Balance", f"${acct['cash_balance']:,.2f}")
                pnl = acct['unrealized_pnl']
                a4.metric("Unrealized P&L", f"${pnl:,.2f}",
                          delta=f"${pnl:+,.2f}", delta_color="normal" if pnl >= 0 else "inverse")
            else:
                st.info("Account data not available")

        with col_positions:
            st.markdown("#### Current Positions")
            positions = _wb_client.get_positions()
            if positions:
                pos_df = pd.DataFrame(positions)
                display_cols = ["symbol", "quantity", "avg_cost", "last_price",
                                "market_value", "unrealized_pnl", "unrealized_pnl_pct"]
                pos_display = pos_df[[c for c in display_cols if c in pos_df.columns]]
                pos_display.columns = [c.replace("_", " ").title() for c in pos_display.columns]
                st.dataframe(pos_display, width="stretch", hide_index=True, height=250)
            else:
                st.info("No open positions")

        # ── Order Entry ──────────────────────────────────────────────
        st.markdown("---")
        order_heading = "Place Paper Order" if _is_paper else "Place LIVE Order (REAL MONEY)"
        st.markdown(f"#### {order_heading}")

        # Block live orders if live trading is not enabled
        _order_blocked = False
        if _is_live:
            from data.webull_client import WebullLiveClient as _LiveCls
            if isinstance(_wb_client, _LiveCls) and not _wb_client.live_enabled:
                st.error("Live trading is not enabled. Scroll up to enable it first.")
                _order_blocked = True

        if not _wb_client.is_trade_ready:
            st.warning("No account found. Check your API credentials.")
        elif not _order_blocked:
            col_ord1, col_ord2, col_ord3, col_ord4, col_ord5 = st.columns([1.5, 1, 1, 1, 1])

            with col_ord1:
                order_symbol = st.text_input("Symbol", value="SPY", key="order_symbol")
            with col_ord2:
                order_action = st.selectbox("Side", ["BUY", "SELL"], key="order_action")
            with col_ord3:
                order_qty = st.number_input("Quantity", min_value=1, value=1, step=1, key="order_qty")
            with col_ord4:
                order_type = st.selectbox("Type", ["MKT", "LMT", "STP"], key="order_type")
            with col_ord5:
                order_price = st.number_input("Price", min_value=0.0, value=0.0, step=0.01,
                                              key="order_price",
                                              disabled=(order_type == "MKT"))

            col_place, col_tif = st.columns([2, 1])
            with col_tif:
                order_tif = st.selectbox("Time in Force", ["DAY", "GTC"], key="order_tif")
            with col_place:
                # Live mode gets an extra confirmation checkbox per order
                _can_submit = True
                if _is_live:
                    _can_submit = st.checkbox(
                        "I confirm this is a REAL MONEY order",
                        value=False,
                        key="live_order_confirm",
                    )

                submit_label = "Submit Paper Order" if _is_paper else "Submit LIVE Order"
                if st.button(submit_label, type="primary", width="stretch", key="submit_order_btn"):
                    if not _can_submit:
                        st.error("You must check the confirmation box for live orders.")
                    else:
                        limit_p = order_price if order_type == "LMT" else None
                        stop_p = order_price if order_type == "STP" else None
                        result = _wb_client.place_order(
                            symbol=order_symbol.upper(),
                            side=order_action,
                            qty=order_qty,
                            order_type=order_type,
                            limit_price=limit_p,
                            stop_price=stop_p,
                            tif=order_tif,
                            user_confirmed=True,
                        )
                        if result.get("success"):
                            mode_tag_order = result.get("mode", _wb_client.mode_label)
                            st.success(f"[{mode_tag_order}] Order placed: {order_action} {order_qty} {order_symbol.upper()} ({order_type})")
                        else:
                            st.error(f"Order failed: {result.get('error', 'Unknown error')}")

        # ── Open Orders ─────────────────────────────────────────────
        st.markdown("---")
        col_open, col_hist = st.columns(2)

        with col_open:
            st.markdown("#### Open Orders")
            open_orders = _wb_client.get_open_orders()
            if open_orders:
                oo_df = pd.DataFrame(open_orders)
                display_cols = ["symbol", "side", "order_type", "quantity", "price", "status"]
                oo_display = oo_df[[c for c in display_cols if c in oo_df.columns]]
                st.dataframe(oo_display, width="stretch", hide_index=True, height=200)

                cancel_id = st.text_input("Order ID to cancel", key="cancel_order_id")
                if st.button("Cancel Order", key="cancel_order_btn"):
                    if cancel_id:
                        res = _wb_client.cancel_order(cancel_id)
                        if res.get("success"):
                            st.success("Order cancelled")
                            st.rerun()
                        else:
                            st.error(res.get("error", "Cancel failed"))
            else:
                st.info("No open orders")

        with col_hist:
            st.markdown("#### Order History")
            history = _wb_client.get_order_history(count=20)
            if history:
                hist_df = pd.DataFrame(history)
                display_cols = ["symbol", "side", "order_type", "quantity",
                                "filled_qty", "price", "status"]
                hist_display = hist_df[[c for c in display_cols if c in hist_df.columns]]
                st.dataframe(hist_display, width="stretch", hide_index=True, height=200)
            else:
                st.info("No order history")

        # ── Live Chart ──────────────────────────────────────────────
        st.markdown("---")
        st.markdown("#### Live Price Chart")
        chart_symbol = st.text_input("Chart Symbol", value="SPY", key="chart_symbol")
        chart_interval = st.selectbox("Interval", ["m1", "m5", "m15", "m30", "h1", "d1"], index=1, key="chart_interval")

        bars = _wb_client.get_bars(chart_symbol.upper(), interval=chart_interval, count=200)
        if bars is not None and not bars.empty:
            fig_live = go.Figure()
            if all(c in bars.columns for c in ["open", "high", "low", "close"]):
                x_axis = bars["timestamp"] if "timestamp" in bars.columns else bars.index
                fig_live.add_trace(go.Candlestick(
                    x=x_axis,
                    open=bars["open"],
                    high=bars["high"],
                    low=bars["low"],
                    close=bars["close"],
                    name=chart_symbol.upper(),
                ))
            else:
                x_axis = bars["timestamp"] if "timestamp" in bars.columns else bars.index
                fig_live.add_trace(go.Scatter(
                    x=x_axis, y=bars["close"],
                    name=chart_symbol.upper(),
                    line=dict(color="#ffffff", width=2),
                ))

            fig_live.update_layout(
                height=450,
                template="plotly_dark",
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                xaxis=dict(gridcolor="#1e1e22", rangeslider=dict(visible=False)),
                yaxis=dict(gridcolor="#1e1e22", tickprefix="$"),
                margin=dict(l=60, r=20, t=20, b=40),
                showlegend=False,
            )
            st.plotly_chart(fig_live, key="live_chart_fig")
        else:
            st.info("No chart data available for this symbol/interval.")

        # ── Live mode: disable button ────────────────────────────────
        if _is_live:
            st.markdown("---")
            if st.button("Disable Live Trading", key="disable_live_btn"):
                from data.webull_client import WebullLiveClient as _LC
                if isinstance(_wb_client, _LC):
                    _wb_client.disable_live_trading()
                    st.info("Live trading disabled. Orders will be blocked.")
                    st.rerun()


# ═══════════════════════════════════════════════════════════════════════════
# TAB: PAPER TRADING
# ═══════════════════════════════════════════════════════════════════════════

if selected_page == "Paper Trading":
    if not _has_paper:
        st.info("Paper trading requires yfinance. Install with: pip install yfinance")
    elif not _user_id:
        st.info("Please log in to use paper trading.")
    else:
        # Portfolio summary
        summary = get_portfolio_summary(_user_id)

        col_cash, col_positions, col_equity, col_pnl = st.columns(4)
        col_cash.metric("Cash", f"${summary['cash']:,.0f}")
        col_positions.metric("Positions", f"${summary['positions_value']:,.0f}")
        col_equity.metric("Equity", f"${summary['total_equity']:,.0f}")
        pnl_delta = f"{summary['total_pnl_pct']:+.2f}%"
        col_pnl.metric("P&L", f"${summary['total_pnl']:+,.0f}", delta=pnl_delta)

        # Trade execution + Watchlist side by side
        col_trade, col_watchlist = st.columns([1, 2])

        with col_trade:
            st.markdown("**Place Trade**")
            with st.form("paper_trade_form"):
                trade_symbol = st.text_input("Symbol", value="SPY", placeholder="SPY, AAPL, BTC-USD")
                trade_qty = st.number_input("Quantity", min_value=0.01, value=10.0, step=1.0)

                # Price preview inside form
                if trade_symbol:
                    live_price = get_current_price(trade_symbol)
                    if live_price > 0:
                        st.caption(f"{trade_symbol.upper()} @ ${live_price:,.2f} — est. ${live_price * trade_qty:,.2f}")

                col_buy, col_sell = st.columns(2)
                buy_btn = col_buy.form_submit_button("Buy", use_container_width=True)
                sell_btn = col_sell.form_submit_button("Sell", use_container_width=True)

                if buy_btn:
                    ok, msg = execute_buy(_user_id, trade_symbol, trade_qty)
                    if ok:
                        st.success(msg)
                    else:
                        st.error(msg)
                    st.rerun()
                elif sell_btn:
                    ok, msg = execute_sell(_user_id, trade_symbol, trade_qty)
                    if ok:
                        st.success(msg)
                    else:
                        st.error(msg)
                    st.rerun()

        with col_watchlist:
            wl_header, wl_refresh = st.columns([3, 1])
            wl_header.markdown("**Live Watchlist**")
            if wl_refresh.button("↻", key="refresh_paper_watchlist", help="Refresh prices"):
                st.cache_data.clear()

            watchlist_input = st.text_input(
                "Symbols",
                value=", ".join(DEFAULT_WATCHLIST),
                key="paper_watchlist_symbols",
                label_visibility="collapsed",
            )
            symbols = [s.strip().upper() for s in watchlist_input.split(",") if s.strip()]

            quotes_df = get_watchlist_quotes(symbols)
            if not quotes_df.empty:
                st.dataframe(quotes_df, use_container_width=True, hide_index=True, height=360)
            else:
                st.info("No quotes available.")

        # Positions + Trade History side by side
        col_pos, col_hist = st.columns(2)

        with col_pos:
            st.markdown("**Open Positions**")
            if summary["positions"]:
                pos_df = pd.DataFrame(summary["positions"])
                pos_df = pos_df[["symbol", "quantity", "avg_entry_price", "current_price", "unrealized_pnl", "market_value"]]
                pos_df.columns = ["Symbol", "Qty", "Entry", "Price", "P&L", "Value"]
                st.dataframe(pos_df, use_container_width=True, hide_index=True)
            else:
                st.caption("No open positions.")

        with col_hist:
            st.markdown("**Trade History**")
            trades = get_trade_history(_user_id)
            if trades:
                trades_df = pd.DataFrame(trades)
                st.dataframe(trades_df, use_container_width=True, hide_index=True, height=300)
            else:
                st.caption("No trades yet.")

# ═══════════════════════════════════════════════════════════════════════════
# TAB: BROKER SETTINGS
# ═══════════════════════════════════════════════════════════════════════════

if selected_page == "Broker Settings":
    if _has_auth:
        render_broker_settings()
    else:
        st.info("Broker settings require database connection. Install asyncpg and configure Postgres.")

# ═══════════════════════════════════════════════════════════════════════════
# TAB: ADMIN (admin users only)
# ═══════════════════════════════════════════════════════════════════════════

if selected_page == "Admin":
    if _has_auth:
        render_admin_dashboard()
    else:
        st.info("Admin panel requires database connection.")

# ═══════════════════════════════════════════════════════════════════════════
# FOOTER
# ═══════════════════════════════════════════════════════════════════════════

st.markdown(f"""
<div style="text-align: center; color: #3f3f46; font-size: 0.7rem; padding: 1rem 0 0.5rem; border-top: 1px solid #18181b; margin-top: 1rem;">
    ATE v1.0 &nbsp;&middot;&nbsp; {_trading_mode_str if use_webull else "Demo"} &nbsp;&middot;&nbsp;
    {"Webull" if use_webull else "Synthetic Data"} &nbsp;&middot;&nbsp; {len(data['models'])} models
</div>
""", unsafe_allow_html=True)
