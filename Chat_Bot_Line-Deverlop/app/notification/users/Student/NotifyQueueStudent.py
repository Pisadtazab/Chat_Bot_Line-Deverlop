from fastapi import APIRouter
from pydantic import AliasChoices, BaseModel, Field

from app.notification.helpers.flex import flex_row, send_flex_request_notifications


class StudentNotifyData(BaseModel):
    StudentId: str 
    AdvisorId: str
    StudentName: str |None = None
    AdvisorName: str |None = None
    ResearchTopic: str 
    Date: str
    Time: str
    Status: str


router = APIRouter()


@router.post("/NotifyStudent")
def notify_student(data: StudentNotifyData):
    statuses = {
        "Approved": (
            "ยืนยันการจองคิวแล้ว ", "อนุมัติแล้ว", "#00B900",
            "อนุมัติแล้ว",
        ),
        "Cancelled": (
            "การจองคิวถูกยกเลิก", "ยกเลิกแล้ว", "#FF4444",
            "ยกเลิกแล้ว",
        ),
    }
    if data.Status not in statuses:
        return {"status": "skip", "message": "ไม่รู้จัก Status"}
    title, status_text, color, sender_result = statuses[data.Status]
    research_topic = data.ResearchTopic.strip() or "-"
    details = [
        flex_row("👨‍🏫 อาจารย์", data.AdvisorName),
        flex_row("📝 หัวข้อ", research_topic, wrap=True),
        flex_row("📅 วันที่", data.Date),
        flex_row("⏰ เวลา", data.Time),
        {"type": "separator"},
        flex_row("🔖 สถานะ", status_text, value_color=color, value_weight="bold"),
    ]
    confirmation = [
        flex_row("👨‍🏫 อาจารย์", data.AdvisorName),
        flex_row("📝 หัวข้อ", research_topic, wrap=True),
        flex_row("📅 วันที่", data.Date),
        flex_row("⏰ เวลา", data.Time),
        {"type": "separator"},
        flex_row("🔖 ผลการแจ้ง", sender_result, value_color="#00B900", value_weight="bold", wrap=True),
    ]
    sender_title = "ส่งผลอนุมัติการจองสำเร็จ" if data.Status == "Approved" else "ส่งคำขอยกเลิกสำเร็จ"
    delivery = send_flex_request_notifications(
        data.AdvisorId, data.StudentId, sender_title, title, color, confirmation, details,
    )
    message = (
        f"แจ้งเตือนนักศึกษา {data.StudentName} แล้ว"
        if delivery["status"] == "success"
        else f"ส่งแจ้งเตือนนักศึกษา {data.StudentName} ไม่สำเร็จ"
    )
    return {"status": delivery["status"], "message": message, "notification": delivery}
