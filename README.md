# Chat_Bot_Line-Deverlop 🤖💬

LINE Chatbot ที่ใช้ RAG (Retrieval-Augmented Generation) พร้อม Typhoon AI สำหรับแนะนำอาจารย์ที่ปรึกษาวิจัย โดยใช้ FastAPI เป็น Backend, MongoDB เป็นฐานข้อมูล และ Cloudflare Tunnel สำหรับเปิด Webhook ของ LINE

---

## 📋 สารบัญ

- [คุณสมบัติ](#features)
- [สถาปัตยกรรมระบบ](#architecture)
- [โครงสร้างโปรเจกต์](#project-structure)
- [เทคโนโลยีที่ใช้](#tech-stack)
- [การติดตั้ง](#installation)
- [ตัวแปรสภาพแวดล้อม](#environment-variables)
- [API Endpoints](#api)

---

## ✨ คุณสมบัติ

- **LINE Messaging API** — รับ-ส่งข้อความผ่าน LINE OA
- **RAG Pipeline** — ดึงข้อมูลจากเอกสาร PDF แล้วส่งให้ AI ตอบ
- **Typhoon AI** — โมเดลภาษาไทยสำหรับสร้างคำตอบ
- **PDF Extraction** — แยกข้อความ + รูปภาพจาก PDF ด้วย PyMuPDF
- **Sentence Transformers** — สร้าง Embeddings สำหรับค้นหาเอกสาร
- **MongoDB + GridFS** — จัดเก็บข้อมูล, Embeddings และไฟล์รูปภาพ
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
```

---

## 📁 โครงสร้างโปรเจกต์

```
Chat_Bot_Line-Deverlop/
├── app/
│   ├── main.py                    # FastAPI entry point, /callback webhook, /image endpoint
│   ├── retriever.py               # RAG pipeline (query, embedding, image lookup)
│   ├── promrt_typhoon.py          # Typhoon AI prompt & completion
│   ├── components/
│   │   └── response_message.py   # สร้าง LINE Message objects
│   └── routers/
│       ├── views.py               # Serve หน้า UI (HTML)
│       ├── extractPDF.py          # อัปโหลดและแยก PDF → MongoDB
│       ├── getData.py             # ดึงรายชื่อ PDF / ข้อมูลจาก DB
│       └── deleteFile.py          # ลบไฟล์ PDF จาก DB
├── DB/
│   └── database.py                # MongoDB connection, collection
├── templates/
│   └── index.html                 # หน้า Admin UI (Nginx)
├── Dockerfile                     # Python 3.12 + FastAPI + Uvicorn
├── docker-compose.yml             # Services: Nginx + ngrok (dev)
├── requirements.txt               # Python dependencies
└── .env                           # ตัวแปรลับ (ไม่ commit)
```

---

## 🛠️ เทคโนโลยีที่ใช้

| หมวด | เทคโนโลยี |
|------|-----------|
| **Backend** | FastAPI, Uvicorn, Starlette |
| **AI / NLP** | Typhoon AI (OpenAI SDK), Sentence Transformers, PyThaiNLP |
| **Database** | MongoDB, GridFS (PyMongo) |
| **PDF** | PyMuPDF (fitz), FixThaiPDF |
| **LINE** | line-bot-sdk v3 |
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
TYPHOON_API_KEY=your_typhoon_api_key
MONGODB_URI=your_mongodb_connection_string

```

**3. รัน FastAPI**

```bash
# รันตรงๆ
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# หรือ Docker
docker-compose up -d
```

---

## 🔑 ตัวแปรสภาพแวดล้อม

| ตัวแปร | คำอธิบาย |
|--------|----------|
| `ACCESS_TOKEN` | LINE Channel Access Token |
| `CHANNEL_SECRET` | LINE Channel Secret |
| `TYPHOON_API_KEY` | Typhoon AI API Key |
| `MONGODB_URI` | MongoDB connection string |
| `NGROK_TOKEN` | ngrok authtoken (dev only) |

> ตัวแปรสามารถวางไว้ใน `.env` หรือ Mount ผ่าน Secret Manager (Cloud Run) ที่ `/secrets/<name>`

---

## 📡 API Endpoints

| Method | Path | คำอธิบาย |
|--------|------|----------|
| `POST` | `/callback` | LINE Webhook — รับ event จาก LINE Platform |
| `GET` | `/image/{file_id}` | ดึงรูปภาพจาก GridFS |
| `POST` | `/extract-pdf` | อัปโหลด PDF และแยกข้อมูลเข้า MongoDB |
| `GET` | `/get-data` | ดึงรายชื่อ PDF / ข้อมูลจาก DB |
| `DELETE` | `/delete-file` | ลบไฟล์ PDF จาก DB |
| `GET` | `/` | Admin UI (HTML) |

---

## 💬 การทำงานของ Chatbot

1. ผู้ใช้ส่งข้อความใน LINE
2. LINE ส่ง Webhook มาที่ `POST /callback` ผ่าน Cloudflare Tunnel
3. ระบบแสดง Loading animation ให้ผู้ใช้รอ
4. `retriever.py` ค้นหาข้อมูลที่เกี่ยวข้องจาก MongoDB ด้วย Sentence Transformers
5. `promrt_typhoon.py` ส่ง context + คำถามไปให้ Typhoon AI สร้างคำตอบ
6. ตอบกลับผู้ใช้ผ่าน LINE Reply Message API (ข้อความ + รูปภาพ)

---

## 📄 License

This project is open source.




# Chat_Bot_Line-Deverlop 🤖💬

LINE Chatbot ที่ใช้ RAG (Retrieval-Augmented Generation) พร้อม Typhoon AI สำหรับแนะนำอาจารย์ที่ปรึกษาวิจัย โดยใช้ FastAPI เป็น Backend, MongoDB เป็นฐานข้อมูล และ Cloudflare Tunnel สำหรับเปิด Webhook ของ LINE

---

## 📋 สารบัญ

- [คุณสมบัติ](#features)
- [สถาปัตยกรรมระบบ](#architecture)
- [โครงสร้างโปรเจกต์](#project-structure)
- [เทคโนโลยีที่ใช้](#tech-stack)
- [การติดตั้ง](#installation)
- [ตัวแปรสภาพแวดล้อม](#environment-variables)
- [API Endpoints](#api)

---

## ✨ คุณสมบัติ

- **LINE Messaging API** — รับ-ส่งข้อความผ่าน LINE OA
- **RAG Pipeline** — ดึงข้อมูลจากเอกสาร PDF แล้วส่งให้ AI ตอบ
- **Typhoon AI** — โมเดลภาษาไทยสำหรับสร้างคำตอบ
- **PDF Extraction** — แยกข้อความ + รูปภาพจาก PDF ด้วย PyMuPDF
- **Sentence Transformers** — สร้าง Embeddings สำหรับค้นหาเอกสาร
- **MongoDB + GridFS** — จัดเก็บข้อมูล, Embeddings และไฟล์รูปภาพ
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
```

---

## 📁 โครงสร้างโปรเจกต์

```
Chat_Bot_Line-Deverlop/
├── app/
│   ├── main.py                    # FastAPI entry point, /callback webhook, /image endpoint
│   ├── retriever.py               # RAG pipeline (query, embedding, image lookup)
│   ├── promrt_typhoon.py          # Typhoon AI prompt & completion
│   ├── components/
│   │   └── response_message.py   # สร้าง LINE Message objects
│   └── routers/
│       ├── views.py               # Serve หน้า UI (HTML)
│       ├── extractPDF.py          # อัปโหลดและแยก PDF → MongoDB
│       ├── getData.py             # ดึงรายชื่อ PDF / ข้อมูลจาก DB
│       └── deleteFile.py          # ลบไฟล์ PDF จาก DB
├── DB/
│   └── database.py                # MongoDB connection, collection
├── templates/
│   └── index.html                 # หน้า Admin UI (Nginx)
├── Dockerfile                     # Python 3.12 + FastAPI + Uvicorn
├── docker-compose.yml             # Services: Nginx + ngrok (dev)
├── requirements.txt               # Python dependencies
└── .env                           # ตัวแปรลับ (ไม่ commit)
```

---

## 🛠️ เทคโนโลยีที่ใช้

| หมวด | เทคโนโลยี |
|------|-----------|
| **Backend** | FastAPI, Uvicorn, Starlette |
| **AI / NLP** | Typhoon AI (OpenAI SDK), Sentence Transformers, PyThaiNLP |
| **Database** | MongoDB, GridFS (PyMongo) |
| **PDF** | PyMuPDF (fitz), FixThaiPDF |
| **LINE** | line-bot-sdk v3 |
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
TYPHOON_API_KEY=your_typhoon_api_key
MONGODB_URI=your_mongodb_connection_string

```

**3. รัน FastAPI**

```bash
# รันตรงๆ
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# หรือ Docker
docker-compose up -d
```

---

## 🔑 ตัวแปรสภาพแวดล้อม

| ตัวแปร | คำอธิบาย |
|--------|----------|
| `ACCESS_TOKEN` | LINE Channel Access Token |
| `CHANNEL_SECRET` | LINE Channel Secret |
| `TYPHOON_API_KEY` | Typhoon AI API Key |
| `MONGODB_URI` | MongoDB connection string |
| `NGROK_TOKEN` | ngrok authtoken (dev only) |

> ตัวแปรสามารถวางไว้ใน `.env` หรือ Mount ผ่าน Secret Manager (Cloud Run) ที่ `/secrets/<name>`

---

## 📡 API Endpoints

| Method | Path | คำอธิบาย |
|--------|------|----------|
| `POST` | `/callback` | LINE Webhook — รับ event จาก LINE Platform |
| `GET` | `/image/{file_id}` | ดึงรูปภาพจาก GridFS |
| `POST` | `/extract-pdf` | อัปโหลด PDF และแยกข้อมูลเข้า MongoDB |
| `GET` | `/get-data` | ดึงรายชื่อ PDF / ข้อมูลจาก DB |
| `DELETE` | `/delete-file` | ลบไฟล์ PDF จาก DB |
| `GET` | `/` | Admin UI (HTML) |

---

## 💬 การทำงานของ Chatbot

1. ผู้ใช้ส่งข้อความใน LINE
2. LINE ส่ง Webhook มาที่ `POST /callback` ผ่าน Cloudflare Tunnel
3. ระบบแสดง Loading animation ให้ผู้ใช้รอ
4. `retriever.py` ค้นหาข้อมูลที่เกี่ยวข้องจาก MongoDB ด้วย Sentence Transformers
5. `promrt_typhoon.py` ส่ง context + คำถามไปให้ Typhoon AI สร้างคำตอบ
6. ตอบกลับผู้ใช้ผ่าน LINE Reply Message API (ข้อความ + รูปภาพ)

---

## 📄 License

This project is open source.
