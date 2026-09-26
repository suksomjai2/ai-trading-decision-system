class DecisionEngine:
    """
    Decision Engine Framework

    Input:
        - Market Features
        - Market Regime

    Output:
        - Trading Decision
    """

    def __init__(self):
        pass


    def decide(self, regime, features):
        """
        Generate trading decision
        """

        decision = {
            "action": "NO_TRADE",
            "confidence": 0.0,
            "reason": []
        }


        # =========================
        # Trend Up
        # =========================

        if regime == "TREND_UP":

            decision["action"] = "BUY"

            decision["confidence"] = 0.75

            decision["reason"].append(
                "Market trend is bullish"
            )


        # =========================
        # Trend Down
        # =========================

        elif regime == "TREND_DOWN":

            decision["action"] = "SELL"

            decision["confidence"] = 0.75

            decision["reason"].append(
                "Market trend is bearish"
            )


        # =========================
        # Range Market
        # =========================

        elif regime == "RANGE":

            decision["action"] = "WAIT"

            decision["confidence"] = 0.40

            decision["reason"].append(
                "Sideway market detected"
            )


        # =========================
        # High Volatility
        # =========================

        elif regime == "HIGH_VOLATILITY":

            decision["action"] = "NO_TRADE"

            decision["confidence"] = 0.90

            decision["reason"].append(
                "Risk protection mode"
            )


        # =========================
        # Transition
        # =========================

        elif regime == "TRANSITION":

            decision["action"] = "WAIT"

            decision["confidence"] = 0.50

            decision["reason"].append(
                "Market transition detected"
            )


        return decision
