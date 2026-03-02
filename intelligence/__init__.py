from intelligence.regime import RegimeDetector
from intelligence.meta import MetaLearner
from intelligence.confidence_model import ConfidenceModel
from intelligence.ensemble_engine import EnsembleEngine
from intelligence.decision_pipeline import DecisionPipeline

# Lazy imports for modules with heavy/optional dependencies
def __getattr__(name):
    if name == "ModelRetrainer":
        from intelligence.retrainer import ModelRetrainer
        return ModelRetrainer
    if name == "LLMAnalyst":
        from intelligence.llm_analyst import LLMAnalyst
        return LLMAnalyst
    if name == "OllamaClient":
        from intelligence.ollama_client import OllamaClient
        return OllamaClient
    if name == "LLMRouter":
        from intelligence.llm_router import LLMRouter
        return LLMRouter
    raise AttributeError(f"module 'intelligence' has no attribute {name}")

__all__ = [
    "RegimeDetector",
    "ModelRetrainer",
    "MetaLearner",
    "LLMAnalyst",
    "OllamaClient",
    "LLMRouter",
    "ConfidenceModel",
    "EnsembleEngine",
    "DecisionPipeline",
]
