# กติกา V4 — Decision / Audit / Research ต้องแยกกัน

V4 = V2 + แก้ pending setup PRICE_REACTION ค้าง + max_chase_atr 0.50 + ตรวจ M15 ก่อน ENTRY

เมื่อผ่านเงื่อนไขเข้าและ RR เดิมแล้ว ก่อนสร้าง ENTRY:
- BUY และ M15 DOWN: ยกเลิก setup ด้วย M15_TREND_AGAINST_ENTRY
- SELL และ M15 UP: ยกเลิกแบบเดียวกัน
- M15 NEUTRAL หรือทิศเดียวกัน: เข้าได้ตามกติกาเดิม

ใช้ direction M15 ที่คำนวณจากข้อมูลปิดแล้ว: close/EMA20, EMA20/EMA50, ความชัน EMA20 และโครงสร้าง 5 แท่งล่าสุด ต้องครบเงื่อนไข UP/DOWN เดิม ไม่เพิ่ม indicator, การรอปิดแท่ง หรือ H4/H1 veto
ไม่รวมการแก้แท่งยืนยันในกรอบ, 2 quote, ER/RSI/VWAP หรือการกลับ BUY/SELL

core/market_state.py เป็นผู้ตัดสินใจแต่เพียงส่วนเดียว; engine.sqlite3 เก็บ state และ append-only events
research_observer.py อ่าน decision DB แบบ read-only และเขียน research.sqlite3 แยกกัน ห้าม observer กลับไปเปลี่ยน candidate, setup, TP/SL, cooldown หรือผลการเข้าไม้
ห้ามรอ observer ก่อนตัดสินใจ; observer เสียต้องไม่หยุด decision

MFE/MAE หลัง SL ใช้กติกา V3 เดิม เริ่มหลังราคาออกที่สังเกตจนขอบปิด M5 ปัจจุบัน เช่น 22:03 จบ 22:05
BUY ใช้ Bid และ SELL ใช้ Ask ไม่ใช้ High/Low ก่อน SL หรือ Bid OHLC แทน Ask ย้อนหลัง
ไม่เปลี่ยน SL เป็น TP เมื่อราคากลับตัว และไม่ยืนยันว่าไม่แตะ TP เมื่อข้อมูลขาด

ไม้ที่เปิดด้วย V2/V3 ก่อนอัปเดตยังถือด้วย entry/TP/SL/policy เดิม; V4 ไม่ปิดหรือกลับฝั่งอัตโนมัติ
Dashboard แสดง policy ของ engine และ policy ของไม้เดิมแยกกัน รูปเดิมต้องคง bytes เดิม

ระบบยัง READ_ONLY/PAPER_ONLY ไม่มีคำสั่งซื้อขายกับ broker
