class MarketState:


    def __init__(self):
        pass



    def analyze(self, market_data):

        # ======================
        # Input
        # ======================

        open_price = market_data["open"]
        close = market_data["close"]
        high = market_data["high"]
        low = market_data["low"]
        volume = market_data.get("volume", 0)



        # ======================
        # Trend Direction
        # ======================

        if close > open_price:

            state = "BULLISH"
            trend_direction = "UP"

        elif close < open_price:

            state = "BEARISH"
            trend_direction = "DOWN"

        else:

            state = "NEUTRAL"
            trend_direction = "SIDEWAY"



        # ======================
        # Momentum
        # ======================

        price_range = high - low



        # ======================
        # Volume Analysis
        # ======================

        if volume >= 1000000:

            volume_state = "HIGH"

        elif volume >= 500000:

            volume_state = "MEDIUM"

        else:

            volume_state = "LOW"



        # ======================
        # Output
        # ======================

        return {

            "state": state,

            "market_state": state,

            "price_range": price_range,

            "trend_direction": trend_direction,

            "volume_state": volume_state

        }
