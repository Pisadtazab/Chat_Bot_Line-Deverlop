import os
import requests
from fastapi import APIRouter
from dotenv import load_dotenv
from app.notification.DB.database_noti import collection_BookingOnline as notify_BookingOnline
from pydantic import BaseModel
from typing import Optional

# ค้นหาไฟล์ .env จากโฟลเดอร์หลักอัตโนมัติ
base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../.."))
dotenv_path = os.path.join(base_dir, ".env")
load_dotenv(dotenv_path=dotenv_path)

ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")
LINE_PUSH_URL = "https://api.line.me/v2/bot/message/push"

class BookingData(BaseModel):
    AdvisorId    : str
    StudentName  : str
    ResearchTopic: str
    Date         : str
    Time         : str
    Status       : str

router = APIRouter()


# ─────────────────────────────────────────────
# Push: Flex Message แจ้งเตือน (กำหนด default เป็นสีเหลืองส้มเตือน #FFB100)
# ─────────────────────────────────────────────
def push_flex_notification(user_id: str, title: str, student_name: str, research_topic: str, date: str, time: str, status_text: str, color: str = "#FFB100") -> dict:
    if not ACCESS_TOKEN:
        print(" [ERROR] ไม่พบ ACCESS_TOKEN กรุณาตรวจสอบไฟล์ .env")
        return {"status": 401, "message": "Missing ACCESS_TOKEN"}

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {ACCESS_TOKEN}",
    }
    
    payload = {
        "to": user_id,
        "messages": [
            {
                "type": "flex",
                "altText": title,
                "contents": {
                    "type": "bubble",
                    "size": "mega",
                    "header": {
                        "type": "box",
                        "layout": "vertical",
                        "contents": [
                            {
                                "type": "text",
                                "text": "🔔 " + title,
                                "color": "#ffffff",
                                "size": "md",
                                "weight": "bold"
                            }
                        ],
                        "backgroundColor": color,
                        "paddingAll": "15px"
                    },
                    "body": {
                        "type": "box",
                        "layout": "vertical",
                        "spacing": "md",
                        "contents": [
                            {
                                "type": "box",
                                "layout": "horizontal",
                                "contents": [
                                    {"type": "text", "text": "👤 ชื่อ", "size": "sm", "color": "#aaaaaa", "flex": 2},
                                    {"type": "text", "text": student_name, "size": "sm", "color": "#1a1a1a", "wrap": True, "flex": 4}
                                ]
                            },
                            # ✅ เพิ่ม ResearchTopic
                            {
                                "type": "box",
                                "layout": "horizontal",
                                "contents": [
                                    {"type": "text", "text": "📝 หัวข้อ", "size": "sm", "color": "#aaaaaa", "flex": 2},
                                    {"type": "text", "text": research_topic, "size": "sm", "color": "#1a1a1a", "wrap": True, "flex": 4}
                                ]
                            },
                            {
                                "type": "box",
                                "layout": "horizontal",
                                "contents": [
                                    {"type": "text", "text": "📅 วันที่", "size": "sm", "color": "#aaaaaa", "flex": 2},
                                    {"type": "text", "text": date, "size": "sm", "color": "#1a1a1a", "flex": 4}
                                ]
                            },
                            {
                                "type": "box",
                                "layout": "horizontal",
                                "contents": [
                                    {"type": "text", "text": "⏰ เวลา", "size": "sm", "color": "#aaaaaa", "flex": 2},
                                    {"type": "text", "text": time, "size": "sm", "color": "#1a1a1a", "flex": 4}
                                ]
                            },
                            {"type": "separator"},
                            {
                                "type": "box",
                                "layout": "horizontal",
                                "contents": [
                                    {"type": "text", "text": "🟡 สถานะ", "size": "sm", "color": "#aaaaaa", "flex": 2},
                                    {"type": "text", "text": status_text, "size": "sm", "color": color, "weight": "bold", "flex": 4}
                                ]
                            }
                        ],
                        "paddingAll": "20px"
                    },
                    "footer": {
                        "type": "box",
                        "layout": "vertical",
                        "contents": [
                            {
                                "type": "text",
                                "text": "ระบบแจ้งเตือนอัตโนมัติ",
                                "size": "xs",
                                "color": "#aaaaaa",
                                "align": "center"
                            }
                        ],
                        "paddingAll": "10px"
                    }
                }
            }
        ]
    }
    
    try:
        response = requests.post(LINE_PUSH_URL, headers=headers, json=payload)
        print(f"Flex Push to {user_id}: {response.status_code}")
        return response.json()
    except Exception as e:
        print(f" ส่ง Flex Line ล้มเหลว: {e}")
        return {"status": 500, "message": str(e)}


# แจ้งเตือนมีคนจอง
@router.post("/BookingStudent")
def notifyqueue(data: BookingData):
    push_flex_notification(
        user_id=data.AdvisorId,
        title="มีนักศึกษาขอจองคิว 📋",
        student_name=data.StudentName,
        research_topic=data.ResearchTopic, 
        date=data.Date,
        time=data.Time,
        status_text="รอการอนุมัติ",
        color="#FFB100"
    )
    return {"status": "success"}

# if __name__ == "__main__":
#     notifyqueue()