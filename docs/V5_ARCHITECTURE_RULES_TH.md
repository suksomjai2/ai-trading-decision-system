# V5.1 — ข้อตกลงระบบ
ฐานV5ล่าสุด + ตรวจM15candidateเฉพาะ setup ที่อ้าง M5 ตามขาต่อ ตามสูตรที่ทดลองได้24TP14SL10 +71.14
CONTEXTUAL_REACTION_V5, PAPER_ONLY, ไม่มี broker order
เกณฑ์ continuation: setup.zone_basis BROKEN_M5_LEVEL_LIVE_CONFIRMED หรือ selection_reason M5_BROKEN_LEVEL_HELD; M15candidateต้องตรงsetupside ตรวจเมื่อotherwiseพร้อมเข้าเท่านั้น
ไม่ใช้กฎนี้ครอบ PRICE_REACTION ทั้งหมด ไม่รวมการออกแบบV6ใหม่ ไม่เปลี่ยนสองquoteเป็นเวอร์ชันadjacentโดยเงียบๆ
Origin ของsetup, active setup ณ เข้า และ selector ปัจจุบันเป็นคนละข้อมูล ห้ามเขียนทับกันหรือใช้ป้ายเหตุผลตอนเข้าแทนต้นกำเนิด
Decision emit facts ในauditเดิม -> observerอ่านแบบread-only -> research.sqlite3/setup_lifecycle + setup_lifecycle_events -> Supabase bounded snapshot -> dashboard
Coreไม่importโมดูลวิจัย ไม่มีqueryฐานวิจัย การขัดข้องของobserverไม่แตะdecision/cooldown/TP/SL
เก็บknown_at, Bid/Ask, M15/M5แท่งที่ปิดแล้ว, selection, โซน/SLของsetup และentry_checks จุดอ้างอิงไม่ใช่หลักฐานว่าแนวรับแข็งแรง
Originก่อนอัปเกรดที่ไม่มีบันทึกใหม่ระบุ UNKNOWN_PRE_V5 ไม่สร้างประวัติย้อนหลังขึ้นเอง
รูปเด็กผู้หญิงใช้assets/dashboard_photo.jpegเดิม ตรวจhashก่อนและหลัง ไม่upload/เปลี่ยนasset
ส่งออก ZIP มีsetup_lifecycle.json + setup_lifecycle_events.jsonl + continuation_entry_vetoes.json และข้อมูลเดิมทั้งหมด
ส่งออกอดีตตัดtraceที่ปลายวัน/เวลาที่ขอ ไม่ใช้summaryปัจจุบันที่มีข้อมูลอนาคต; originก่อนช่วงขอแนบเพื่ออ่านเหตุผลครบ
PostSL1M5เดิมยังแยกข้อมูลวิจัย บันทึกไม่ใช่กำไรเงินจริง ไม่มีการเปลี่ยนSLย้อนหลังเป็นTP
เก็บV2_REFERENCEและสำรองV4_SOURCE/runtimeก่อนติดตั้ง rollbackคืนsourceไม่ย้อนฐานข้อมูลปัจจุบัน

แก้ชนิดข้อมูลhold_keyให้เป็นJSONlistทั้งก่อนบันทึก/หลังอ่านSQLite มิฉะนั้นtupleไม่เท่ากับlistทำให้ไม่ผ่าน2quote เป็นการแก้การจัดเก็บข้อมูล ไม่เพิ่มความเข้มของเงื่อนไขและไม่ใช่adjacent-quotefix
