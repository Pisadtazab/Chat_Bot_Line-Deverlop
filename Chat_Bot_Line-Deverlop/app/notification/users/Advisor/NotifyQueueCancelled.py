from fastapi import APIRouter
from pydantic import BaseModel

from app.notification.helpers.flex import flex_row, send_flex_request_notifications


class CancelData(BaseModel):
    AdvisorId: str
    StudentId: str 
    StudentName: str
    ResearchTopic: str = ""
    Date: str
    Time: str
    CancelReason: str


router = APIRouter()


@router.post("/CancelBooking")
def notify_cancel(data: CancelData):
    reason = data.CancelReason.strip() or "ไม่ได้ระบุเหตุผล"
    details = [
        flex_row("👤 ชื่อ", data.StudentName, wrap=True),
        *([flex_row("📝 หัวข้อ", data.ResearchTopic, wrap=True)] if data.ResearchTopic else []),
        flex_row("📅 วันที่", data.Date),
        flex_row("⏰ เวลา", data.Time),
        {"type": "separator"},
        flex_row("💬 เหตุผล", reason, value_color="#FF4444", value_weight="bold", wrap=True),
    ]
    confirmation = [
        flex_row("👨‍🏫 อาจารย์", data.AdvisorName, wrap=True),
        *([flex_row("📝 หัวข้อ", data.ResearchTopic, wrap=True)] if data.ResearchTopic else []),
        flex_row("📅 วันที่", data.Date),
        flex_row("⏰ เวลา", data.Time),
        {"type": "separator"},
        flex_row("สถานะ", "ส่งคำขอยกเลิกสำเร็จ", value_color="#00B900", value_weight="bold"),
    ]
    delivery = send_flex_request_notifications(
        data.StudentId, data.AdvisorId, "ยกเลิกคิวสำเร็จ", "นักศึกษายกเลิกการจอง", "#FF4444", confirmation, details
    )
    return {"status": delivery["status"], "notification": delivery}
