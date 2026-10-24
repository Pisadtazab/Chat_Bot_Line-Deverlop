import asyncio
import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from app.notification.DB.database_noti import collection_BookingOnline
from app.notification.helpers.flex import flex_row, send_flex_notifications


TZ = ZoneInfo("Asia/Bangkok")
# shortcut: tracks failed pending bookings in memory; use persistent deduplication if this set grows large.
_logged_notification_failures: set[tuple[str, str]] = set()


def template_notify(booking: dict, marker: str, title: str, color: str, status: str) -> None:
    user_ids = list(dict.fromkeys(user_id for user_id in (booking.get("UserId"), booking.get("AdvisorId")) if user_id))
    delivered_field = f"{marker}UserIds"
    delivered_ids = set(booking.get(delivered_field, []))
    body = [
        flex_row("👤 นักศึกษา", booking.get("StudentName", "-"), wrap=True),
        flex_row("👨‍🏫 อาจารย์", booking.get("Advisor_Name", "-"), wrap=True),
        flex_row("📝 หัวข้อ", booking.get("ResearchTopic", "-"), wrap=True),
        flex_row("📅 วันที่", str(booking.get("Date", "-"))),
        flex_row("⏰ เวลา", str(booking.get("Time", "-"))),
        flex_row("🔖 สถานะ", status, value_color=color, value_weight="bold", wrap=True),
    ]

    for user_id in user_ids:
        if user_id in delivered_ids:
            continue
        # shortcut: a crash before MongoDB records success can resend; use LINE retry keys to close this gap.
        delivery = send_flex_notifications([user_id], title, color, body)
        if delivery.get("sent", 0):
            collection_BookingOnline.update_one(
                {"_id": booking["_id"]}, {"$addToSet": {delivered_field: user_id}}
            )
            delivered_ids.add(user_id)
        else:
            failure_key = (str(booking.get("_id")), marker)
            if failure_key not in _logged_notification_failures:
                logging.warning(
                    "Booking notification not delivered; booking_id=%s marker=%s user_id=%s result=%s",
                    booking.get("_id"), marker, user_id, delivery,
                )
                _logged_notification_failures.add(failure_key)

    if user_ids and all(user_id in delivered_ids for user_id in user_ids):
        _logged_notification_failures.discard((str(booking.get("_id")), marker))
        collection_BookingOnline.update_one({"_id": booking["_id"]}, {"$set": {marker: True}})


def trigger_booking_notifications() -> None:
    now = datetime.now(TZ)
    for booking in collection_BookingOnline.find({"Status": "Approved", "ReminderSent": {"$ne": True}}):
        try:
            start = datetime.strptime(
                f"{booking['Date']} {booking['Time'].split('-')[0].strip()}", "%Y-%m-%d %H:%M"
            ).replace(tzinfo=TZ)
        except (KeyError, ValueError, AttributeError):
            continue
        if start - timedelta(minutes=30) <= now < start:
            template_notify(booking, "ReminderSent", "อีก 30 นาทีถึงเวลาปรึกษา", "#445DFF", "เตรียมตัวเข้ารับคำปรึกษา")

    for booking in collection_BookingOnline.find({"Status": "Approved", "StartNotified": {"$ne": True}}):
        try:
            start = datetime.strptime(
                f"{booking['Date']} {booking['Time'].split('-')[0].strip()}", "%Y-%m-%d %H:%M"
            ).replace(tzinfo=TZ)
        except (KeyError, ValueError, AttributeError):
            continue
        if now >= start:
            template_notify(booking, "StartNotified", "ถึงเวลาให้คำปรึกษาแล้ว", "#00B900", "ถึงเวลาให้คำปรึกษา")

    for booking in collection_BookingOnline.find({"Status": "Completed", "CompletionNotified": {"$ne": True}}):
        template_notify(booking, "CompletionNotified", "การปรึกษาเสร็จสิ้น", "#00B900", "เสร็จสิ้น")


async def booking_notification_loop() -> None:
    while True:
        try:
            await asyncio.to_thread(trigger_booking_notifications)
        except Exception:
            logging.exception("Booking notification check failed")
        await asyncio.sleep(60)
