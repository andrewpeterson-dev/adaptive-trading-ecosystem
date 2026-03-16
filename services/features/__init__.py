"""
Feature engineering pipeline for the adaptive trading ecosystem.

Transforms raw market data into structured features for quant models
and the AI reasoning engine.
"""

from services.features.pipeline import FeaturePipeline
from services.features.feature_set import FeatureSet

__all__ = ["FeaturePipeline", "FeatureSet"]
