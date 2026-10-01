class TargetEngine:

    def evaluate(self, price, features, action):

        high = features.get(
            "high",
            price
        )

        low = features.get(
            "low",
            price
        )

        range_size = high - low


        if action == "BUY":

            target = price + range_size

            stop = low


        elif action == "SELL":

            target = price - range_size

            stop = high


        else:

            target = price

            stop = price


        return {
            "action": action,
            "target_price": round(
                target,
                4
            ),
            "invalid_price": round(
                stop,
                4
            )
        }
