# Adaptive Trading Ecosystem

A modular, scalable AI trading platform where multiple models train, compete, adapt, and allocate capital dynamically. Integrates backtesting, paper trading, and live trading in one unified system.

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                    ORCHESTRATOR                               │
│  data → regime → retrain → signals → risk → execute → learn │
└──────────┬───────────┬──────────┬────────────┬───────────────┘
           │           │          │            │
    ┌──────▼──┐  ┌─────▼────┐ ┌──▼───┐  ┌─────▼─────┐
    │  DATA   │  │  MODELS  │ │ RISK │  │ EXECUTION │
    │ Layer   │  │  Layer   │ │ Mgmt │  │  Engine   │
    └─────────┘  └──────────┘ └──────┘  └───────────┘
         │            │           │           │
    ┌────▼────┐  ┌────▼────┐ ┌───▼───┐  ┌───▼────┐
    │ Alpaca  │  │Ensemble │ │Capital│  │ Alpaca │
    │  Data   │  │  Meta   │ │Alloc  │  │ Trade  │
    └─────────┘  └─────────┘ └───────┘  └────────┘
```

## Models

| Model | Type | Strategy |
|-------|------|----------|
| `momentum_fast` | MomentumModel | Fast MA crossover (5/20) |
| `momentum_slow` | MomentumModel | Slow MA crossover (20/100) |
| `mean_reversion_tight` | MeanReversionModel | Z-score reversion (15-bar, 2σ) |
| `mean_reversion_wide` | MeanReversionModel | Z-score reversion (30-bar, 2.5σ) |
| `volatility_squeeze` | VolatilityModel | Bollinger squeeze breakout |
| `ml_xgboost` | MLModel | XGBoost return classification |
| `ml_random_forest` | MLModel | Random Forest return classification |
| `ensemble_meta` | EnsembleMetaModel | Performance-weighted signal aggregation |

## Quick Start

### 1. Environment Setup

```bash
cp .env.example .env
# Edit .env with your Alpaca API keys and database credentials
```

### 2. Docker (Recommended)

```bash
docker-compose up -d
```

This starts PostgreSQL, Redis, the API server, and the Streamlit dashboard.

- API: http://localhost:8000
- Dashboard: http://localhost:8501
- API Docs: http://localhost:8000/docs

### 3. Local Development

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Initialize database
python scripts/init_db.py

# Start API server
uvicorn api.main:app --reload

# Start dashboard (separate terminal)
streamlit run dashboard/app.py

# Run backtest
python scripts/run_backtest.py

# Run orchestrator
python orchestrator.py
```

### 4. Run Tests

```bash
pytest
```

## Project Structure

```
adaptive-trading-ecosystem/
├── config/             # Settings and env management
├── db/                 # Database models and connection
├── data/               # Data ingestion, streaming, features
├── models/             # Trading model implementations
│   ├── base.py         # Abstract ModelBase class
│   ├── momentum.py     # Trend-following
│   ├── mean_reversion.py
│   ├── volatility.py   # Squeeze breakout
│   ├── ml_model.py     # XGBoost / RandomForest
│   ├── ensemble.py     # Meta-model aggregator
│   └── registry.py     # Model discovery
├── engine/             # Backtesting and execution
├── risk/               # Risk management
├── allocation/         # Dynamic capital allocation
├── intelligence/       # Regime detection, retraining, meta-learning
├── api/                # FastAPI backend
├── dashboard/          # Streamlit frontend
├── scripts/            # CLI utilities
├── tests/              # Test suite
├── orchestrator.py     # Main trading loop
└── docker-compose.yml  # Full deployment
```

## Adding a New Model

1. Create a new file in `models/` that extends `ModelBase`
2. Implement `train()`, `predict()`, and `evaluate()`
3. Register it in `models/registry.py`
4. It will automatically be picked up by the ensemble and capital allocator

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/trading/execute` | Execute a trading signal |
| GET | `/api/trading/account` | Account info |
| GET | `/api/trading/positions` | Open positions |
| GET | `/api/trading/risk-summary` | Risk status |
| GET | `/api/models/list` | All models + metrics |
| POST | `/api/models/retrain` | Trigger retraining |
| POST | `/api/models/allocate` | Recompute allocation |
| GET | `/api/models/regime` | Current market regime |
| GET | `/api/models/ensemble-status` | Ensemble weights |

## Risk Controls

- Max position size: 10% of equity
- Max portfolio exposure: 80%
- Max drawdown shutdown: 15%
- Per-position stop loss: 3%
- Trade frequency limit: 20/hour
- All configurable via `.env`
