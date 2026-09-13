from fastapi import APIRouter
from pydantic import BaseModel

from app.notification.helpers.flex import flex_row, send_flex_notification


class StudentNotifyData(BaseModel):
    userId: str
    StudentName: str
    AdvisorName: str
    Date: str
    Time: str
    Status: str


router = APIRouter()


@router.post("/NotifyStudent")
def notify_student(data: StudentNotifyData):
    statuses = {
        "Approved": ("การจองได้รับการยืนยัน ✅", "ยืนยันแล้ว", "#00B900"),
        "Cancelled": ("การจองถูกยกเลิก ❌", "ยกเลิกแล้ว", "#FF4444"),
    }
    if data.Status not in statuses:
        return {"status": "skip", "message": "ไม่รู้จัก Status"}
    title, status_text, color = statuses[data.Status]
    send_flex_notification(data.userId, title, color, [
        flex_row("👤 ชื่อ", data.StudentName),
        flex_row("👨‍🏫 อาจารย์", data.AdvisorName),
        flex_row("📅 วันที่", data.Date),
        flex_row("⏰ เวลา", data.Time),
        {"type": "separator"},
        flex_row("🔖 สถานะ", status_text, value_color=color, value_weight="bold"),
    ])
    return {"status": "success", "message": f"แจ้งเตือนนักศึกษา {data.StudentName} แล้ว"}
