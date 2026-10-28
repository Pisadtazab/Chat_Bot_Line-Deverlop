from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional

from app.notification.helpers.flex import FOOTER, send_flex_notification


class LineNotification(BaseModel):
    line_user_id: Optional[list[str]]
    url: str
    AdvisorName:str
  


router = APIRouter()


@router.post("/send_url/notification")
def receive_line_notification_url(payload: LineNotification):
    if not payload.url.startswith(("http://", "https://")):
        return {"status": "error", "detail": "url must start with http:// or https://"}
    title = "แจ้งเตือนนัดหมาย"
    
    results = []
    for sent in payload.line_user_id or []:
        result = send_flex_notification(sent, title, "#01579B", [
            {"type": "text", "text": title, "weight": "bold", "size": "lg", "wrap": True, "color": "#1a1a1a"},
            {"type": "separator"},
            {"type": "text", "text": f"คุณมีลิงก์นัดหมายกลุ่มกับ {payload.AdvisorName} กดปุ่มด้านล่างเพื่อเปิด", "size": "sm", "wrap": True, "color": "#555555"},
        ], header_text=" 👥 การแจ้งเตือนกลุ่ม", footer=[
            {"type": "button", "style": "primary", "height": "sm", "color": "#00B900", "action": {"type": "uri", "label": "เปิดลิงก์", "uri": payload.url}},
            FOOTER,
        ])
        results.append({"line_user_id": sent, **result})

    sent_count = sum(result.get("status") == "success" for result in results)
    failed_count = len(results) - sent_count
    status = "success" if not failed_count and results else "partial" if sent_count else "error" if failed_count else "skipped"
    return {"status": status, "sent": sent_count, "failed": failed_count, "results": results}
