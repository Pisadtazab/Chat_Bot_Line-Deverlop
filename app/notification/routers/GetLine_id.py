from fastapi import APIRouter
from pydantic import BaseModel
from app.notification.DB.database_noti import collection as notify_collection
from .line_notify import  push_flex_notification

class notifyLogin(BaseModel):
    userId: str
    Firstname:str

router = APIRouter()


@router.post("/UserLine_id")  # ✅ เปลี่ยนจาก GET เป็น POST
def sendNotify_Login(data: notifyLogin):
    push_flex_notification(
        user_id=data.userId,
        title=f"สวัสดีคุณ {data.Firstname}! 👋",
        message="ระบบแจ้งเตือนพร้อมแล้ว \nยินดีต้อนรับเข้าสู่ระบบ😊",
        color="#00B900"
    )
    return {"status": "success", "message": f"ส่งแจ้งเตือนถึง {data.Firstname} แล้ว"}



# if __name__ == "__main__":
#     sendNotify_Login()