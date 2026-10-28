from fastapi import APIRouter
from pydantic import BaseModel

from app.notification.DB.database_noti import collection as notify_collection
from app.notification.helpers.flex import send_flex_notifications

class Pendinglogin(BaseModel):
    Email: str
    level: str

router = APIRouter()

@router.post("/ApprovedUser/login")
def group_line_notification_url(payload: Pendinglogin):
    if payload.level == "mid":
        # จัดการ
    
        pass
    # admin_ids = [admin.get("userId") for admin in notify_collection.find({"Role": "Admin"})]
    # delivery = send_flex_notifications(
    #     admin_ids,
    #     "รออนุมัติการยืนยันเข้าสู่ระบบ",
    #     "#01579B",
    #     [
    #         {"type": "text", "text": "มีคำขอยืนยันเข้าสู่ระบบรอการอนุมัติ", "wrap": True},
    #         {"type": "text", "text": f"LINE ID: {payload.userId}", "size": "sm", "wrap": True},
    #         {"type": "text", "text": f"Role: {payload.Role}", "size": "sm", "wrap": True},
    #     ],
    # )
    # return {"status": delivery["status"], "notification": delivery}
