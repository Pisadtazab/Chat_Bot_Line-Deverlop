from fastapi import APIRouter
from pydantic import BaseModel

from app.notification.helpers.flex import flex_row, send_flex_notification


class BookingData(BaseModel):
    AdvisorId: str
    StudentName: str
    ResearchTopic: str
    Date: str
    Time: str
    Status: str


router = APIRouter()


@router.post("/BookingStudent")
def notifyqueue(data: BookingData):
    send_flex_notification(data.AdvisorId, "มีนักศึกษาขอจองคิว 📋", "#FFB100", [
        flex_row("👤 ชื่อ", data.StudentName, wrap=True),
        flex_row("📝 หัวข้อ", data.ResearchTopic, wrap=True),
        flex_row("📅 วันที่", data.Date),
        flex_row("⏰ เวลา", data.Time),
        {"type": "separator"},
        flex_row("🟡 สถานะ", "รอการอนุมัติ", value_color="#FFB100", value_weight="bold"),
    ])
    return {"status": "success"}
