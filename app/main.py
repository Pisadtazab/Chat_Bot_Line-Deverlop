import os
import uvicorn

from dotenv import load_dotenv

from fastapi import FastAPI, Request, HTTPException, Header
from fastapi.responses import PlainTextResponse

from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.webhooks import MessageEvent, TextMessageContent,FollowEvent

from linebot.v3.messaging import (
    ApiClient, 
    MessagingApi, 
    Configuration, 
    ReplyMessageRequest, 
    TextMessage, 
    # FlexMessage, 
    # Emoji,
)

from gridfs import GridFS
from pymongo import MongoClient
import requests
import json


from app.components.response_message import response_message #ติดต่อกับการสร้างเงื่อนไขข้อความ
# from app.chatbot import respond_to_message  #นำเข้าฟังก์ชั่น llm
from app.retriever import query_rag ,respone_message_LLM,id_image,send_image
from DB.database import collection,db

from fastapi import HTTPException
from fastapi.responses import StreamingResponse
# import io
from bson import ObjectId


from .routers import extractPDF
from .routers import deleteFile 
from .routers import getData
from .routers import views #หน้าตา ui

app = FastAPI()

# หน้าตา ui
app.include_router(views.router)

# เพิ่มการทำงานการดึงข้อมูลในไฟล์ pdf
app.include_router(extractPDF.router)

app.include_router(getData.router)
# เพิ่มการลบไฟล์ pdf
app.include_router(deleteFile.router)

# การเก็บ key
load_dotenv(override=True)



def get_secret_value(secret_name, default=None):
    """Try reading from a mounted file, fallback to env variable."""
    secret_path = f"/secrets/{secret_name}"
    if os.path.exists(secret_path):  # For Cloud Run with Secret Manager
        with open(secret_path, "r") as f:
            return f.read().strip()
    return os.getenv(secret_name, default)  # Fallback to env variable

get_access_token = get_secret_value('ACCESS_TOKEN')
get_channel_secret = get_secret_value('CHANNEL_SECRET')

configuration = Configuration(access_token=get_access_token)
handler = WebhookHandler(channel_secret=get_channel_secret)

# animation chat

def send_loading(chat_id, seconds=5):
    """ สำหรับอนิเมชั่นตอนกำลังตอบกลับ """
    url = "https://api.line.me/v2/bot/chat/loading/start"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {get_access_token}"
    }
    payload = {
        "chatId": chat_id,
        "loadingSeconds": seconds
    }

    response = requests.post(url, headers=headers, data=json.dumps(payload))
    print("Status:", response.status_code)
    print("Response:", response.text)
    

@app.post("/callback")
async def callback(request: Request, x_line_signature: str = Header(None,alias="X-Line-Signature")):
    body = await request.body()
    body_str = body.decode('utf-8')
    try:
        handler.handle(body_str, x_line_signature)
    except InvalidSignatureError:
        print("Invalid signature. Please check your channel access token/channel secret.")
        raise HTTPException(status_code=400, detail="Invalid signature.")

    return PlainTextResponse("OK", status_code=200)


@handler.add(FollowEvent)
def handle_follow(event: FollowEvent):
    '''ฟังก์ชั่น เมื่อผู้ใช้แอดเพื่อนจะส่งข้อความตอบกลับทันที'''
    user_id = event.source.user_id
    welcome_text = "สวัสดีครับ! ขอบคุณที่แอดเราเป็นเพื่อน 😊\n ฉันสามารถแนะนำอาจารย์ปรึกษาวิจัยให้กับคุณได้"
    # ส่ง reply
    with ApiClient(configuration) as api_client:
        messaging_api = MessagingApi(api_client)
        messaging_api.reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=welcome_text)]
            )
        )
    # TODO: เก็บ user_id ลง DB สำหรับ push ในอนาคต

@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event: MessageEvent): #เงื่อนไขจัดการกับข้อความ
    user_text = event.message.text
    
     # 1 ดึง userId สำหรับแสดงโหลด
    user_id = event.source.user_id

    # 2 ส่งวงกลมกำลังโหลดไปก่อน
    send_loading(user_id, seconds=5)
    
    
    # 3 ส่งข้อความนี้ไป query RAG หรือ DB และ  ดึงคำตอบจาก LLM (string)
    answer, current_pdf_name  = query_rag(user_text)

    
    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        
        # เก็บข้อความเป็น  list
        messages = []
        
        reply_message = response_message(event) # TextMessage, FlexMessage
        

        reply_message_AI =  respone_message_LLM(answer) # แปลง string เป็น TextMessage เพื่อส่งคำตอบ llm
        if reply_message_AI:
            messages.append(reply_message_AI)
        
        gridfs_ids = id_image(answer, collection,current_pdf_name)  # คืน list ของ ObjectId
        line_image = send_image(gridfs_ids)
        if line_image:
            messages.extend(line_image) # ใส่ค่าที่ละตัวไม่เอวเป็นก้อน ใช้แทน append

        if not reply_message:
            return None
        
        
        line_bot_api.reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                # messages=[reply_message,reply_message_AI, line_image]
                # messages=messages[:4]  # LINE จำกัด 3 บังคับให้ส่งได้แค่ 
                messages=messages
            )
        )
       

        print(event)
        

# เทส api
fs = GridFS(db)

# ค้นหารูปภาพ
@app.get("/image/{file_id}")
def get_image(file_id: str):
    try:
        oid = ObjectId(file_id) # มันอยู่ใน metadata ใช้ ObjectId ในการค้นหา
    except:
        raise HTTPException(status_code=400, detail="Invalid ObjectId")

    if not fs.exists(oid):
        raise HTTPException(status_code=404, detail="Image not found")

    grid_out = fs.get(oid)

    return StreamingResponse(
        grid_out,
        media_type=grid_out.content_type or "image/jpeg",
    )

 
if __name__ == "__main__":
    uvicorn.run("main:app", host="8000")