from engine.backtester import BacktestEngine

# Lazy import — ExecutionEngine requires alpaca SDK
def __getattr__(name):
    if name == "ExecutionEngine":
        from engine.executor import ExecutionEngine
        return ExecutionEngine
    raise AttributeError(f"module 'engine' has no attribute {name}")

__all__ = ["ExecutionEngine", "BacktestEngine"]
