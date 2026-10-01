class HistoricalEngine:

    def __init__(self):
        pass


    def analyze(self, history):

        if not history:
            return {
                "trend": "UNKNOWN",
                "count": 0
            }


        buy = 0
        sell = 0


        for item in history:

            action = item.get(
                "decision",
                {}
            ).get(
                "action"
            )

            if action == "BUY":
                buy += 1

            elif action == "SELL":
                sell += 1


        trend = "NEUTRAL"

        if buy > sell:
            trend = "BULLISH"

        elif sell > buy:
            trend = "BEARISH"


        return {
            "trend": trend,
            "buy_count": buy,
            "sell_count": sell,
            "count": len(history)
        }
