from app.notification.helpers.flex import flex_row, send_flex_notification


def push_reschedule_notification(user_id: str, title: str, student_name: str, status_text: str, date: str, time: str, color: str = "#445DFF") -> dict:
    rows = [("👤 ชื่อ", student_name), ("📅 วันที่", date), ("⏰ เวลา", time), (" สถานะ", status_text)]
    contents = []
    for index, (label, value) in enumerate(rows):
        if index == 3:
            contents.append({"type": "separator"})
        contents.append(flex_row(label, value, value_color="#445DFF" if index == 3 else "#1a1a1a", value_weight="bold" if index == 3 else "regular", wrap=True, label_color="#000000" if index == 3 else "#aaaaaa"))
    return send_flex_notification(user_id, title, color, contents)
