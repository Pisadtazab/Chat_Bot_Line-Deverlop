import os

import requests
from dotenv import load_dotenv


LINE_PUSH_URL = "https://api.line.me/v2/bot/message/push"
FOOTER = {"type": "text", "text": "ระบบแจ้งเตือนอัตโนมัติ", "size": "xs", "color": "#aaaaaa", "align": "center"}

load_dotenv()


def flex_row(label: str, value: str, *, value_color: str = "#1a1a1a", value_weight: str = "regular", wrap: bool = False, label_color: str = "#aaaaaa") -> dict:
    return {"type": "box", "layout": "horizontal", "contents": [
        {"type": "text", "text": label, "size": "sm", "color": label_color, "flex": 2},
        {"type": "text", "text": value, "size": "sm", "color": value_color, "weight": value_weight, "wrap": wrap, "flex": 4},
    ]}


def send_flex_notification(user_id: str, title: str, color: str, body: list[dict], *, header_text: str | None = None, footer: list[dict] | None = None) -> dict:
    token = os.getenv("ACCESS_TOKEN")
    if not token:
        return {"status": 401, "message": "Missing ACCESS_TOKEN"}
    payload = {"to": user_id, "messages": [{"type": "flex", "altText": title, "contents": {
        "type": "bubble", "size": "mega",
        "header": {"type": "box", "layout": "vertical", "contents": [{"type": "text", "text": header_text or f"🔔 {title}", "color": "#ffffff", "size": "md", "weight": "bold"}], "backgroundColor": color, "paddingAll": "15px"},
        "body": {"type": "box", "layout": "vertical", "spacing": "md", "contents": body, "paddingAll": "20px"},
        "footer": {"type": "box", "layout": "vertical", "contents": footer or [FOOTER], "paddingAll": "10px"},
    } }]}
    try:
        response = requests.post(LINE_PUSH_URL, headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"}, json=payload, timeout=5.0)
        print(f"Flex Push to {user_id}: {response.status_code}")
        return response.json()
    except requests.RequestException as exc:
        return {"status": 500, "message": str(exc)}
