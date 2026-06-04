import os
import requests
from fastapi import APIRouter
from dotenv import load_dotenv
from app.notification.DB.database_noti import collection_BookingOnline as notify_BookingOnline
from pydantic import BaseModel
from typing import Optional

# ค้นหาไฟล์ .env จากโฟลเดอร์หลักอัตโนมัติ
base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../.."))
dotenv_path = os.path.join(base_dir, ".env")
load_dotenv(dotenv_path=dotenv_path)

ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")
LINE_PUSH_URL = "https://api.line.me/v2/bot/message/push"

class BookingData(BaseModel):
    userId: str
    StudentName: str
    Date: str
    Time: str
    Status: str

router = APIRouter()


# ─────────────────────────────────────────────
# Push: Flex Message แจ้งเตือน (กำหนด default เป็นสีเหลืองส้มเตือน #FFB100)
# ─────────────────────────────────────────────
def push_flex_notification(user_id: str, title: str, student_name: str, date: str, time: str, status_text: str, color: str = "#FFB100") -> dict:
    if not ACCESS_TOKEN:
        print("⚠️ [ERROR] ไม่พบ ACCESS_TOKEN กรุณาตรวจสอบไฟล์ .env")
        return {"status": 401, "message": "Missing ACCESS_TOKEN"}

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {ACCESS_TOKEN}",
    }
    
    payload = {
        "to": user_id,
        "messages": [
            {
                "type": "flex",
                "altText": title,
                "contents": {
                    "type": "bubble",
                    "size": "mega",
                    "header": {
                        "type": "box",
                        "layout": "vertical",
                        "contents": [
                            {
                                "type": "text",
                                "text": "🔔 " + title,
                                "color": "#ffffff",
                                "size": "md",
                                "weight": "bold"
                            }
                        ],
                        "backgroundColor": color,
                        "paddingAll": "15px"
                    },
                    "body": {
                        "type": "box",
                        "layout": "vertical",
                        "spacing": "md",
                        "contents": [
                            {
                                "type": "box",
                                "layout": "horizontal",
                                "contents": [
                                    {"type": "text", "text": "👤 ชื่อ", "size": "sm", "color": "#aaaaaa", "flex": 2},
                                    {"type": "text", "text": student_name, "size": "sm", "color": "#1a1a1a", "wrap": True, "flex": 4}
                                ]
                            },
                            {
                                "type": "box",
                                "layout": "horizontal",
                                "contents": [
                                    {"type": "text", "text": "📅 วันที่", "size": "sm", "color": "#aaaaaa", "flex": 2},
                                    {"type": "text", "text": date, "size": "sm", "color": "#1a1a1a", "flex": 4}
                                ]
                            },
                            {
                                "type": "box",
                                "layout": "horizontal",
                                "contents": [
                                    {"type": "text", "text": "⏰ เวลา", "size": "sm", "color": "#aaaaaa", "flex": 2},
                                    {"type": "text", "text": time, "size": "sm", "color": "#1a1a1a", "flex": 4}
                                ]
                            },
                            {"type": "separator"},
                            {
                                "type": "box",
                                "layout": "horizontal",
                                "contents": [
                                    {"type": "text", "text": "🟢 สถานะ", "size": "sm", "color": "#aaaaaa", "flex": 2},
                                    {"type": "text", "text": status_text, "size": "sm", "color": color, "weight": "bold", "flex": 4}
                                ]
                            }
                        ],
                        "paddingAll": "20px"
                    },
                    "footer": {
                        "type": "box",
                        "layout": "vertical",
                        "contents": [
                            {
                                "type": "text",
                                "text": "ระบบแจ้งเตือนอัตโนมัติ",
                                "size": "xs",
                                "color": "#aaaaaa",
                                "align": "center"
                            }
                        ],
                        "paddingAll": "10px"
                    }
                }
            }
        ]
    }
    
    try:
        response = requests.post(LINE_PUSH_URL, headers=headers, json=payload)
        print(f"Flex Push to {user_id}: {response.status_code}")
        return response.json()
    except Exception as e:
        print(f"❌ ส่ง Flex Line ล้มเหลว: {e}")
        return {"status": 500, "message": str(e)}


@router.get("/BookingStudent")
def notifyqueue():
    """ดึงข้อมูล Booking ทั้งหมดจาก DB แล้วส่ง LINE แจ้งเตือนแบบ Flex Message"""
    print(" เริ่มทำงานฟังก์ชัน notifyqueue()...")
    
    # ดึงข้อมูลทั้งหมดจาก MongoDB แปลงเป็น list เพื่อความชัวร์
    bookings_list = list(notify_BookingOnline.find({}))
    print(f"📊 จำนวนข้อมูลในฐานข้อมูล: {len(bookings_list)} รายการ")

    results = []
    for booking in bookings_list:
        user_id = booking.get("UserId")
        student_name = booking.get("StudentName", "ไม่ได้ระบุชื่อ")
        date = booking.get("Date", "-")
        time = booking.get("Time", "-")
        
        # จัดการแปลงสถานะ
        booking_status = booking.get("Status")
        if booking_status == "Pending":
            booking_status_th = "รอการอนุมัติ"
            card_color = "#FFB100"  # 🟡 สีเหลืองเข้มส้ม สำหรับรอการอนุมัติ
        elif booking_status == "Approved":
            booking_status_th = "อนุมัติแล้ว"
            card_color = "#00B900"  # 🟢 สีเขียว สำหรับอนุมัติแล้ว
        else:
            booking_status_th = booking_status if booking_status else "ไม่ระบุสถานะ"
            card_color = "#555555"  # ⚪ สีเทา สำหรับกรณีอื่นๆ

        if not user_id:
            print(f"⚠️ ข้ามรายการของ {student_name} เนื่องจากไม่มี userId")
            continue

        # เรียกใช้ฟังก์ชันส่งแบบ Flex Message ตามสีกรณีต่างๆ 
        # (หากเป็น Pending จะได้หัวสีเหลือง และตัวหนังสือสถานะสีเหลือง)
        res_data = push_flex_notification(
            user_id=user_id,
            title="แจ้งเตือนการจองคิว",
            student_name=student_name,
            date=date,
            time=time,
            status_text=booking_status_th,
            color=card_color
        )

        results.append({
            "UserId": user_id,
            "StudentName": student_name,
            "Date": date,
            "Time": time,
            "Status": booking_status_th,
            "line_response": res_data
        })
        
    print("\nทำงานเสร็จสิ้น")
    return {"sent": len(results), "details": results}


if __name__ == "__main__":
    notifyqueue()