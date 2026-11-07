import json
from datetime import datetime, timezone, timedelta
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

import streamlit as st


st.set_page_config(
    page_title="AI Trading Decision System",
    layout="wide",
)

# Original photograph, responsive layout; no generated portrait or image edits.
from pathlib import Path
import base64

# Both photographs are kept byte-for-byte and must stay on the dashboard in every release
# (guarded by tests/test_dashboard_photos.py).
PHOTO_FILES = ('dashboard_photo.jpeg', 'dashboard_photo_2.jpeg')


def load_photo(name):
    path = Path(__file__).resolve().parent / 'assets' / name
    return base64.b64encode(path.read_bytes()).decode('ascii') if path.exists() else ''


photos = [load_photo(name) for name in PHOTO_FILES]
st.markdown('<style>\n.v3-hero{display:flex;align-items:center;justify-content:space-between;gap:24px;padding:22px 26px;margin-bottom:22px;border:1px solid #dce5f2;border-radius:22px;background:linear-gradient(120deg,#eef5ff 0%,#fff 78%);color:#14253d}\n.v3-hero h1{font-size:clamp(22px,3.1vw,38px);line-height:1.15;margin:10px 0!important;padding:0!important;color:#14253d}\n.v3-hero p{margin:8px 0;color:#4b607a;font-size:14px}.v3-label{display:inline-block;background:#173c6b;color:white;border-radius:30px;padding:5px 12px;font-size:12px;letter-spacing:.08em}\n.v3-photos{display:flex;gap:14px;align-items:flex-end;flex-shrink:0}\n.v3-photo{width:148px;aspect-ratio:3/4;object-fit:cover;display:block;border-radius:14px;border:3px solid #fff;box-shadow:0 8px 22px #173c6b24;flex-shrink:0}\n.v3-photo+.v3-photo{transform:translateY(-10px)}\n@media(max-width:560px){.v3-hero{padding:16px;gap:12px}.v3-photos{gap:8px}.v3-photo{width:64px;border-width:2px}.v3-photo+.v3-photo{transform:translateY(-6px)}.v3-hero p{font-size:11px}.v3-label{font-size:10px}}\n</style>', unsafe_allow_html=True)
photo_html = '<div class="v3-photos">' + ''.join(
    f'<img class="v3-photo" src="data:image/jpeg;base64,{photo}" alt="ภาพประจำ dashboard">'
    for photo in photos if photo) + '</div>'
st.markdown(f'<section class="v3-hero"><div><span class="v3-label">AI TRADING · H1CON_RAW_V1</span><h1>AI Trading<br>Decision System</h1><p>XAUUSD · H4 / H1 / M15 / M5</p><p>ระบบหลัก: H1CON ไม่มี AI · Shadow: H1CON+AI</p><p>ข้อมูล MT5 · ประเมินด้วย Python · PAPER ONLY</p></div>{photo_html}</section>', unsafe_allow_html=True)


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


MAIN_POLICY = "H1CON_RAW_V1"
SHADOW_POLICY = "H1CON_AI_V1"


def _nth_sunday(year, month, n):
    d = datetime(year, month, 1, tzinfo=timezone.utc)
    first = d + timedelta(days=(6 - d.weekday()) % 7)
    return first + timedelta(days=7 * (n - 1))


def new_york_offset_hours(now_utc):
    """US DST without tz database: 2nd Sunday of March 07:00 UTC to 1st Sunday of November 06:00 UTC."""
    start = _nth_sunday(now_utc.year, 3, 2) + timedelta(hours=7)
    end = _nth_sunday(now_utc.year, 11, 1) + timedelta(hours=6)
    return -4 if start <= now_utc < end else -5


def gold_market_open(now_utc):
    """Hours in which the MT5 feed is expected (New York time), taken from the recorded feed:
    quotes stop at 16:58 and return at 19:00 every day; the week starts Sunday ~21:00 and ends Friday 16:58.
    Outside these hours a missing quote is normal and no alert is shown."""
    ny = now_utc + timedelta(hours=new_york_offset_hours(now_utc))
    minute = ny.hour * 60 + ny.minute
    if ny.weekday() == 5:
        return False
    if ny.weekday() == 6:
        return minute >= 21 * 60
    if ny.weekday() == 4 and minute >= 16 * 60 + 55:
        return False
    return not (16 * 60 + 55 <= minute < 19 * 60 + 5)


