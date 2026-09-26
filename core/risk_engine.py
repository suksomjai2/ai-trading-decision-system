class RiskEngine:
    """
    Risk Management Engine

    Responsible for:
    - Risk evaluation
    - Confidence adjustment
    - Trade permission control
    """

    def __init__(self):
        pass


    def evaluate(self, decision, features):
        """
        Evaluate trading risk

        Input:
            decision:
                action from DecisionEngine

            features:
                market features

        Output:
            risk assessment
        """

        risk = {
            "risk_level": "LOW",
            "risk_score": 0.0,
            "allowed": True,
            "adjusted_confidence": decision.get(
                "confidence",
                0.0
            ),
            "reason": []
        }


        volatility = features.get(
            "volatility_state",
            "NORMAL"
        )

        atr = features.get(
            "atr",
            0
        )


        # =========================
        # High volatility protection
        # =========================

        if volatility == "HIGH":

            risk["risk_level"] = "HIGH"

            risk["risk_score"] += 0.5

            risk["adjusted_confidence"] *= 0.5

            risk["reason"].append(
                "High volatility detected"
            )


        # =========================
        # Large price movement
        # =========================

        if atr > 2:

            risk["risk_score"] += 0.3

            risk["adjusted_confidence"] *= 0.8

            risk["reason"].append(
                "Large price movement"
            )


        # =========================
        # No trade protection
        # =========================

        if decision.get("action") == "NO_TRADE":

            risk["allowed"] = False

            risk["reason"].append(
                "Decision engine blocked trade"
            )


        # =========================
        # Final risk control
        # =========================

        if risk["risk_score"] >= 0.7:

            risk["risk_level"] = "HIGH"

            risk["allowed"] = False

            risk["reason"].append(
                "Risk threshold exceeded"
            )


        return risk
