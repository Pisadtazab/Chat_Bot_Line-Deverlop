import os
import requests
from fastapi import APIRouter
from dotenv import load_dotenv

from pydantic import BaseModel


# ค้นหาไฟล์ .env จากโฟลเดอร์หลักอัตโนมัติ
base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../.."))
dotenv_path = os.path.join(base_dir, ".env")
load_dotenv(dotenv_path=dotenv_path)

ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")
LINE_PUSH_URL = "https://api.line.me/v2/bot/message/push"

class RecheduleData(BaseModel):
    AdvisorId   : str
    StudentName : str
    Date        : str
    Time        : str
    Status      : str

router = APIRouter()

def push_flex_rechedule_notification(user_id: str, title: str, student_name: str, status_text: str, date: str, time: str, color: str = "#445DFF") -> dict:
    if not ACCESS_TOKEN:
        print("[ERROR] ไม่พบ ACCESS_TOKEN")
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
                                    {"type": "text", "text": " สถานะ", "size": "sm", "color": "#000000", "flex": 2},
                                    {"type": "text", "text": status_text, "size": "sm", "color": "#445DFF", "weight": "bold", "wrap": True, "flex": 4}
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
        print(f"Flex Push Cancel to {user_id}: {response.status_code}")
        print(f" LINE response: {response.json()}") 
        return response.json()
    except Exception as e:
        print(f" ส่ง Flex Line ล้มเหลว: {e}")
        return {"status": 500, "message": str(e)}

@router.post("/RecheduleAdvisor")
def notify_Rechedule(data: RecheduleData):
     
    if data.Status == "Rescheduled":
        status_text = "้เลื่อนคิว"

    push_flex_rechedule_notification(
        user_id=data.AdvisorId,
        title="นักศึกษาเลื่อนคิว",
        student_name=data.StudentName,
        date=data.Date,
        time=data.Time,
        status_text=status_text,
        color="#445DFF" 
    )
    return {"status": "success"}
