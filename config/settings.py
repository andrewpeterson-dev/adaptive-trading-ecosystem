"""
Centralized configuration via pydantic-settings.
All secrets and tunables come from environment variables or .env file.
"""

from enum import Enum
from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class TradingMode(str, Enum):
    BACKTEST = "backtest"
    PAPER = "paper"
    LIVE = "live"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # --- Database ---
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "trading_ecosystem"
    postgres_user: str = "trader"
    postgres_password: str = "changeme"

    @property
    def database_url(self) -> str:
        if self.use_sqlite:
            return "sqlite+aiosqlite:///trading_ecosystem.db"
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def database_url_sync(self) -> str:
        return (
            f"postgresql+psycopg2://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    # --- Redis ---
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_password: str = ""

    @property
    def redis_url(self) -> str:
        auth = f":{self.redis_password}@" if self.redis_password else ""
        return f"redis://{auth}{self.redis_host}:{self.redis_port}/0"

    # --- Alpaca ---
    alpaca_api_key: str = ""
    alpaca_secret_key: str = ""
    alpaca_base_url: str = "https://paper-api.alpaca.markets"
    alpaca_data_url: str = "https://data.alpaca.markets"

    # --- Alpaca Paper/Live Key Separation ---
    paper_api_key: str = ""
    paper_secret_key: str = ""
    live_api_key: str = ""
    live_secret_key: str = ""

    # --- Trading Mode ---
    trading_mode: TradingMode = TradingMode.PAPER
    live_trading_enabled: bool = False

    # --- Risk ---
    max_position_size_pct: float = 0.10
    max_portfolio_exposure_pct: float = 0.80
    max_drawdown_pct: float = 0.15
    stop_loss_pct: float = 0.03
    max_trades_per_hour: int = 20

    # --- Model Retraining ---
    retrain_interval_hours: int = 24
    walk_forward_window_days: int = 252
    performance_decay_threshold: float = 0.3

    # --- Capital ---
    initial_capital: float = 100_000.0
    min_model_weight: float = 0.05
    max_model_weight: float = 0.40

    # --- Logging ---
    log_level: str = "INFO"
    log_file: str = "logs/trading.log"
    audit_log_path: str = "logs/trade-log.jsonl"

    # --- Market Data Providers ---
    alphavantage_api_key: str = ""  # SET IN .env: ALPHAVANTAGE_API_KEY=...
    finnhub_api_key: str = ""       # SET IN .env: FINNHUB_API_KEY=...
    polygon_api_key: str = ""       # SET IN .env: POLYGON_API_KEY=...
    tradier_api_key: str = ""       # SET IN .env: TRADIER_API_KEY=...
    tradier_sandbox: bool = True    # SET IN .env: TRADIER_SANDBOX=false for live

    # --- LLM Intelligence ---
    anthropic_api_key: str = ""  # SET IN .env: ANTHROPIC_API_KEY=sk-ant-...
    openai_api_key: str = ""     # SET IN .env: OPENAI_API_KEY=sk-...
    llm_provider: str = "anthropic"  # "anthropic" or "openai"
    llm_model: str = "claude-sonnet-4-20250514"
    llm_analysis_interval_minutes: int = 15
    llm_max_retries: int = 2
    llm_temperature: float = 0.3

    # --- Ollama (Local LLM) ---
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.1:8b"
    ollama_enabled: bool = False
    ollama_timeout_seconds: int = 30

    # --- Monitoring ---
    webhook_url: str = ""  # Webhook URL for failure notifications
    llm_timeout_seconds: int = 30
    health_check_interval_seconds: int = 300

    # --- API ---
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    # --- Dashboard ---
    dashboard_port: int = 8501

    # --- Auth ---
    encryption_key: str = ""  # Fernet key for broker credential encryption
    jwt_secret: str = ""  # JWT signing key — MUST be set in .env
    jwt_expiry_days: int = 7
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""  # Gmail app password
    base_url: str = "http://localhost:3000"  # Frontend URL for email links
    use_sqlite: bool = True  # Use SQLite for local dev (no PostgreSQL needed)

    # --- CORS ---
    cors_origins: str = "http://localhost:3000,http://localhost:3001,http://localhost:3002"  # Comma-separated allowed origins

    # --- Autonomous Loop ---
    auto_loop_enabled: bool = False
    auto_loop_dry_run: bool = True
    auto_loop_max_tasks_per_run: int = 1

    # --- Lighthouse ---
    frontend_url: str = "http://localhost:3000"
    lighthouse_schedule_hours: int = 168  # weekly = 7*24

    @property
    def auth_database_url(self) -> str:
        """Database URL for the auth/dashboard sync engine."""
        if self.use_sqlite:
            return "sqlite:///trading_ecosystem.db"
        return self.database_url_sync


@lru_cache()
def get_settings() -> Settings:
    return Settings()
