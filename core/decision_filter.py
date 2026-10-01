class DecisionFilter:

    def evaluate(self, decision, regime):

        action = decision.get(
            "action",
            "HOLD"
        )

        market = regime.get(
            "regime",
            "SIDEWAY"
        )


        final_action = "WAIT"


        if action == "BUY":

            if market in [
                "UPTREND",
                "BUY_PRESSURE"
            ]:
                final_action = "BUY"


        elif action == "SELL":

            if market in [
                "DOWNTREND",
                "SELL_PRESSURE"
            ]:
                final_action = "SELL"


        return {
            "action": final_action,
            "regime": market
        }
