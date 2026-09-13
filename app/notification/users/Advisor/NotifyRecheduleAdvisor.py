from fastapi import APIRouter
from pydantic import BaseModel

from app.notification.routers.reschedule import push_reschedule_notification

router = APIRouter()


class RecheduleData(BaseModel):
    AdvisorId: str
    StudentName: str
    Date: str
    Time: str
    Status: str


@router.post("/RecheduleAdvisor")
def notify_Rechedule(data: RecheduleData):
    if data.Status == "Rescheduled":
        push_reschedule_notification(data.AdvisorId, "นักศึกษาเลื่อนคิว", data.StudentName, "เลื่อนคิว", data.Date, data.Time)
    return {"status": "success"}
