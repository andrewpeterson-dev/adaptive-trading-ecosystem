"""
Load, validate, and manage strategy configurations.
Strategy configs define which models to run, risk parameters, and execution settings.
"""

import json
from pathlib import Path
from typing import Optional

import structlog

from models.base import ModelBase
from models.registry import create_default_models

logger = structlog.get_logger(__name__)

DEFAULT_CONFIG_PATH = Path(__file__).parent / "strategy_config.json"

# Maps strategy instance names to their class + constructor kwargs.
# This bridges the gap between config names and the model registry.
STRATEGY_CATALOG: dict[str, dict] = {
    "momentum_fast": {"class": "MomentumModel", "kwargs": {"fast_window": 5, "slow_window": 20}},
    "momentum_slow": {"class": "MomentumModel", "kwargs": {"fast_window": 20, "slow_window": 100}},
    "mean_reversion_tight": {"class": "MeanReversionModel", "kwargs": {"lookback": 15, "entry_z": 1.5}},
    "mean_reversion_wide": {"class": "MeanReversionModel", "kwargs": {"lookback": 30, "entry_z": 2.2}},
    "vol_squeeze": {"class": "VolatilityModel", "kwargs": {}},
    "volatility_squeeze": {"class": "VolatilityModel", "kwargs": {}},
    "breakout_sr": {"class": "BreakoutModel", "kwargs": {}},
    "iv_crush": {"class": "IVCrushModel", "kwargs": {}},
    "earnings_momentum": {"class": "EarningsMomentumModel", "kwargs": {}},
    "pairs_statarb": {"class": "PairsModel", "kwargs": {}},
    "ml_xgboost": {"class": "MLModel", "kwargs": {"estimator_type": "xgboost"}},
    "ml_random_forest": {"class": "MLModel", "kwargs": {"estimator_type": "random_forest"}},
}

VALID_POSITION_SIZING = {"equal_weight", "risk_parity", "inverse_vol", "kelly"}
VALID_ORDER_TYPES = {"market", "limit", "stop", "stop_limit"}
VALID_TIF = {"DAY", "GTC", "IOC", "FOK"}


class StrategyLoader:
    """Load, validate, and manage strategy configurations."""

    def __init__(self):
        self._config: Optional[dict] = None

    def load_config(self, path: str = None) -> dict:
        """Load strategy config from JSON file."""
        config_path = Path(path) if path else DEFAULT_CONFIG_PATH
        if not config_path.exists():
            raise FileNotFoundError(f"Strategy config not found: {config_path}")

        with open(config_path) as f:
            self._config = json.load(f)

        logger.info("strategy_config_loaded", path=str(config_path), name=self._config.get("name"))
        return self._config

    def save_config(self, config: dict, path: str = None) -> str:
        """Save strategy config to JSON file."""
        config_path = Path(path) if path else DEFAULT_CONFIG_PATH
        config_path.parent.mkdir(parents=True, exist_ok=True)

        with open(config_path, "w") as f:
            json.dump(config, f, indent=2)

        self._config = config
        logger.info("strategy_config_saved", path=str(config_path))
        return str(config_path)

    def validate_config(self, config: dict) -> tuple[bool, list[str]]:
        """
        Validate strategy config. Returns (valid, errors).
        Checks required fields, strategy names against catalog, and risk param bounds.
        """
        errors = []

        # Required top-level fields
        for field in ("name", "version", "active_strategies", "risk_params"):
            if field not in config:
                errors.append(f"Missing required field: {field}")

        if errors:
            return False, errors

        # Validate active strategies exist in catalog
        active = config.get("active_strategies", [])
        if not active:
            errors.append("active_strategies must not be empty")

        for name in active:
            if name not in STRATEGY_CATALOG:
                errors.append(f"Unknown strategy '{name}'. Available: {list(STRATEGY_CATALOG.keys())}")

        # Validate risk params
        risk = config.get("risk_params", {})
        if "max_allocation_pct" in risk:
            v = risk["max_allocation_pct"]
            if not (0 < v <= 1.0):
                errors.append(f"max_allocation_pct must be in (0, 1.0], got {v}")

        if "stop_loss_pct" in risk:
            v = risk["stop_loss_pct"]
            if not (0 < v <= 0.5):
                errors.append(f"stop_loss_pct must be in (0, 0.5], got {v}")

        if "max_daily_drawdown_pct" in risk:
            v = risk["max_daily_drawdown_pct"]
            if not (0 < v <= 1.0):
                errors.append(f"max_daily_drawdown_pct must be in (0, 1.0], got {v}")

        if "position_sizing" in risk:
            v = risk["position_sizing"]
            if v not in VALID_POSITION_SIZING:
                errors.append(f"Invalid position_sizing '{v}'. Must be one of {VALID_POSITION_SIZING}")

        if "max_positions" in risk:
            v = risk["max_positions"]
            if not (1 <= v <= 500):
                errors.append(f"max_positions must be in [1, 500], got {v}")

        # Validate execution params
        execution = config.get("execution", {})
        if "order_type" in execution and execution["order_type"] not in VALID_ORDER_TYPES:
            errors.append(f"Invalid order_type '{execution['order_type']}'")

        if "time_in_force" in execution and execution["time_in_force"] not in VALID_TIF:
            errors.append(f"Invalid time_in_force '{execution['time_in_force']}'")

        if "slippage_bps" in execution:
            v = execution["slippage_bps"]
            if not (0 <= v <= 100):
                errors.append(f"slippage_bps must be in [0, 100], got {v}")

        # Validate backtest params
        backtest = config.get("backtest", {})
        if "initial_capital" in backtest:
            v = backtest["initial_capital"]
            if v is not None and v <= 0:
                errors.append(f"initial_capital must be positive, got {v}")

        return len(errors) == 0, errors

    def get_active_models(self, config: dict = None) -> list[ModelBase]:
        """
        Return instantiated model objects for active strategies in the config.
        Falls back to the default models from the registry for known names.
        """
        cfg = config or self._config
        if cfg is None:
            cfg = self.load_config()

        active_names = set(cfg.get("active_strategies", []))
        if not active_names:
            logger.warning("no_active_strategies")
            return []

        # Build from create_default_models, filtering to active set
        all_defaults = create_default_models()
        models = [m for m in all_defaults if m.name in active_names]

        # Check for strategies referenced in config but not in defaults
        found_names = {m.name for m in models}
        missing = active_names - found_names

        # Try to instantiate missing ones from catalog
        if missing:
            from models.registry import get_model_class
            for name in missing:
                entry = STRATEGY_CATALOG.get(name)
                if entry:
                    try:
                        cls = get_model_class(entry["class"])
                        model = cls(name=name, **entry["kwargs"])
                        models.append(model)
                    except (KeyError, TypeError) as e:
                        logger.warning("strategy_instantiation_failed", name=name, error=str(e))

        logger.info("active_models_loaded", count=len(models), names=[m.name for m in models])
        return models

    @property
    def config(self) -> Optional[dict]:
        return self._config
