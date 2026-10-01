class EntryDecision:

    def evaluate(self, setup, confidence):

        setup_type = setup.get(
            "setup",
            "NO_SETUP"
        )

        quality = confidence.get(
            "quality",
            "LOW"
        )


        action = "WAIT"


        if quality == "HIGH":

            if setup_type == "BUY_SETUP":
                action = "BUY"

            elif setup_type == "SELL_SETUP":
                action = "SELL"


        return {
            "action": action,
            "setup": setup_type,
            "quality": quality
        }
