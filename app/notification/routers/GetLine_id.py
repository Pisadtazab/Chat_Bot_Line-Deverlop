from fastapi import APIRouter
from pydantic import BaseModel
from app.notification.DB.database_noti import collection as notify_collection
from .line_notify import  push_flex_notification

class notifyLogin(BaseModel):
    userId: str
    Firstname:str

router = APIRouter()

@router.post("/UserLine_id")
def sendNotify_Login(data: notifyLogin):
    
    #  เช็ค Status ปัจจุบันใน collection
    existing_user = notify_collection.find_one({"userId": data.userId})
    
    if existing_user and existing_user.get("Status") == "Approved":
        #  ยังไม่ Approved → ส่งแจ้งเตือน
        print(f" กำลัง push ไปที่ userId: {data.userId}")
        push_flex_notification(
            user_id=data.userId,
            title=f"สวัสดีคุณ {data.Firstname}! 👋",
            message="ระบบแจ้งเตือนพร้อมแล้ว \nยินดีต้อนรับเข้าสู่ระบบ😊",
            color="#00B900"
        )
        return {"status": "success"}

    
    print(" Approved แล้ว skip")
    return {"status": "skip"}
    
# if __name__ == "__main__":
#     sendNotify_Login()