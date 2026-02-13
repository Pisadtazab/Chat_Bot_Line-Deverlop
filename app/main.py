import os
import uvicorn

from dotenv import load_dotenv

from fastapi import FastAPI, Request, HTTPException, Header,Depends
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


from app.response_message import response_message #ติดต่อกับการสร้างเงื่อนไขข้อความ
# from app.chatbot import respond_to_message  #นำเข้าฟังก์ชั่น llm
from app.retriever import query_rag ,respone_message_LLM,id_image,send_image

from fastapi import HTTPException
from gridfs import GridFS
from pymongo import MongoClient
from fastapi.responses import StreamingResponse
# import io
from bson import ObjectId


app = FastAPI()


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
""" สำหรับอนิเมชั่นตอนกำลังตอบกลับ """
def send_loading(chat_id, seconds=5):
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

'''ฟังก์ชั่น เมื่อผู้ใช้แอดเพื่อนจะส่งข้อความตอบกลับทันที'''
@handler.add(FollowEvent)
def handle_follow(event: FollowEvent):
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
        if reply_message:
            messages.append(reply_message)

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
        
        # เทส
        # gridfs_ids = id_image(answer, collection)  # คืน list ของ ObjectId
        # send_image(gridfs_ids,event)
    
        
        # line_bot_api.push_message(user_id, image_message)
        # print(f"Image {file_id} sent successfully!")
        


# @handler.add(MessageEvent, message=TextMessageContent)
# async def handle_user_message(event: MessageEvent):
#     user_msg = event.message.text
#     reply_msg = await respond_to_message(user_msg)

#     with ApiClient(configuration) as api_client:
#         messaging_api = MessagingApi(api_client)
#         messaging_api.reply_message(
#             ReplyMessageRequest(
#                 reply_token=event.reply_token,
#                 messages=[TextMessage(text=reply_msg)]
#             )
#         )


""" test api """

# MongoDB configuration MONGO_URI
mogo_uri = os.getenv("MONGO_URI")
client = MongoClient(mogo_uri )

# Name entity db
db = client["employee_research_db"]
collection = db["employees_profiles"]   



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
    
""" test หน้าตา ui ง่ายๆ """

from pydantic import BaseModel
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, JSONResponse

from DB.database import get_db, delete_pdf_from_db

# กำหนดโฟลเดอร์สำหรับเก็บไฟล์ HTML templates
templates = Jinja2Templates(directory="templates")

# Model สำหรับแสดงข้อมูลในฐานข้อมูล
class FileData(BaseModel):
    file_name: str
    file_id: str

@app.get("/", response_class=HTMLResponse)
async def home(request: Request, db=Depends(get_db)):
    """
    แสดงชื่อไฟล์ PDF ทั้งหมดจากฐานข้อมูล
    """
    try:
        files = db["employees_profiles"].find()  # ดึงข้อมูลไฟล์ทั้งหมดจาก MongoDB
        file_list = [file["metadata"]["source"] for file in files]  # ดึงเฉพาะชื่อไฟล์ (จาก metadata.source)
        
        return templates.TemplateResponse("index.html", {"request": request, "file_list": file_list})
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")

@app.get("/files", response_model=list[FileData])
async def get_files(db=Depends(get_db)):
    """
    ดึงข้อมูลไฟล์ทั้งหมดจาก MongoDB
    """
    try:
        files = db["employees_profiles"].find()
        file_list = [{"file_name": file["metadata"]["source"], "file_id": str(file["_id"])} for file in files]
        return file_list
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/delete_file", response_class=JSONResponse)
async def delete_file(pdf_name: str, db=Depends(get_db)):
    """
    ลบไฟล์จาก MongoDB โดยใช้ชื่อไฟล์
    """
    try:
        # ค้นหาไฟล์ที่มีชื่อ pdf_name
        file = db["employees_profiles"].find_one({"metadata.source": pdf_name})
        
        if not file:
            raise HTTPException(status_code=404, detail="File not found")

        # ลบไฟล์จากฐานข้อมูล
        delete_pdf_from_db(db, str(file["_id"]))
        return {"status": "success", "message": f"File '{pdf_name}' deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# @app.get("/")
# async def root():
#     return {"message": "Hello World"}



#sever กำลังรัน
@app.get("/")
async def root():
    return {"message": "LINE Chatbot is running!"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0")