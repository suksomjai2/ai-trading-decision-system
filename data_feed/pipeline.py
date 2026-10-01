from data_feed.market_data import MarketData
from data_feed.validator import CandleValidator


class MarketDataPipeline:

    def __init__(self, symbol="XAUUSD"):
        self.market_data = MarketData(symbol)
        self.validator = CandleValidator()

    def process(
        self,
        timestamp,
        open_price,
        high,
        low,
        close,
        volume=0
    ):
        # 1. Normalize incoming market data
        candle = self.market_data.normalize_candle(
            timestamp=timestamp,
            open_price=open_price,
            high=high,
            low=low,
            close=close,
            volume=volume
        )

        # 2. Validate candle
        validation = self.validator.validate(candle)

        # 3. Reject invalid data
        if not validation["valid"]:
            return {
                "accepted": False,
                "reason": validation["reason"],
                "candle": None
            }

        # 4. Accepted market data
        return {
            "accepted": True,
            "reason": "OK",
            "candle": candle
        }