def show_feed_alert(quote_time):
    """Prominent alert when quotes stop arriving while the gold market is open."""
    now = datetime.now(timezone.utc)
    if not isinstance(quote_time, (int, float)):
        st.error("⚠️ ไม่พบเวลาราคาล่าสุดจาก MT5 — ตรวจ MT5 และ EA AI_DataSender บน VPS")
        return
    age_min = (now.timestamp() - quote_time) / 60
    if gold_market_open(now) and age_min > 10:
        st.error(f"⚠️ ราคาหยุดส่งมาแล้ว {age_min:,.0f} นาที ขณะที่ตลาดทองเปิดอยู่ — "
                 "ตรวจว่า MT5 เปิดอยู่ และ EA AI_DataSender ยังอยู่บนกราฟ (ระบบจะไม่เข้าไม้จนกว่าราคาจะกลับมา)")
    elif not gold_market_open(now):
        st.info(f"ตลาดทองปิดอยู่ (วันหยุด/ช่วงพักรายวัน) • ราคาล่าสุดเมื่อ {age_min:,.0f} นาทีก่อน")


def show_system_banner(diagnostics):
    policy = (diagnostics or {}).get("policy")
    bangkok = timezone(timedelta(hours=7))
    if policy == MAIN_POLICY:
        since = diagnostics.get("main_policy_since")
        since_text = datetime.fromtimestamp(since, bangkok).strftime("%d/%m/%Y %H:%M") if since else "—"
        st.success(f"✅ ระบบหลัก: **{MAIN_POLICY}** — H1CON ไม่มี AI (เข้าทุกสัญญาณ, TP/SL 12, ถือครั้งละไม้) "
                   f"• เริ่มใช้ตั้งแต่ {since_text} น.")
        st.info(f"🔍 Shadow: **{SHADOW_POLICY}** — H1CON + AI (รับไม้เมื่อโอกาส > 55%) จำลองคู่ขนาน "
                "ไม่มีผลต่อการตัดสินใจของระบบหลัก")
    else:
        st.error(f"ระบบบน VPS ยังรายงาน policy = {policy or 'N/A'} (ยังไม่ใช่ {MAIN_POLICY}) — การอัปเกรดยังไม่สมบูรณ์")


def show_compare(report):
    st.divider()
    st.subheader("เทียบผลสะสมตั้งแต่อัปเกรด · ระบบหลัก vs Shadow")
    if not report or report.get("status") != "OK":
        st.info("ยังไม่มีข้อมูลเปรียบเทียบ (รอไม้แรกหลังอัปเกรด หรือรายงานยังไม่อัปเดต)")
        return
    since = report.get("since_utc")
    if since:
        st.caption("ตั้งแต่เวลาไทย " + datetime.fromisoformat(since).astimezone(timezone(timedelta(hours=7))).strftime("%d/%m/%Y %H:%M"))
    cols = st.columns(2)
    for col, key, title in ((cols[0], "main", "ระบบหลัก · H1CON ไม่มี AI"), (cols[1], "shadow", "Shadow · H1CON + AI")):
        v = (report.get("systems") or {}).get(key) or {}
        with col:
            st.markdown(f"**{title}** (`{v.get('policy', 'N/A')}`)")
            a, b, c = st.columns(3)
            a.metric("ไม้ที่ปิดแล้ว", v.get("closed", 0))
            b.metric("TP / SL", f"{v.get('tp', 0)} / {v.get('sl', 0)}")
            win = v.get("win_rate")
            c.metric("อัตรา TP", f"{win*100:.0f}%" if isinstance(win, (int, float)) else "—")
            net = v.get("net_price_move", 0)
            st.metric("ผลรวม (หน่วยราคา ≈ $ ที่ 0.01 lot)", f"{net:+,.2f}")
            st.caption("ไม้ที่เปิดอยู่: " + (v.get("open_side") or "ไม่มี"))
    st.caption("ผลจำลองจากราคาที่ตรวจพบ ไม่ใช่กำไรจริงจากโบรกเกอร์ • ไม้ที่เปิดก่อนอัปเกรดไม่นับในตารางนี้")


