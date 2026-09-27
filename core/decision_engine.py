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


        # Bullish condition

        if (
            market_state == "BULLISH"
            and trend == "UP"
            and volume == "HIGH"
        ):

            return {

                "action": "BUY",

                "confidence": 0.8

            }



        # Bearish condition

        elif (
            market_state == "BEARISH"
            and trend == "DOWN"
        ):

            return {

                "action": "SELL",

                "confidence": 0.8

            }



        # Neutral

        else:

            return {

                "action": "HOLD",

                "confidence": 0.5

            }
