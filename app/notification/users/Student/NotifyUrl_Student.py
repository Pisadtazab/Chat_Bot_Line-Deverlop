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

class LineNotification(BaseModel):
    line_user_id: str
    url: str

router = APIRouter()

@router.post("/send_url/notification")
async def receive_line_notification_url(payload: LineNotification):
    print(payload.line_user_id, payload.url)
    # เรียก LINE Messaging API ส่ง Flex Message แจ้งเตือนไปยัง user คนนี้
    result = push_flex_notification_url(
        line_user_id=payload.line_user_id,
        title="แจ้งเตือนนัดหมาย",
        message="คุณมีลิงก์นัดหมายใหม่ กดปุ่มด้านล่างเพื่อเปิด",
        url=payload.url,
    )
    return {"status": "ok", "line_response": result}


# ─────────────────────────────────────────────
# ส่ง Flex Message แจ้งเตือน
# ─────────────────────────────────────────────
def push_flex_notification_url(
    line_user_id: str,
    title: str,
    message: str,
    url: str,
    color: str = "#00B900",
) -> dict:
    if not ACCESS_TOKEN:
        print("[WARN] ACCESS_TOKEN ไม่ถูกตั้งค่าใน .env")
        return {"status": "error", "detail": "ACCESS_TOKEN missing"}

    if not url.startswith(("http://", "https://")):
        print(f"[WARN] url ไม่ถูกต้อง (ต้องขึ้นต้นด้วย http/https): {url}")
        return {"status": "error", "detail": "url must start with http:// or https://"}

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {ACCESS_TOKEN}",
    }
    payload = {
        "to": line_user_id,
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
                                "text": "🔔 การแจ้งเตือน",
                                "color": "#ffffff",
                                "size": "sm",
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
                                "type": "text",
                                "text": title,
                                "weight": "bold",
                                "size": "lg",
                                "wrap": True,
                                "color": "#1a1a1a"
                            },
                            {"type": "separator"},
                            {
                                "type": "text",
                                "text": message,
                                "size": "sm",
                                "wrap": True,
                                "color": "#555555"
                            }
                        ],
                        "paddingAll": "20px"
                    },
                    "footer": {
                        "type": "box",
                        "layout": "vertical",
                        "spacing": "sm",
                        "contents": [
                            {
                                "type": "button",
                                "style": "primary",
                                "height": "sm",
                                "color": color,
                                "action": {
                                    "type": "uri",
                                    "label": "เปิดลิงก์",
                                    "uri": url
                                }
                            },
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
        response = requests.post(LINE_PUSH_URL, headers=headers, json=payload, timeout=5.0)
        print(f"Flex Push to {line_user_id}: {response.status_code}")
        return response.json()
    except requests.RequestException as exc:
        print(f"[WARN] ส่ง LINE push ไม่สำเร็จ: {exc}")
        return {"status": "error", "detail": str(exc)}