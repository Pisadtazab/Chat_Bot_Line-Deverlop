# Chat Bot LINE — Develop 🤖💬

LINE Chatbot ที่ใช้ RAG (Retrieval-Augmented Generation) พร้อม Typhoon AI สำหรับแนะนำอาจารย์ที่ปรึกษาวิจัย พร้อมระบบแจ้งเตือนคิวและนัดหมายผ่าน LINE Flex Message

---

## 📋 สารบัญ

- [คุณสมบัติ](#-คุณสมบัติ)
- [สถาปัตยกรรมระบบ](#-สถาปัตยกรรมระบบ)
- [โครงสร้างโปรเจกต์](#-โครงสร้างโปรเจกต์)
- [เทคโนโลยีที่ใช้](#-เทคโนโลยีที่ใช้)
- [การติดตั้ง](#-การติดตั้ง)
- [ตัวแปรสภาพแวดล้อม](#-ตัวแปรสภาพแวดล้อม)
- [API Endpoints](#-api-endpoints)
- [การทำงานของ Chatbot](#-การทำงานของ-chatbot)
- [ระบบแจ้งเตือน (Notification)](#-ระบบแจ้งเตือน-notification)

---

## ✨ คุณสมบัติ

- **LINE Messaging API** — รับ-ส่งข้อความผ่าน LINE OA
- **RAG Pipeline** — ดึงข้อมูลจากเอกสาร PDF แล้วส่งให้ AI ตอบ
- **Typhoon AI** — โมเดลภาษาไทยสำหรับสร้างคำตอบ
- **PDF Extraction** — แยกข้อความ + รูปภาพจาก PDF ด้วย PyMuPDF
- **Sentence Transformers** — สร้าง Embeddings สำหรับค้นหาเอกสาร (BAAI/bge-m3)
- **MongoDB + GridFS** — จัดเก็บข้อมูล, Embeddings และไฟล์รูปภาพ
- **LINE Flex Message Notification** — แจ้งเตือนคิว/นัดหมายแบบ Push Message ให้ทั้งนักศึกษาและอาจารย์
- **Cloudflare Tunnel** — เปิด HTTPS URL สาธารณะสำหรับ LINE Webhook ที่ `/callback`
- **Docker Compose** — Deploy ง่ายด้วย Nginx + ngrok (dev mode)

---

## 🏗️ สถาปัตยกรรมระบบ

```
User (LINE App)
    │
    ▼
LINE Platform ──POST /callback──▶ Cloudflare Tunnel
                                        │
                                        ▼
                               FastAPI (main.py) :8000
                                   │
                    ┌──────────────┼──────────────┐
                    ▼              ▼               ▼
            app/routers/    app/retriever.py  app/promrt_typhoon.py
            ├── views.py    (RAG + Embed)     (Typhoon AI)
            ├── extractPDF.py
            ├── getData.py
            └── deleteFile.py
                    │              │
                    ▼              ▼
             templates/       MongoDB + GridFS
             index.html       (DB/database.py)

ระบบ Notify (Push Message):
External System ──POST /NotifyQueueAdivsor/...──▶ FastAPI
                ──POST /NotifyQueueStudent/...──▶
                ──POST /NotifyCancelled/...────▶
                                                    │
                                                    ▼
                                        LINE Push Message API
                                        (Flex Message → ผู้ใช้)
```

---

## 📁 โครงสร้างโปรเจกต์

```
Chat_Bot_Line-Deverlop/
├── app/
│   ├── main.py                          # FastAPI entry point, /callback webhook
│   ├── retriever.py                     # RAG pipeline (query, embedding, image lookup)
│   ├── promrt_typhoon.py                # Typhoon AI system prompt & completion
│   ├── response_message.py              # สร้าง LINE Message objects
│   ├── notification/                    # 🔔 ระบบแจ้งเตือน LINE
│   │   ├── DB/
│   │   │   └── database_noti.py         # MongoDB connection สำหรับ BORC/UserProfile
│   │   ├── routers/
│   │   │   ├── line_notify.py           # push_flex_notification() + /CancelBooking
│   │   │   └── GetLine_id.py            # /NotifyFristLogin/UserLine_id
│   │   └── users/
│   │       ├── Advisor/
│   │       │   ├── NotifyQueue.py       # แจ้งเตือนอาจารย์เมื่อมีนักศึกษาจองคิว
│   │       │   ├── NotifyQueueCancelled.py  # แจ้งเตือนอาจารย์เมื่อนักศึกษายกเลิก
│   │       │   └── NotifyRecheduleAdvisor.py # แจ้งเตือนอาจารย์เมื่อมีการเลื่อนคิว
│   │       └── Student/
│   │           ├── NotifyQueueStudent.py    # แจ้งเตือนนักศึกษาเมื่ออาจารย์ยืนยัน/ยกเลิก
│   │           └── NotifyReaheduleStudent.py # แจ้งเตือนนักศึกษาเมื่ออาจารย์เลื่อนคิว
│   └── routers/
│       ├── views.py                     # Serve หน้า UI (HTML)
│       ├── extractPDF.py                # อัปโหลดและแยก PDF → MongoDB
│       ├── getData.py                   # ดึงรายชื่อ PDF / รูปภาพจาก DB
│       └── deleteFile.py               # ลบไฟล์ PDF จาก DB
├── DB/
│   └── database.py                      # MongoDB connection หลัก, delete_pdf_from_db()
├── templates/
│   └── index.html                       # หน้า Admin UI จัดการ PDF
├── Dockerfile                           # Python 3.12 + FastAPI + Uvicorn
├── docker-compose.yml                   # Services: Nginx + ngrok (dev)
├── requirements.txt                     # Python dependencies
└── .env                                 # ตัวแปรลับ (ไม่ commit)
```

---

## 🛠️ เทคโนโลยีที่ใช้

| หมวด | เทคโนโลยี |
|------|-----------|
| **Backend** | FastAPI, Uvicorn, Starlette |
| **AI / NLP** | Typhoon AI (typhoon-v2.5-30b-a3b-instruct), Sentence Transformers (BAAI/bge-m3), PyThaiNLP |
| **Database** | MongoDB Atlas, GridFS (PyMongo) |
| **PDF** | PyMuPDF (fitz) |
| **LINE** | line-bot-sdk v3, LINE Flex Message Push API |
| **Tunnel (Production)** | Cloudflare Tunnel (cloudflared) |
| **Tunnel (Dev)** | ngrok |
| **Deployment** | Docker, Docker Compose, Nginx |
| **Language** | Python 3.12 |

---

## 🚀 การติดตั้ง

### ข้อกำหนดเบื้องต้น

- Docker & Docker Compose
- LINE Developers Account (Messaging API Channel)
- Typhoon AI API Key
- MongoDB instance (local หรือ Atlas)

### ขั้นตอน

**1. Clone repository**

```bash
git clone https://github.com/Pisadtazab/Chat_Bot_Line-Deverlop.git
cd Chat_Bot_Line-Deverlop
```

**2. สร้างไฟล์ `.env`**

```env
ACCESS_TOKEN=your_line_channel_access_token
CHANNEL_SECRET=your_line_channel_secret
Typhoon_api_key=your_typhoon_api_key
MONGO_URI=your_mongodb_connection_string          # สำหรับ chatbot DB
MONGO_URI_LOCAL=your_mongodb_local_connection     # สำหรับ notification DB (BORC)
NGROK_TOKEN=your_ngrok_authtoken
NGROK_URL=your_ngrok_or_cloudflare_url
```

**3. รันแอปพลิเคชัน**

```bash
# รันตรงๆ
uvicorn app.main:app --host 0.0.0.0 --port 5000 --reload

# หรือผ่าน Docker
docker-compose up -d
```

---

## 🔑 ตัวแปรสภาพแวดล้อม

| ตัวแปร | คำอธิบาย |
|--------|----------|
| `ACCESS_TOKEN` | LINE Channel Access Token สำหรับส่งข้อความ |
| `CHANNEL_SECRET` | LINE Channel Secret สำหรับ verify webhook |
| `Typhoon_api_key` | Typhoon AI API Key |
| `MONGO_URI` | MongoDB URI สำหรับ chatbot (`employee_research_db`) |
| `MONGO_URI_LOCAL` | MongoDB URI สำหรับระบบ notify (`BORC`) |
| `NGROK_TOKEN` | ngrok authtoken (สำหรับ dev เท่านั้น) |
| `NGROK_URL` | URL สาธารณะสำหรับ serve รูปภาพ (ngrok หรือ Cloudflare) |

> ตัวแปรรองรับการอ่านจาก `/secrets/<name>` (Cloud Run Secret Manager) โดยอัตโนมัติ

---

## 📡 API Endpoints

### Chatbot & Admin

| Method | Path | คำอธิบาย |
|--------|------|----------|
| `POST` | `/callback` | LINE Webhook รับ event จาก LINE Platform |
| `GET` | `/` | Admin UI (HTML) จัดการไฟล์ PDF |
| `POST` | `/upload_pdf` | อัปโหลด PDF และแยกข้อมูลเข้า MongoDB |
| `GET` | `/files` | ดึงรายชื่อ PDF ทั้งหมดจาก DB |
| `DELETE` | `/delete_file?pdf_name=...` | ลบไฟล์ PDF พร้อมรูปภาพออกจาก DB |
| `GET` | `/image/{file_id}` | ดึงรูปภาพจาก GridFS ด้วย ObjectId |

### Notification

| Method | Path | คำอธิบาย |
|--------|------|----------|
| `POST` | `/NotifyFristLogin/UserLine_id` | แจ้งเตือนเมื่อผู้ใช้ผูก LINE กับระบบ |
| `POST` | `/NotifyQueueAdivsor/...` | แจ้งเตือนอาจารย์เมื่อมีนักศึกษาจองคิว |
| `POST` | `/NotifyQueueAdivsor/RecheduleAdvisor` | แจ้งเตือนอาจารย์เมื่อมีการเลื่อนนัด |
| `POST` | `/NotifyCancelled/CancelBooking` | แจ้งเตือนอาจารย์เมื่อนักศึกษายกเลิกการจอง |
| `POST` | `/NotifyQueueStudent/NotifyStudent` | แจ้งเตือนนักศึกษาเมื่ออาจารย์ยืนยันหรือยกเลิก |
| `POST` | `/NotifyQueueStudent/RecheduleStudent` | แจ้งเตือนนักศึกษาเมื่ออาจารย์เลื่อนนัด |

---

## 💬 การทำงานของ Chatbot

1. ผู้ใช้ส่งข้อความใน LINE
2. LINE ส่ง Webhook มาที่ `POST /callback` ผ่าน Cloudflare Tunnel
3. ระบบแสดง Loading animation ให้ผู้ใช้รอ
4. `retriever.py` สร้าง embedding จากคำถามด้วย BAAI/bge-m3 แล้วค้นหา vector search ใน MongoDB
5. `promrt_typhoon.py` ส่ง context + คำถามไปให้ Typhoon AI สร้างคำตอบ
6. ระบบดึงรูปภาพที่เกี่ยวข้องจาก GridFS (ถ้ามี)
7. ตอบกลับผู้ใช้ผ่าน LINE Reply Message API (ข้อความ + รูปภาพ)

---

## 🔔 ระบบแจ้งเตือน (Notification)
> ⚠️ **Note:** ระบบแจ้งเตือน (Notification System) อยู่ใน branch [`feature/notifications`](../../tree/feature/notifications)

ระบบแจ้งเตือนทำงานแบบ **Push Message** ผ่าน LINE Messaging API โดยส่งข้อความในรูปแบบ **Flex Message** (การ์ดสวยงาม) ไปยัง LINE ของผู้ใช้โดยตรง ไม่ต้องรอให้ผู้ใช้ส่งข้อความมาก่อน

### โครงสร้างข้อมูล (MongoDB: BORC)

ระบบ notify ใช้ฐานข้อมูลแยก (`BORC`) ซึ่งมี collections ดังนี้:
- `UserProfile` — เก็บ `userId` (LINE User ID) และข้อมูลผู้ใช้ที่สมัครในระบบจอง
- `BookingOnline` — เก็บข้อมูลการจองนัดหมาย

### รูปแบบ Flex Message

ทุก notification ส่งเป็น Flex Message แบบ `bubble` ที่มีโครงสร้าง 3 ส่วน:

```
┌─────────────────────────────┐
│ 🔔 [ชื่อการแจ้งเตือน]  (header สี) │
├─────────────────────────────┤
│ 👤 ชื่อ        [ชื่อ]         │
│ 📅 วันที่       [วันที่]       │  (body)
│ ⏰ เวลา        [เวลา]         │
│ ─────────────────────────── │
│ 🔖 สถานะ      [สถานะ]        │
├─────────────────────────────┤
│     ระบบแจ้งเตือนอัตโนมัติ     │  (footer)
└─────────────────────────────┘
```

### ประเภทการแจ้งเตือนและ Request Body

#### 1. แจ้งเตือนเมื่อผูก LINE กับระบบ (`/NotifyFristLogin/UserLine_id`)

ส่งเมื่อผู้ใช้ login ครั้งแรกและผูก LINE User ID เข้าระบบ

```json
POST /NotifyFristLogin/UserLine_id
{
  "userId": "U521b4c90449e6f574705dbbd70de11a7",
  "Firstname": "สมชาย"
}
```

ระบบจะตรวจสอบว่า `userId` นี้มีสถานะ `Approved` ใน DB หรือไม่ ถ้ามีจะส่ง Flex Message ต้อนรับ (สีเขียว)

---

#### 2. แจ้งเตือนอาจารย์ — มีนักศึกษาจองคิว (`/NotifyQueueAdivsor/...`)

> ไฟล์: `notification/users/Advisor/NotifyQueue.py`

ส่งเมื่อนักศึกษาจองนัดหมายกับอาจารย์สำเร็จ

```json
POST /NotifyQueueAdivsor/[endpoint]
{
  "AdvisorId": "Uxxxxxxxxxxxxxxxx",   // LINE userId ของอาจารย์
  "StudentName": "นายสมศักดิ์ ใจดี",
  "Date": "2025-07-01",
  "Time": "10:00"
}
```

Flex Message จะแสดง: ชื่อนักศึกษา, วันที่, เวลา (header สีเขียว 🟢)

---

#### 3. แจ้งเตือนอาจารย์ — นักศึกษายกเลิกการจอง (`/NotifyCancelled/CancelBooking`)

> ไฟล์: `notification/users/Advisor/NotifyQueueCancelled.py`

ส่งเมื่อนักศึกษายกเลิกนัดหมาย พร้อมแสดงเหตุผล

```json
POST /NotifyCancelled/CancelBooking
{
  "AdvisorId": "Uxxxxxxxxxxxxxxxx",
  "StudentName": "นายสมศักดิ์ ใจดี",
  "Date": "2025-07-01",
  "Time": "10:00",
  "CancelReason": "ติดสอบ"
}
```

Flex Message จะแสดง: ชื่อนักศึกษา, วันที่, เวลา, เหตุผลการยกเลิก (header สีแดง 🔴)

---

#### 4. แจ้งเตือนอาจารย์ — นักศึกษาเลื่อนคิว (`/NotifyQueueAdivsor/RecheduleAdvisor`)

> ไฟล์: `notification/users/Advisor/NotifyRecheduleAdvisor.py`

ส่งเมื่อนักศึกษาขอเลื่อนวันนัดหมาย

```json
POST /NotifyQueueAdivsor/RecheduleAdvisor
{
  "AdvisorId": "Uxxxxxxxxxxxxxxxx",
  "StudentName": "นายสมศักดิ์ ใจดี",
  "Date": "2025-07-05",
  "Time": "13:00",
  "Status": "Rescheduled"
}
```

Flex Message จะแสดง: ชื่อนักศึกษา, วันที่ใหม่, เวลาใหม่, สถานะ "เลื่อนคิว" (header สีน้ำเงิน 🔵)

---

#### 5. แจ้งเตือนนักศึกษา — อาจารย์ยืนยันหรือยกเลิก (`/NotifyQueueStudent/NotifyStudent`)

> ไฟล์: `notification/users/Student/NotifyQueueStudent.py`

ส่งเมื่ออาจารย์ตอบรับหรือปฏิเสธการจองของนักศึกษา

```json
POST /NotifyQueueStudent/NotifyStudent
{
  "userId": "Uxxxxxxxxxxxxxxxx",     // LINE userId ของนักศึกษา
  "StudentName": "นายสมศักดิ์ ใจดี",
  "AdvisorName": "ผศ.ดร.วิชาญ สอนดี",
  "Date": "2025-07-01",
  "Time": "10:00",
  "Status": "Approved"              // หรือ "Cancelled"
}
```

| Status | หัวข้อ | สีหัวการ์ด |
|--------|--------|-----------|
| `Approved` | การจองได้รับการยืนยัน ✅ | สีเขียว 🟢 |
| `Cancelled` | การจองถูกยกเลิก ❌ | สีแดง 🔴 |

Flex Message จะแสดง: ชื่อนักศึกษา, ชื่ออาจารย์, วันที่, เวลา, สถานะ

---

#### 6. แจ้งเตือนนักศึกษา — อาจารย์เลื่อนนัด (`/NotifyQueueStudent/RecheduleStudent`)

> ไฟล์: `notification/users/Student/NotifyReaheduleStudent.py`

ส่งเมื่ออาจารย์ต้องการเลื่อนวันนัดหมายกับนักศึกษา

```json
POST /NotifyQueueStudent/RecheduleStudent
{
  "UserId": "Uxxxxxxxxxxxxxxxx",
  "StudentName": "นายสมศักดิ์ ใจดี",
  "Date": "2025-07-10",
  "Time": "14:00",
  "Status": "Rescheduled"
}
```

Flex Message จะแสดง: ชื่อนักศึกษา, วันที่ใหม่, เวลาใหม่, สถานะ "เลื่อนคิว" (header สีน้ำเงิน 🔵)

---

### ลำดับขั้นตอนการทำงาน Notify (Sequence)

```
ระบบจอง (External) ──POST /NotifyQueueStudent/NotifyStudent──▶ FastAPI
                                                                    │
                                                         ตรวจสอบ Status
                                                       (Approved/Cancelled)
                                                                    │
                                                     สร้าง Flex Message payload
                                                                    │
                                                    POST https://api.line.me/v2/
                                                         bot/message/push
                                                                    │
                                                                    ▼
                                                         LINE ส่งการ์ดให้ผู้ใช้
```

### Event FollowEvent (ผู้ใช้ Add LINE OA)

เมื่อผู้ใช้ add LINE OA เป็น friend ระบบจะตรวจสอบว่า `userId` นั้นมีใน `UserProfile` DB หรือไม่:

- **พบข้อมูล** → ส่ง Flex Message ต้อนรับพร้อมชื่อ (สีเขียว)
- **ไม่พบข้อมูล** → แจ้งให้ไปสมัครในระบบจองก่อน (สีแดง)

---

## 📄 License

This project is open source.
