class MarketData:

    def __init__(self, symbol="XAUUSD"):
        self.symbol = symbol

    def normalize_candle(
        self,
        timestamp,
        open_price,
        high,
        low,
        close,
        volume=0
    ):
        return {
            "symbol": self.symbol,
            "timestamp": timestamp,
            "open": float(open_price),
            "high": float(high),
            "low": float(low),
            "close": float(close),
            "volume": float(volume)
        }
