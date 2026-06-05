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

router = APIRouter()

class StudentNotifyData(BaseModel):
    userId: str       # userId ของนักศึกษา
    StudentName: str
    AdvisorName: str
    Date: str
    Time: str
    Status: str       # "Approved" หรือ "Cancelled"

def push_flex_notification(user_id: str, title: str, student_name: str, advisor_name: str, date: str, time: str, status_text: str, color: str) -> dict:
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
                                    {"type": "text", "text": student_name, "size": "sm", "color": "#1a1a1a", "flex": 4}
                                ]
                            },
                            {
                                "type": "box",
                                "layout": "horizontal",
                                "contents": [
                                    {"type": "text", "text": "👨‍🏫 อาจารย์", "size": "sm", "color": "#aaaaaa", "flex": 2},
                                    {"type": "text", "text": advisor_name, "size": "sm", "color": "#1a1a1a", "flex": 4}
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
                                    {"type": "text", "text": "🔖 สถานะ", "size": "sm", "color": "#aaaaaa", "flex": 2},
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
        print(f"❌ ส่ง Flex Line ล้มเหลว: {e}")
        return {"status": 500, "message": str(e)}


@router.post("/NotifyStudent")
def notify_student(data: StudentNotifyData):

    if data.Status == "Approved":
        title = "การจองได้รับการยืนยัน ✅"
        status_text = "ยืนยันแล้ว"
        color = "#00B900"  # 🟢 สีเขียว

    elif data.Status == "Cancelled":
        title = "การจองถูกยกเลิก ❌"
        status_text = "ยกเลิกแล้ว"
        color = "#FF4444"  # 🔴 สีแดง

    else:
        return {"status": "skip", "message": "ไม่รู้จัก Status"}

    push_flex_notification(
        user_id=data.userId,
        title=title,
        student_name=data.StudentName,
        advisor_name=data.AdvisorName,
        date=data.Date,
        time=data.Time,
        status_text=status_text,
        color=color
    )

    return {"status": "success", "message": f"แจ้งเตือนนักศึกษา {data.StudentName} แล้ว"}