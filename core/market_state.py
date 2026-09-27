class MarketState:

    def __init__(self):
        pass


    def analyze(self, market_data):

        close = market_data["close"]
        open_price = market_data["open"]

        if close > open_price:
            state = "BULLISH"

        elif close < open_price:
            state = "BEARISH"

        else:
            state = "NEUTRAL"


        return {
            "state": state
        }
