class DecisionEngine:

    def __init__(self):
        pass


    def decide(self, market_state, features):

        trend = features.get(
            "trend_direction",
            "NEUTRAL"
        )

        volume = features.get(
            "volume_state",
            "UNKNOWN"
        )


        if market_state == "BULLISH" and trend == "UP":

            return {
                "action": "BUY",
                "confidence": 0.8
            }


        elif market_state == "BEARISH" and trend == "DOWN":

            return {
                "action": "SELL",
                "confidence": 0.8
            }


        else:

            return {
                "action": "HOLD",
                "confidence": 0.5
            }