def price(value):
    if isinstance(value, (int, float)):
        return f"{value:,.2f}"
    return "N/A"


def show_paper_report(report, title="ออเดอร์จำลองรอบปัจจุบัน · ระบบหลัก H1CON_RAW_V1 · เริ่มรอบใหม่ 07:00 น."):
    st.divider()
    st.subheader(title)
    st.caption("ผลจากการรันสด PAPER ONLY — ไม่มีการส่งออเดอร์เข้าบัญชี MT5")
    if not report or report.get("status") != "OK":
        st.info("ยังไม่มีรายงานจาก VPS หรืออ่านประวัติไม่ได้ จึงยังสรุปจำนวนไม่ได้")
        return
    bangkok = timezone(timedelta(hours=7))

    def local_time(value):
        if not value:
            return "—"
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(bangkok).strftime("%d/%m %H:%M:%S")

    st.caption("ตั้งแต่เวลาไทย: " + local_time(report["window_start_utc"]) + " ถึง " +
               local_time(report["window_end_utc"]))
    generated = datetime.fromisoformat(report["generated_at_utc"].replace("Z", "+00:00"))
    if (datetime.now(timezone.utc) - generated).total_seconds() > 180:
        st.warning("รายงานนี้ยังไม่ได้อัปเดตตามเวลาปัจจุบัน")
    started = report.get("audit_started_at_utc")
    if not started:
        st.warning("ยังไม่พบเวลาที่เริ่มบันทึกการประเมินสด จึงยืนยันความครบถ้วนของช่วงเวลาไม่ได้")
    elif datetime.fromisoformat(started) > datetime.fromisoformat(report["window_start_utc"]):
        st.info("เริ่มมีบันทึกสดเวลาไทย " + local_time(started) + " — เริ่มบันทึกหลังเวลาเริ่มรอบ")
    st.caption("เริ่มรอบถัดไป: " + local_time(report["next_reset_utc"]) +
               " น. • อัปเดตอัตโนมัติประมาณ 15–30 วินาที ประวัติเดิมไม่ถูกลบ")
    counts = report["counts"]
    a, b, c = st.columns(3)
    a.metric("เข้า BUY ในช่วงนี้", counts["buy_entries"])
    b.metric("เข้า SELL ในช่วงนี้", counts["sell_entries"])
    c.metric("สถานะจำลองที่ยังเปิด", counts["open_positions"])
    d, e, f = st.columns(3)
    d.metric("ตรวจพบแตะ TP ในช่วงนี้", counts["tp_observed"])
    e.metric("ตรวจพบแตะ SL ในช่วงนี้", counts["sl_observed"])
    f.metric("ยังแยกลำดับ TP/SL ไม่ได้", counts["unresolved_positions"])
    st.caption("นับการเข้าจากเวลา ENTRY และการออกจากเวลา EXIT แยกกัน "
               "ตารางรวมรายการที่เข้า/ออกในช่วงนี้ และรายการเก่าที่ยังเปิดอยู่")
    if counts["exits_with_coverage_gap"]:
        st.warning("มีรายการออก " + str(counts["exits_with_coverage_gap"]) +
                   " รายการที่ข้อมูลราคาไม่ครบ ไม่ถือเป็นผลชนะ/แพ้ที่ยืนยันเส้นทางครบถ้วน")
    labels = {"OPEN": "กำลังติดตาม", "TP_TOUCHED": "ตรวจพบแตะ TP",
              "SL_TOUCHED": "ตรวจพบแตะ SL", "UNRESOLVED_TP_SL": "ลำดับ TP/SL ไม่ชัดเจน",
              "MISSING_EXIT_RECORD": "ยังไม่พบบันทึกออก"}
    rows = []
    for trade in report["trades"]:
        result = labels.get(trade["status"], trade["status"])
        if trade["status"] == "OPEN" and not trade["entry_in_window"]:
            result += " • ค้างจากรอบก่อน"
        if trade["coverage_gap"]:
            result += " • ข้อมูลราคาไม่ครบ"
        rows.append({"ID": trade["id"], "ฝั่ง": trade["side"],
                     "เวลาเข้า (ไทย)": local_time(trade["entry_time_utc"]),
                     "ราคาเข้า": trade["entry_price"], "TP": trade["tp"], "SL": trade["sl"],
                     "RR ตอนเข้า": trade.get("rr"), "ผล": result,
                     "MFE ที่พบ": trade.get("mfe_observed"),
                     "MAE ที่พบ": trade.get("mae_observed"),
                     "Policy ตอนเข้า": trade.get("policy"),
                     "เหตุผลเลือกฝั่งตอนเข้า": (trade.get("selection") or {}).get("selection_reason"),
                     "เวลาออก (ไทย)": local_time(trade.get("exit_time_utc")),
                     "ราคาที่ตรวจพบตอนออก": trade.get("exit_observed_price"),
                     "การเปลี่ยนราคาตามฝั่ง": trade.get("observed_price_move"),
                     "รอบที่เข้า": "รอบนี้" if trade["entry_in_window"] else "รอบก่อน"})
    if rows:
        st.dataframe(rows, hide_index=True)
    else:
        st.info("ไม่มีออเดอร์จำลองที่เข้า/ออกในช่วงนี้ และไม่มีสถานะที่ยังเปิดอยู่")
    st.caption("การเปลี่ยนราคาเป็นหน่วยราคา ไม่ใช่กำไรเป็นเงิน ราคาที่ตรวจพบตอนออกไม่ใช่ราคาจับคู่จริง "
               "ข้อมูลขาดรวมถึงช่วงที่ไม่ทราบราคา Ask ย้อนหลัง จึงไม่คำนวณ Win rate จากรายการเหล่านี้")


