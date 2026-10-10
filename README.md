# 🇻🇳 Hanoi Lottery Statistical & Prediction System
### ระบบสถิติ คำนวณสูตร และแนะนำชุดตัวเลขหวยฮานอย (พิเศษ 17:30 / ปกติ 18:30 / VIP 19:30)

ระบบเว็บแอปพลิเคชันและ REST API สำหรับติดตามผลรางวัล บันทึกสถิติ วิเคราะห์ความถี่ตัวเลข และคำนวณแนวทางตัวเลขด้วยโมเดลคณิตศาสตร์ 22 รูปแบบ พร้อมชุดตัวเลขคัดพิเศษ (เลขรูดตัวเดียว, ชุดสู้ชีวิต 10-40 ตัว, ชุดบน-ล่าง 10-50 ตัว) และฟังก์ชัน 1-Click Copy Text สำหรับนำไปใช้งานต่อบน LINE / Telegram

---

## 🌟 หน้าการใช้งานหลัก (Web Dashboard)
1. **🏠 หน้าแรก (Live Dashboard - `/`):** แสดงผล 3 รอบสดๆ ล่าสุด พร้อมระบบนับเวลาถอยหลังสู่งวดถัดไป
2. **🎯 แนวทางชุดตัวเลข (`/recommend`):** คำนวณแนวทางตัวเลขทุกชุด พร้อมปุ่มคัดลอกข้อความ
3. **📊 สถิติเชิงลึก (`/stats`):** กราฟความถี่ตัวเลข 0-9 และตารางวิเคราะห์เลขเด่น/เลขดับ (Hot / Cold)
4. **🏆 จัดอันดับสูตร (`/leaderboard`):** แสดงตารางเปรียบเทียบสูตรคำนวณทั้ง 22 โมเดล เรียงตาม Win Rate %
5. **⚙️ จัดการข้อมูลผลรางวัล (`/manage`):** บันทึกผลใหม่, ลบข้อมูล, ปุ่มล้างข้อมูลทั้งหมด และนำเข้า/ส่งออกไฟล์ CSV / JSON

---

## 🚀 วิธีติดตั้งและรันบน Render.com (ฟรี 100%)
1. อัปโหลดไฟล์ทั้งหมดในโปรเจกต์นี้ขึ้น GitHub Repository ของคุณ
2. เข้าสู่ระบบที่ **[render.com](https://render.com)** ด้วยบัญชี GitHub
3. กดปุ่ม **New +** -> เลือก **Web Service**
4. เลือก Repository ที่คุณอัปโหลด
5. ตั้งค่าดังนี้:
   - **Environment:** `Python 3`
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `gunicorn app:app`
6. กดปุ่ม **Deploy Web Service**
7. รอประมาณ 1-2 นาที คุณจะได้ลิงก์เว็บไซต์พร้อมใช้งานตลอด 24 ชั่วโมง

---

## 💻 การรันบนเครื่องคอมพิวเตอร์ (Local)
```bash
# 1. ติดตั้งไลบรารี
pip install -r requirements.txt

# 2. รันเว็บเซิร์ฟเวอร์
python main.py web
# หรือ
python app.py
```
เปิดเบราว์เซอร์ไปที่: `http://localhost:5000`

---

## 📁 โครงสร้างโปรเจกต์
```
├── app.py                   # เซิร์ฟเวอร์ Flask และ REST API ทั้งหมด
├── database.py              # ระบบจัดการฐานข้อมูล SQLite (CRUD & Import/Export)
├── formulas.py              # สูตรคำนวณคณิตศาสตร์ 22 โมเดล & ตัวสร้างชุดตัวเลข
├── stats.py                 # วิเคราะห์สถิติความถี่ตัวเลข 0-9 และ Hot/Cold
├── backtest.py              # คำนวณ Win Rate % ของแต่ละสูตรย้อนหลัง
├── fetcher.py               # ตัวช่วยดึงผลรางวัล
├── pipeline.py              # Pipeline ประมวลผล
├── main.py                  # Entry Point
├── real_hanoi_history.csv   # ข้อมูลผลรางวัลย้อนหลังของจริง (231 งวด 77 วัน)
├── hanoi.db                 # ฐานข้อมูล SQLite พร้อมข้อมูลจริง
├── Procfile                 # คำสั่ง Start สำหรับ Render
├── requirements.txt         # รายการแพ็กเกจ Python
├── templates/               # เทมเพลตหน้าเว็บ HTML (Tailwind CSS)
│   ├── base.html
│   ├── index.html
│   ├── recommend.html
│   ├── stats.html
│   ├── leaderboard.html
│   └── manage.html
└── static/
    └── app.js               # JavaScript ฝั่ง Client-side (Countdown, Toast, Copy, Ajax)
```
