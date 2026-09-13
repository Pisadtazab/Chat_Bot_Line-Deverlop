from fastapi import APIRouter
from pydantic import BaseModel

from app.notification.helpers.flex import flex_row, send_flex_notification


class CancelData(BaseModel):
    AdvisorId: str
    StudentName: str
    Date: str
    Time: str
    CancelReason: str


router = APIRouter()


@router.post("/CancelBooking")
def notify_cancel(data: CancelData):
    reason = data.CancelReason.strip() or "ไม่ได้ระบุเหตุผล"
    send_flex_notification(data.AdvisorId, "นักศึกษายกเลิกการจอง ", "#FF4444", [
        flex_row("👤 ชื่อ", data.StudentName, wrap=True),
        flex_row("📅 วันที่", data.Date),
        flex_row("⏰ เวลา", data.Time),
        {"type": "separator"},
        flex_row("💬 เหตุผล", reason, value_color="#FF4444", value_weight="bold", wrap=True),
    ])
    return {"status": "success"}
