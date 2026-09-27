class MarketState:


    def __init__(self):
        pass



    def analyze(self, market_data):

        open_price = market_data.get(
            "open",
            0
        )

        close = market_data.get(
            "close",
            0
        )


        if close > open_price:

            state = "BULLISH"


        elif close < open_price:

            state = "BEARISH"


        else:

            state = "NEUTRAL"



        return {
            "state": state
        }
