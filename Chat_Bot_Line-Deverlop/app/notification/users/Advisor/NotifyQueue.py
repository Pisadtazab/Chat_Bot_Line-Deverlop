from fastapi import APIRouter
from pydantic import BaseModel

from app.notification.helpers.flex import flex_row, send_flex_request_notifications


class BookingData(BaseModel):
    AdvisorId: str 
    StudentId: str 
    StudentName: str | None = None
    AdvisorName:str | None = None
    ResearchTopic: str
    Date: str
    Time: str
    Status: str


router = APIRouter()

#
@router.post("/BookingStudent")
def notifyqueue(data: BookingData):
    confirmation = [
        flex_row("👤 ชื่อ", data.StudentName),
        # flex_row("👨‍🏫 อาจารย์", data.AdvisorName, wrap=True),
        flex_row("📝 หัวข้อ", data.ResearchTopic, wrap=True),
        flex_row("📅 วันที่", data.Date),
        flex_row("⏰ เวลา", data.Time),
        {"type": "separator"},
        flex_row("สถานะ", "รอการอนุมัติ", value_color="#FFB100", value_weight="bold", wrap=True),
    ]
    details = [
        flex_row("นักศึกษา", data.StudentName, wrap=True),
        # flex_row("อาจารย์", data.AdvisorName, wrap=True),
        flex_row("หัวข้อ", data.ResearchTopic, wrap=True),
        flex_row("วันที่", data.Date),
        flex_row("เวลา", data.Time),
        {"type": "separator"},
        flex_row("สถานะ", "รอการอนุมัติ", value_color="#FFB100", value_weight="bold", wrap=True),
    ]
    delivery = send_flex_request_notifications(
        data.StudentId, data.AdvisorId,
        "ส่งคำขอจองคิวสำเร็จ", "มีนักศึกษาจองคิว", "#FFB100",
        confirmation, details, sender_color="#00B900",
    )
    return {"status": delivery["status"], "notification": delivery}
