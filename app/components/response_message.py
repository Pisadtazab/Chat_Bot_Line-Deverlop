from linebot.v3.messaging import TextMessage, Emoji

def response_message(event):
    request_message = event.message.text.strip().lower()

    # HELLO
    if request_message == "hello":
        emojis = [
            Emoji(index=0, productId="5ac1bfd5040ab15980c9b435", emojiId="002"),
        ]
        text_response = "$ Hello/สวัสดีครับ from PythonDevBot $"
        return TextMessage(text=text_response, emojis=emojis)

    # HI
    elif request_message == "hi":
        emojis = [
            Emoji(index=0, productId="5ac1bfd5040ab15980c9b435", emojiId="002"),
        ]
        text_response = "$ Hiiiiiii/สวัสดีครับ from PythonDevBot "
        return TextMessage(text=text_response, emojis=emojis)

    # Default response
    else:
        return TextMessage(text="ขออภัยผู้ใช้งาน ระบบไม่สามารถตอบคำถามเดิมได้ เนื่องจากไม่ได้บันทึกการถาม–ตอบก่อนหน้านี้ กรุณาพิมพ์คำถามใหม่อีกครั้ง")