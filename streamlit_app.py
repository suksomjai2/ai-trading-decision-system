import json
from datetime import datetime, timezone, timedelta
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

import streamlit as st


st.set_page_config(
    page_title="AI Trading Decision System",
    layout="wide",
)

st.title("AI Trading Decision System")
st.subheader("XAUUSD · M15")
st.caption(
    "READ_ONLY | Market data: MT5 | Analysis: Python on VPS"
)


def fetch_latest():
    url = str(st.secrets["SUPABASE_URL"]).rstrip("/")
    key = str(st.secrets["SUPABASE_SECRET_KEY"]).strip()

    endpoint = (
        url + "/rest/v1/market_latest"
        "?symbol=eq.XAUUSD&timeframe=eq.M15&select=*"
    )
    request = Request(
        endpoint,
        headers={
            "apikey": key,
            "User-Agent": "AITrading-Streamlit/1.0",
            "Accept": "application/json",
        },
    )

    with urlopen(request, timeout=10) as response:
        rows = json.load(response)

    if not isinstance(rows, list) or len(rows) != 1:
        raise ValueError("Expected one XAUUSD M15 snapshot")

    row = rows[0]
    snapshot = row["snapshot"]

    if (
        row["symbol"] != "XAUUSD"
        or row["timeframe"] != "M15"
        or snapshot["market"]["symbol"] != "XAUUSD"
        or snapshot["market"]["timeframe"] != "M15"
        or snapshot["analysis"]["status"] != "PROCESSED"
        or snapshot["mode"] != "READ_ONLY"
    ):
        raise ValueError("Invalid snapshot")

    return row


def price(value):
    if isinstance(value, (int, float)):
        return f"{value:,.2f}"
    return "N/A"


@st.fragment(run_every=15)
def dashboard():
    st.button("Refresh now")

    try:
        row = fetch_latest()
        snapshot = row["snapshot"]
        market = snapshot["market"]
        analysis = snapshot["analysis"]
        decision = analysis.get("decision") or {}
        entry = decision.get("entry") or {}
        target = decision.get("target") or {}

        received = datetime.fromisoformat(
            row["received_at_utc"].replace("Z", "+00:00")
        )
        if received.tzinfo is None:
            raise ValueError("Missing receive-time timezone")

        age = (
            datetime.now(timezone.utc) - received
        ).total_seconds()

    except HTTPError as error:
        st.error(f"Database connection failed: HTTP {error.code}")
        return
    except (URLError, TimeoutError, OSError):
        st.error("Cannot reach database. Please refresh later.")
        return
    except KeyError:
        st.error("Missing app Secrets or required snapshot fields.")
        return
    except (ValueError, TypeError, AttributeError):
        st.error("Database response has an unexpected format.")
        return
    except Exception:
        st.error("Unable to load data. Check the app configuration.")
        return

    st.success("Connected to Supabase — saved MT5 data loaded")

    if age > 20 * 60:
        st.warning(
            "No newly received snapshot for over 20 minutes. "
            "The values below are the last saved data."
        )
    elif age < -60:
        st.warning("Receive time is ahead of the app clock.")

    bangkok = timezone(timedelta(hours=7))
    st.write(
        "**Last received (Thailand):**",
        received.astimezone(bangkok).strftime("%Y-%m-%d %H:%M:%S"),
    )
    st.write(
        "**Candle timestamp (broker time):**",
        market.get("timestamp", "N/A"),
    )
    st.caption(
        "Closed M15 candle data. Page checks for updates every "
        "15 seconds while open; these are not live tick prices."
    )

    col1, col2, col3 = st.columns(3)
    col1.metric("Candle close", price(market.get("close")))
    col2.metric("Decision", decision.get("decision", "N/A"))
    col3.metric("Setup quality", entry.get("quality", "N/A"))

    col4, col5 = st.columns(2)
    col4.metric("Target price", price(target.get("target_price")))
    col5.metric("Invalidation price", price(target.get("invalid_price")))

    st.divider()
    st.subheader("MT5 candle")
    st.json(market)

    st.subheader("Analysis from VPS")
    st.json(decision)


dashboard()
