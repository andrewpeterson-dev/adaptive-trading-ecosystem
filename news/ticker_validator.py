"""
Ticker symbol validation against known US exchange listings.
Uses a hardcoded set of major tickers with an optional API fallback.
"""

import re
import time

import httpx
import structlog

logger = structlog.get_logger(__name__)

# Top ~500 US-listed tickers (NYSE + NASDAQ) covering S&P 500, major ETFs, and
# frequently traded names. This avoids hallucinated tickers entering sentiment scoring.
_KNOWN_TICKERS: set[str] = {
    # Major indices / ETFs
    "SPY", "QQQ", "IWM", "DIA", "VOO", "VTI", "VEA", "VWO", "EFA", "EEM",
    "XLF", "XLE", "XLK", "XLV", "XLI", "XLP", "XLU", "XLY", "XLB", "XLRE",
    "GLD", "SLV", "TLT", "HYG", "LQD", "IEF", "SHY", "BND", "ARKK", "ARKW",
    "TQQQ", "SQQQ", "SPXU", "UVXY", "VXX", "SOXL", "SOXS", "KWEB",
    # Mega-cap tech
    "AAPL", "MSFT", "AMZN", "GOOGL", "GOOG", "META", "NVDA", "TSLA", "TSM",
    "AVGO", "ORCL", "ADBE", "CRM", "CSCO", "INTC", "AMD", "QCOM", "TXN",
    "IBM", "AMAT", "LRCX", "KLAC", "MRVL", "MU", "SNPS", "CDNS", "ADI",
    "NXPI", "MCHP", "ON", "SWKS", "FTNT", "PANW", "CRWD", "ZS", "NET",
    "DDOG", "SNOW", "PLTR", "SHOP", "SQ", "COIN", "HOOD", "UBER", "LYFT",
    "DASH", "ABNB", "BKNG", "EXPE", "MAR", "HLT",
    # Software / internet
    "NFLX", "DIS", "CMCSA", "T", "VZ", "TMUS", "CHTR", "EA", "ATVI", "RBLX",
    "SPOT", "PINS", "SNAP", "TTD", "ZM", "DOCU", "WDAY", "NOW", "TEAM",
    "HUBS", "VEEV", "BILL", "PAYC", "PCTY", "INTU", "ADSK", "ANSS", "PTC",
    # Finance
    "JPM", "BAC", "WFC", "GS", "MS", "C", "USB", "PNC", "TFC", "SCHW",
    "BLK", "SPGI", "ICE", "CME", "NDAQ", "MCO", "MSCI", "FIS", "FISV",
    "AXP", "V", "MA", "PYPL", "COF", "DFS", "SYF", "AIG", "MET", "PRU",
    "AFL", "ALL", "TRV", "CB", "PGR", "HIG", "BRK.A", "BRK.B", "BRK-B",
    # Healthcare
    "JNJ", "UNH", "PFE", "ABBV", "MRK", "LLY", "TMO", "ABT", "DHR", "BMY",
    "AMGN", "GILD", "VRTX", "REGN", "ISRG", "SYK", "BSX", "MDT", "ZBH",
    "EW", "DXCM", "ILMN", "MRNA", "BNTX", "BIIB", "HCA", "CI", "ELV",
    "CVS", "MCK", "CAH", "ABC", "HOLX", "IDXX", "IQV",
    # Consumer
    "WMT", "COST", "TGT", "HD", "LOW", "SBUX", "MCD", "YUM", "CMG", "DPZ",
    "NKE", "LULU", "TJX", "ROST", "DG", "DLTR", "KR", "SYY", "KO", "PEP",
    "MNST", "STZ", "SAM", "PM", "MO", "EL", "CL", "PG", "KMB", "CHD",
    # Industrials
    "CAT", "DE", "HON", "MMM", "GE", "RTX", "LMT", "NOC", "BA", "GD",
    "UPS", "FDX", "UNP", "CSX", "NSC", "DAL", "UAL", "LUV", "AAL",
    "WM", "RSG", "EMR", "ROK", "ETN", "ITW", "PH", "DOV", "SWK", "IR",
    # Energy
    "XOM", "CVX", "COP", "SLB", "EOG", "MPC", "PSX", "VLO", "OXY", "DVN",
    "PXD", "FANG", "HAL", "BKR", "KMI", "WMB", "OKE", "ET", "EPD", "LNG",
    # Materials
    "LIN", "APD", "ECL", "SHW", "DD", "DOW", "NEM", "FCX", "NUE", "STLD",
    "CF", "MOS", "ALB", "VMC", "MLM", "BALL", "PKG", "IP",
    # Real estate
    "AMT", "PLD", "CCI", "EQIX", "PSA", "SPG", "O", "WELL", "DLR", "AVB",
    "EQR", "VTR", "ARE", "MAA", "UDR", "ESS", "INVH", "CPT",
    # Utilities
    "NEE", "DUK", "SO", "D", "AEP", "SRE", "EXC", "XEL", "WEC", "ES",
    "ED", "AWK", "ATO", "CMS", "CNP", "DTE", "EVRG", "FE", "NI", "PNW",
    # Other notable
    "RIVN", "LCID", "NIO", "XPEV", "LI", "F", "GM", "STLA", "TM", "HMC",
    "SOFI", "AFRM", "UPST", "NU", "MELI", "SE", "GRAB", "CPNG", "JD",
    "BABA", "PDD", "BIDU", "BILI", "TME", "WBD", "PARA", "ROKU", "FUBO",
    "AI", "PATH", "U", "RKLB", "LUNR", "RDW", "SPCE", "JOBY",
    "ARM", "SMCI", "VRT", "CEG", "VST", "OKLO", "SMR", "IONQ",
}


class TickerValidator:
    """Validate that ticker symbols actually exist on exchanges."""

    def __init__(self):
        self._cache: dict[str, bool] = {t: True for t in _KNOWN_TICKERS}
        self._negative_cache: dict[str, float] = {}  # ticker -> timestamp of last check
        self._negative_ttl = 3600  # re-check unknown tickers after 1 hour

    def is_valid(self, ticker: str) -> bool:
        """Check if a ticker symbol is valid."""
        ticker = ticker.upper().strip()
        if not ticker or not re.match(r"^[A-Z]{1,5}(?:[.-][A-Z])?$", ticker):
            return False

        if ticker in self._cache:
            return self._cache[ticker]

        # Check negative cache TTL
        if ticker in self._negative_cache:
            if time.time() - self._negative_cache[ticker] < self._negative_ttl:
                return False

        # API fallback: try a quick Yahoo Finance quote check
        valid = self._api_check(ticker)
        if valid:
            self._cache[ticker] = True
        else:
            self._negative_cache[ticker] = time.time()
        return valid

    def validate_batch(self, tickers: list[str]) -> dict[str, bool]:
        """Validate multiple tickers. Returns {ticker: is_valid}."""
        return {t: self.is_valid(t) for t in tickers}

    def _api_check(self, ticker: str) -> bool:
        """Fallback validation via Yahoo Finance quote endpoint."""
        try:
            url = f"https://query2.finance.yahoo.com/v6/finance/quote?symbols={ticker}"
            headers = {"User-Agent": "Mozilla/5.0"}
            resp = httpx.get(url, headers=headers, timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                results = data.get("quoteResponse", {}).get("result", [])
                return len(results) > 0 and results[0].get("symbol") == ticker
        except Exception as e:
            logger.debug("ticker_api_check_failed", ticker=ticker, error=str(e))
        return False
