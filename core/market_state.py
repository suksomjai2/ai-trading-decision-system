class MarketState:

    def __init__(self):
        pass


    def analyze(self, market_data):

        open_price = market_data["open"]
        close = market_data["close"]
        high = market_data["high"]
        low = market_data["low"]


        # Trend Direction

        if close > open_price:
            state = "BULLISH"

        elif close < open_price:
            state = "BEARISH"

        else:
            state = "NEUTRAL"


        # Momentum

        price_range = high - low


        # Volume (ถ้ามี)
        volume_state = "UNKNOWN"

        if "volume" in market_data:
            volume = market_data["volume"]

            if volume > 100000:
                volume_state = "HIGH"
            else:
                volume_state = "LOW"


        return {

            "state": state,

            "market_state": state,

            "price_range": price_range,

            "trend_direction":
                "UP" if close > open_price else "DOWN",

            "volume_state": volume_state
        }
