from fastapi import APIRouter
from pydantic import BaseModel

from app.notification.helpers.flex import send_flex_notification


class ApprovedLogin(BaseModel):
    userId: str


router = APIRouter()


@router.post("/ApprovedUser/student")
def notify_approved_login(payload: ApprovedLogin):
    notification = send_flex_notification(
        payload.userId,
        "อนุมัติการยืนยันเข้าสู่ระบบแล้ว",
        "#00B900",
        [{"type": "text", "text": "คุณได้รับการอนุมัติเข้าสู่ระบบแล้ว", "wrap": True}],
    )
    return {"status": notification.get("status", "error"), "notification": notification}
