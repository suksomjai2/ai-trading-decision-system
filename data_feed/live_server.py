import json
from http.server import BaseHTTPRequestHandler, HTTPServer

from data_feed.mt5_bridge import MT5Bridge
from data_feed.pipeline import MarketDataPipeline
from core.feature_engine import FeatureEngine
from core.market_state import MarketState


bridge = MT5Bridge()
feature_engine = FeatureEngine()
market_state = MarketState()


def analyze(payload):

    # 1. Parse MT5 payload
    parsed = bridge.parse(payload)

    if not parsed["accepted"]:
        return {
            "status": "REJECTED",
            "reason": parsed["reason"],
            "decision": None
        }

    mt5 = parsed["data"]

    # 2. Normalize + validate
    pipeline = MarketDataPipeline(mt5["symbol"])

    market = pipeline.process(
        timestamp=mt5["timestamp"],
        open_price=mt5["open"],
        high=mt5["high"],
        low=mt5["low"],
        close=mt5["close"],
        volume=mt5["volume"]
    )

    if not market["accepted"]:
        return {
            "status": "REJECTED",
            "reason": market["reason"],
            "decision": None
        }

    # 3. Features
    candle = market["candle"]
    features = feature_engine.calculate_features(candle)

    # 4. AI decision
    decision = market_state.trading_decision(
        candle["close"],
        features
    )

    return {
        "status": "PROCESSED",
        "symbol": mt5["symbol"],
        "timeframe": mt5["timeframe"],
        "timestamp": mt5["timestamp"],
        "decision": decision
    }


class Handler(BaseHTTPRequestHandler):

    def do_GET(self):

        if self.path == "/health":
            response = {
                "status": "OK",
                "mode": "READ_ONLY"
            }
            self.send_json(200, response)
            return

        self.send_json(404, {"error": "NOT_FOUND"})

    def do_POST(self):

        if self.path != "/market":
            self.send_json(404, {"error": "NOT_FOUND"})
            return

        try:
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)
            payload = json.loads(body)

            result = analyze(payload)

            self.send_json(200, result)

        except Exception as exc:
            self.send_json(
                400,
                {
                    "status": "ERROR",
                    "reason": str(exc)
                }
            )

    def send_json(self, status_code, data):

        body = json.dumps(data).encode("utf-8")

        self.send_response(status_code)
        self.send_header(
            "Content-Type",
            "application/json"
        )
        self.send_header(
            "Content-Length",
            str(len(body))
        )
        self.end_headers()

        self.wfile.write(body)


def run(host="0.0.0.0", port=8000):

    server = HTTPServer(
        (host, port),
        Handler
    )

    print(
        f"AI Trading Server running "
        f"http://{host}:{port}"
    )

    print("MODE: READ_ONLY")

    server.serve_forever()


if __name__ == "__main__":
    run()