def show_post_sl(report):
    st.divider()
    st.subheader('ติดตามหลัง SL · จนปิดแท่ง M5')
    st.caption('ข้อมูลเพื่อวิเคราะห์เท่านั้น • ไม่เปลี่ยนผล SL และไม่ใช้เลือกฝั่งหรือเปิดไม้')
    if not report or report.get('status') != 'OK':
        st.info('ข้อมูลติดตามยังไม่พร้อมหรือยังไม่อัปเดต การตัดสินใจทำงานแยกจากส่วนนี้')
        return
    rows = []
    labels = {'PENDING':'กำลังติดตาม','INSUFFICIENT_DATA':'ข้อมูลไม่พอ',
              'RETURNED_INSIDE_SL_AT_LAST_QUOTE':'ราคาล่าสุดกลับเข้า SL',
              'STILL_OUTSIDE_SL_AT_LAST_QUOTE':'ราคาล่าสุดยังอยู่นอก SL'}
    def local(t):
        return datetime.fromtimestamp(t, timezone(timedelta(hours=7))).strftime('%d/%m %H:%M:%S') if t else '—'
    for v in report.get('items', []):
        rows.append({'ID':v['trade_id'],'ฝั่ง':v['side'],'เวลา SL':local(v['exit_time']),
          'ติดตามถึง':local(v['deadline']),'MFE หลังออก':v['mfe_after_exit'],
          'MAE หลังออก':v['mae_after_exit'],
          'TP เดิมหลัง SL':'ตรวจพบแตะ' if v['tp_observed_after_sl'] else 'ยังไม่พบในข้อมูล',
          'เวลาแตะ TP':local(v.get('first_tp_time')),
          'ผลติดตาม':labels.get(v['classification'],v['classification']),
          'ราคาปิด Bid M5':v.get('exact_bid_candle_close'),
          'ข้อมูล':v['coverage']})
    if rows:st.dataframe(rows,hide_index=True)
    else:st.caption('ยังไม่มีรายการ SL ที่ติดตามในรอบนี้')
    st.caption('MFE/MAE หลังออกวัดจากราคาที่ตรวจพบตอน SL ตามฝั่งเดิม ใช้เฉพาะราคาหลังออก '
               'SELL ใช้ Ask; ราคาปิดแท่งย้อนหลังเป็น Bid จึงยืนยัน Ask ตอนปิดไม่ได้ '
               'ไม่พบการแตะ TP ในข้อมูล ไม่ได้ยืนยันว่าไม่เคยแตะระหว่างจุดบันทึก')


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
    show_system_banner(decision.get("diagnostics"))
    show_feed_alert((snapshot.get("quote") or {}).get("time"))

    hybrid = decision.get("execution_mode") == "PAPER_ONLY"
    if age > (120 if hybrid else 20 * 60):
        st.warning(
            "Data feed is stale. "
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
        "**Candle timestamp (UTC for upgraded feed):**",
        market.get("timestamp", "N/A"),
    )
    st.caption("Page refreshes every 15 seconds. VPS evaluates incoming quotes independently; "
               "the dashboard is a sampled view, not a trading terminal.")
    if hybrid:
        st.info("PAPER ONLY — entries and outcomes below are simulated. "
                "Actual MT5 positions are not connected; no orders are sent.")
        st.write("**Lifecycle:**", decision.get("state", "WAIT"))
        st.write("**Reason:**", decision.get("reason", "N/A"))
        st.write("**H4 direction:**", decision.get("direction", "NEUTRAL"))
        st.write("**H1 context:**", (decision.get("timeframes", {}).get("H1") or {}).get("direction", "N/A"))
        st.write("**Candidate setup direction:**", decision.get("setup_direction") or "NONE")
        st.write("**Setup mode:**", decision.get("setup_mode", "N/A"))
        diagnostics = decision.get("diagnostics")
        if diagnostics:
            st.caption("H4/H1 เป็นบริบท ใช้โครงสร้างและปฏิกิริยาราคาเลือกฝั่ง "
                       "ระดับราคาถูกใช้เมื่อพบปฏิกิริยา ไม่ใช่คะแนนความแข็งแรงที่ยืนยันแล้ว "
                       "เงื่อนไขเข้าและ RR เดิมยังทำงาน")
            st.write("**Policy:**", diagnostics.get("policy", "N/A"))
            if diagnostics.get("policy") == MAIN_POLICY:
                st.caption("H1CON_RAW_V1: จังหวะเข้าจาก EA H1_con_cool (H1 EMA50/100 + แท่งย่อ M15 + RSI14) • "
                           "เข้าทุกสัญญาณเมื่อไม่มีไม้เปิด (ไม่มี AI กรอง) • TP/SL 12.0 • ไม่มีตัวกรองช่วงเวลา • "
                           "ถือได้ครั้งละไม้ • ไม่มีระบบแก้ไม้ • ค่าโอกาสจาก AI บันทึกไว้เพื่อเทียบเท่านั้น")
                signal = diagnostics.get("last_signal") or {}
                if signal.get("side"):
                    p = signal.get("p")
                    st.write("**สัญญาณล่าสุด:**", signal.get("side"), "| **ระบบหลัก:**",
                             {"ENTERED": "เข้าไม้", "MAIN_BUSY": "มีไม้เปิดอยู่ ไม่เข้าเพิ่ม"}.get(signal.get("status"), signal.get("status")),
                             "| **AI (shadow) ให้โอกาส:**", f"{p*100:.1f}%" if isinstance(p, (int, float)) else "N/A",
                             "| **Shadow:**", {"SHADOW_ENTERED": "เข้าไม้", "SKIPPED_BY_AI": "AI ไม่รับ",
                                              "SHADOW_BUSY": "มีไม้เปิดอยู่"}.get(signal.get("shadow_status"), signal.get("shadow_status") or "—"))
                book = decision.get("paper_trade") or {}
                if book.get("policy") and book.get("policy") != MAIN_POLICY:
                    st.write("**ไม้ที่ถือ:** ไม้เดิมก่อนอัปเกรด (" + str(book.get("policy")) + ") ถือจนปิดตาม TP/SL เดิม")
                sp = diagnostics.get("shadow_position") or {}
                st.write("**ไม้ของ Shadow (H1CON+AI):**", sp.get("side") or "ไม่มี",
                         ("| เข้า " + price(sp.get("entry_price")) + " | TP " + price(sp.get("tp")) + " | SL " + price(sp.get("sl"))) if sp else "")
                st.caption("ข้อมูล V5 ด้านล่าง (selection / candidate) เป็นข้อมูลวิจัย ไม่ใช่ตัวตัดสินเข้าไม้")
            elif diagnostics.get("policy") == "H1CON_AI_V1":
                st.caption("H1CON AI: จังหวะเข้าจาก EA H1_con_cool (H1 EMA50/100 + แท่งย่อ M15 + RSI14) • "
                           "AI (gradient boosting) ประเมินโอกาสถึง TP ก่อน SL • รับไม้เมื่อโอกาส > 55% • TP/SL 12.0 • "
                           "ไม่มีตัวกรองช่วงเวลา • ถือได้ครั้งละไม้ • ไม่มีระบบแก้ไม้")
                signal = diagnostics.get("last_signal") or {}
                if signal.get("side"):
                    p = signal.get("p")
                    st.write("**สัญญาณล่าสุด:**", signal.get("side"), "| **AI ให้โอกาส:**",
                             f"{p*100:.1f}%" if isinstance(p, (int, float)) else "N/A",
                             "| **ผล:**", {"ENTERED": "เข้าไม้", "SKIPPED_BY_AI": "AI ไม่รับ", "TAKE": "เข้าไม้"}.get(signal.get("status"), signal.get("status")))
                book = decision.get("paper_trade") or {}
                if book.get("policy") and book.get("policy") != "H1CON_AI_V1":
                    st.write("**ไม้ที่ถือ:** ไม้เดิมก่อนติดตั้ง (" + str(book.get("policy")) + ") ถือจนปิดตาม TP/SL เดิม")
                st.caption("ข้อมูล V5 ด้านล่าง (selection / candidate) เป็นข้อมูลวิจัย ไม่ใช่ตัวตัดสินเข้าไม้")
            elif diagnostics.get("policy") == "SESSION_BIAS_S5B_V1":
                st.caption("S5B: เอเชีย 07:00–14:00 รับเฉพาะ BUY • นิวยอร์ก 19:30–02:00 รับเฉพาะ SELL • นอกช่วงไม่เปิดไม้ใหม่ • "
                           "H1 มีเทรนด์ = ย่อแตะ EMA20 M15 (SL 1.0 / TP 1.5 ATR) • M15 ไม่มีเทรนด์ = fade ขอบกรอบไปกึ่งกลาง • ถือได้ครั้งละไม้")
                sess = {"ASIA": "เอเชีย", "NY": "นิวยอร์ก", "OUTSIDE": "นอกช่วงเทรด"}
                st.write("**ช่วงเวลา:**", sess.get(diagnostics.get("session"), diagnostics.get("session")),
                         "| **รับฝั่ง:**", diagnostics.get("session_allowed_side") or "ไม่เปิดไม้ใหม่",
                         "| **H1 / M15:**", diagnostics.get("h1_trend", "N/A"), "/", diagnostics.get("m15_trend", "N/A"))
                signal = diagnostics.get("last_signal") or {}
                if signal.get("status", "").startswith("SKIPPED"):
                    st.info("สัญญาณ " + str(signal.get("signal")) + " " + str(signal.get("side")) + " ถูกกรอง: " + signal["status"])
                book = decision.get("paper_trade") or {}
                if book.get("component") == "LEGACY":
                    st.write("**ไม้ที่ถือ:** ไม้ V5 เดิมก่อนติดตั้ง ถือจนปิดตาม TP/SL เดิม")
                st.caption("ข้อมูล V5 ด้านล่าง (selection / candidate) เป็นข้อมูลวิจัย ไม่ใช่ตัวตัดสินเข้าไม้")
            else:
                st.caption("V5.1: แท่งในกรอบ + 2 quote + chase 0.45 ATR; เฉพาะ setup ที่อ้างตามขาต่อจาก M5 ต้องมี M15 candidate ตรงฝั่ง")
            if decision.get('reason') == 'M15_TREND_AGAINST_ENTRY':
                st.info("ยกเลิก setup: เทรนด์ M15 สวนฝั่งที่จะเข้าไม้")
            if decision.get('reason') == 'CONTINUATION_WITHOUT_M15_CANDIDATE':
                st.info('ยกเลิก setup ตามขาต่อ: ยังไม่มี M15 candidate ตรงฝั่ง')
            selection = diagnostics.get("selection") or {}
            st.write("**เหตุผลเลือกฝั่ง:**", selection.get("selection_reason", "N/A"))
            st.write("**M15 / M5 candidate:**", selection.get("m15_candidate") or "NONE",
                     "/", selection.get("m5_candidate") or "NONE")
            rows = []
            for tf in ("H4", "H1", "M15", "M5"):
                f = (decision.get("timeframes") or {}).get(tf) or {}
                rows.append({"Timeframe": tf, "Direction": f.get("direction"),
                             "Structure": f.get("structure"),
                             "Swing high": (f.get("price_action") or {}).get("swing_high"),
                             "Swing low": (f.get("price_action") or {}).get("swing_low"),
                             "Close": f.get("last_close"),
                             "EMA20": f.get("ema20"), "EMA50": f.get("ema50")})
            st.dataframe(rows, hide_index=True)
            with st.expander("Entry checks and blocking values"):
                st.json(diagnostics)
            with st.expander("แนวรับ–ต้านและปฏิกิริยา (ข้อมูลเสริม ไม่บล็อกไม้)"):
                st.json({tf: ((decision.get("timeframes") or {}).get(tf) or {}).get("price_action", {})
                         for tf in ("M15", "M5")})
        trade = decision.get("paper_trade") or {}
        st.write("**Paper position:**", trade.get("side", "NONE"))
        if trade:
            st.write("**Paper entry price:**", price(trade.get("entry_price")))
            st.write("**MFE observed (price units):**", price(trade.get("mfe_observed")))
            st.write("**MAE observed (price units):**", price(trade.get("mae_observed")))
            st.caption("Observed MFE can miss movement between quotes. Historical SELL exits "
                       "cannot be reconstructed exactly without ask-price history.")
        quote = snapshot.get("quote") or {}
        if quote:
            quote_age = datetime.now(timezone.utc).timestamp() - quote["time"]
            st.write("**Last sampled bid / ask:**", price(quote.get("bid")), "/", price(quote.get("ask")))
            if quote_age > 120:
                st.warning("Live quote is stale. Do not interpret this snapshot as a current entry.")

    col1, col2, col3 = st.columns(3)
    col1.metric("Candle close", price(market.get("close")))
    col2.metric("New entry / lifecycle action", decision.get("decision", "N/A"))
    col3.metric("Quality (not a win probability)", entry.get("quality", "N/A"))

    col4, col5 = st.columns(2)
    col4.metric("Paper target price" if hybrid else "Target price", price(target.get("target_price")))
    col5.metric("Paper invalidation price" if hybrid else "Invalidation price", price(target.get("invalid_price")))

    show_compare(snapshot.get("system_compare"))
    show_paper_report(snapshot.get("paper_report_session"))
    show_paper_report(snapshot.get("shadow_report_session"),
                      "Shadow · H1CON + AI (H1CON_AI_V1) · ออเดอร์จำลองรอบปัจจุบัน · ไม่มีผลต่อระบบหลัก")
    show_post_sl(snapshot.get("post_sl_research"))
    with st.expander('ประวัติเหตุผล setup: ต้นกำเนิด → ระหว่างรอ → ตอนเข้า',expanded=False):
        report=snapshot.get('setup_lifecycle') or {}
        st.caption('ข้อมูลสำหรับวิเคราะห์ ไม่เปลี่ยนการตัดสินใจ แสดงรายการล่าสุด; ประวัติครบอยู่ใน ZIP')
        st.write('สถานะข้อมูล:',report.get('status','WAITING_FOR_V5_SYNC'))
        for item in report.get('items',[]):
            origin=item.get('origin') or {}; oe=origin.get('evidence') or {}; entry=item.get('entry') or {}
            ee=entry.get('evidence') or {}; pending=item.get('latest_setup') or {}
            st.write('**Setup:**',item.get('setup_id'), '—',item.get('status'))
            st.write('**ต้นกำเนิด:**',(oe.get('selection') or {}).get('selection_reason') or item.get('origin_status'))
            st.write('**เหตุผลล่าสุด:**',((item.get('last_evidence') or {}).get('selection') or {}).get('selection_reason','N/A'))
            st.write('**เหตุผลตอนเข้า:**',(ee.get('selection') or {}).get('selection_reason','ยังไม่เข้า'))
            st.write('**โซน / จุดที่เหตุผลเสีย:**',price(pending.get('zone_low')),'–',price(pending.get('zone_high')),'/',price(pending.get('sl')))
            st.caption('ระดับที่ใช้วางแผน อาจต่างจาก SL ตอนเข้าที่คำนวณจากจังหวะย่อ')
            st.json(item)


    st.divider()
    st.subheader("MT5 candle")
    st.json(market)

    st.subheader("Analysis from VPS")
    st.json(decision)


dashboard()
