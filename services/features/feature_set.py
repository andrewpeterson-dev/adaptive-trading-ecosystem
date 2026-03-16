"""
Unified feature container for all feature types.

Provides serialization to dict, flattening to numeric vector for ML,
and a quality score indicating data completeness.
"""
from __future__ import annotations

import math
import time
from dataclasses import dataclass, field


@dataclass
class FeatureSet:
    """Container for all computed features for a single symbol at a point in time."""

    symbol: str
    timestamp: float = field(default_factory=time.time)
    technical: dict = field(default_factory=dict)
    sentiment: dict = field(default_factory=dict)
    fundamental: dict = field(default_factory=dict)

    def to_vector(self) -> list[float]:
        """
        Flatten all features to a numeric vector for ML models.

        Non-numeric and None values are replaced with 0.0 (NaN-safe).
        The order is deterministic: technical keys sorted, then sentiment
        sorted, then fundamental sorted.
        """
        values: list[float] = []
        for d in (self.technical, self.sentiment, self.fundamental):
            for key in sorted(d.keys()):
                val = d[key]
                if val is None:
                    values.append(0.0)
                elif isinstance(val, (int, float)):
                    f = float(val)
                    values.append(0.0 if (math.isnan(f) or math.isinf(f)) else f)
                else:
                    values.append(0.0)
        return values

    def to_dict(self) -> dict:
        """Full dict representation with all feature groups."""
        return {
            "symbol": self.symbol,
            "timestamp": self.timestamp,
            "technical": dict(self.technical),
            "sentiment": dict(self.sentiment),
            "fundamental": dict(self.fundamental),
            "quality_score": self.quality_score,
        }

    @property
    def quality_score(self) -> float:
        """
        0-1 score of how complete this feature set is.

        Computed as the percentage of non-null numeric features across
        all feature groups.
        """
        total = 0
        non_null = 0
        for d in (self.technical, self.sentiment, self.fundamental):
            for val in d.values():
                total += 1
                if val is not None:
                    if isinstance(val, (int, float)):
                        f = float(val)
                        if not (math.isnan(f) or math.isinf(f)):
                            non_null += 1
                    else:
                        # Non-numeric but present (e.g. a string placeholder)
                        non_null += 1

        if total == 0:
            return 0.0
        return non_null / total

    @property
    def feature_names(self) -> list[str]:
        """Return ordered list of feature names matching to_vector() order."""
        names: list[str] = []
        for prefix, d in [("tech", self.technical), ("sent", self.sentiment), ("fund", self.fundamental)]:
            for key in sorted(d.keys()):
                names.append(f"{prefix}:{key}")
        return names
