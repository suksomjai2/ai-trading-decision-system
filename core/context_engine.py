class ContextEngine:

    def __init__(self):
        pass


    def analyze(self, features, history):

        context = "NEUTRAL"


        trend = history.get(
            "trend",
            "UNKNOWN"
        )


        strength = features.get(
            "trend_strength",
            0
        )


        if trend == "BULLISH" and strength > 0.5:
            context = "STRONG_UPTREND"


        elif trend == "BEARISH" and strength > 0.5:
            context = "STRONG_DOWNTREND"


        elif trend == "BULLISH":
            context = "UPTREND"


        elif trend == "BEARISH":
            context = "DOWNTREND"


        return {
            "market_context": context,
            "historical_trend": trend,
            "trend_strength": strength
        }
