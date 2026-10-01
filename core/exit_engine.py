class ExitEngine:

    def evaluate(self, price, target):

        target_price = target.get(
            "target_price",
            price
        )

        invalid_price = target.get(
            "invalid_price",
            price
        )

        action = target.get(
            "action",
            "WAIT"
        )


        status = "HOLD"


        if action == "BUY":

            if price >= target_price:
                status = "TAKE_PROFIT"

            elif price <= invalid_price:
                status = "EXIT"


        elif action == "SELL":

            if price <= target_price:
                status = "TAKE_PROFIT"

            elif price >= invalid_price:
                status = "EXIT"


        return {
            "status": status,
            "action": action,
            "current_price": price
        }
