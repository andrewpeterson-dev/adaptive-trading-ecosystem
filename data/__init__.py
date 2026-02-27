def __getattr__(name):
    if name == "DataIngestor":
        from data.ingestion import DataIngestor
        return DataIngestor
    if name == "FeatureEngineer":
        from data.features import FeatureEngineer
        return FeatureEngineer
    if name == "MarketStreamListener":
        from data.stream import MarketStreamListener
        return MarketStreamListener
    if name == "WebullClient":
        from data.webull_client import WebullClient
        return WebullClient
    if name == "WebullPaperClient":
        from data.webull_client import WebullPaperClient
        return WebullPaperClient
    if name == "WebullLiveClient":
        from data.webull_client import WebullLiveClient
        return WebullLiveClient
    if name == "TradingMode":
        from data.webull_client import TradingMode
        return TradingMode
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "DataIngestor", "FeatureEngineer", "MarketStreamListener",
    "WebullClient", "WebullPaperClient", "WebullLiveClient", "TradingMode",
]
