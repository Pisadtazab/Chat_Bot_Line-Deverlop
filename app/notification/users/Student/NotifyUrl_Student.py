from fastapi import APIRouter
from pydantic import BaseModel

from app.notification.helpers.flex import FOOTER, send_flex_notification


class LineNotification(BaseModel):
    line_user_id: str
    url: str


router = APIRouter()


@router.post("/send_url/notification")
async def receive_line_notification_url(payload: LineNotification):
    if not payload.url.startswith(("http://", "https://")):
        return {"status": "error", "detail": "url must start with http:// or https://"}
    title = "แจ้งเตือนนัดหมาย"
    result = send_flex_notification(payload.line_user_id, title, "#00B900", [
        {"type": "text", "text": title, "weight": "bold", "size": "lg", "wrap": True, "color": "#1a1a1a"},
        {"type": "separator"},
        {"type": "text", "text": "คุณมีลิงก์นัดหมายใหม่ กดปุ่มด้านล่างเพื่อเปิด", "size": "sm", "wrap": True, "color": "#555555"},
    ], header_text="🔔 การแจ้งเตือน", footer=[
        {"type": "button", "style": "primary", "height": "sm", "color": "#00B900", "action": {"type": "uri", "label": "เปิดลิงก์", "uri": payload.url}},
        FOOTER,
    ])
    return {"status": "ok", "line_response": result}
