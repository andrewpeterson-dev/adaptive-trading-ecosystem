from intelligence.regime import RegimeDetector
from intelligence.meta import MetaLearner

# Lazy imports for modules with heavy/optional dependencies
def __getattr__(name):
    if name == "ModelRetrainer":
        from intelligence.retrainer import ModelRetrainer
        return ModelRetrainer
    if name == "LLMAnalyst":
        from intelligence.llm_analyst import LLMAnalyst
        return LLMAnalyst
    raise AttributeError(f"module 'intelligence' has no attribute {name}")

__all__ = ["RegimeDetector", "ModelRetrainer", "MetaLearner", "LLMAnalyst"]
