import asyncio
import logging
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
    PushMessageRequest,
    TextMessage,
    # ReplyMessageRequest, 
    # FlexMessage, 
    # Emoji,
)
from fastapi.middleware.cors import CORSMiddleware
import requests


from app.response_message import response_message #ติดต่อกับการสร้างเงื่อนไขข้อความ
# from app.chatbot import respond_to_message  #นำเข้าฟังก์ชั่น llm
from app.retriever import query_rag ,respone_message_LLM,id_image,send_image
from app.DB.database import collection,db


from fastapi import HTTPException


# ของเว็ปไซต์
from .routers import extractPDF
from .routers import deleteFile 
from .routers import getData
from .routers import views #หน้าตา ui


from app.notification.routers.line_notify import push_flex_notification
from app.notification.DB.database_noti import collection as notify_collection

from app.notification.users.Advisor.NotifyQueue import router as noti_router 
from app.notification.users.Advisor.NotifyQueueCancelled import  router as noti_router_cancelled
from app.notification.users.Advisor.NotifyRecheduleAdvisor import router as noti_router_rechedule_Ad

from app.notification.users.Student.NotifyQueueStudent import router as noti_router_St
from app.notification.users.Student.NotifyReaheduleStudent import router as noti_router_rechedule_St
from app.notification.users.Student.NotifyUrl_Student import router as noti_router_chatlink_St

from app.notification.routers.GetLine_id  import router as notify_Login


app = FastAPI()

load_dotenv(override=True)

Backend = os.getenv("Backend_BORC_URL")
Frontend = os.getenv("Frontend_BORC_URL")
ChatBot = os.getenv("ChatBot_URL")

app.add_middleware(
    CORSMiddleware,
    allow_origins = [
        "http://localhost:5173",
        "http://localhost:8000",
        "http://localhost:5000", #API ระบบแชทบอท localhost
        Frontend, #frontend 🔔ตรงนี้เอาไปใส่ในไลน์ dev
        Backend,
        ChatBot
    ],
    allow_credentials = True,
    allow_methods     = ["*"],
    allow_headers     = ["*"],
)

# routers สำหรับ web 
# หน้าตา ui
app.include_router(views.router)

# เพิ่มการทำงานการดึงข้อมูลในไฟล์ pdf
app.include_router(extractPDF.router)

app.include_router(getData.router)
# เพิ่มการลบไฟล์ pdf
app.include_router(deleteFile.router)


#🔔 router สำหรับ notify line
app.include_router(notify_Login, prefix="/NotifyFristLogin", tags=["Notification"])

# Student
app.include_router(noti_router_St, prefix="/NotifyQueueStudent", tags=["Notification"])
app.include_router(noti_router_rechedule_St, prefix="/NotifyQueueStudent" , tags=["Notification"])

# Advisor
app.include_router(noti_router, prefix="/NotifyQueueAdivsor", tags=["Notification"])
app.include_router(noti_router_cancelled, prefix="/NotifyCancelled", tags=["Notification"])
app.include_router(noti_router_rechedule_Ad, prefix="/NotifyQueueAdivsor",tags=["Notification"])

app.include_router(noti_router_chatlink_St, prefix="/NotifyChat", tags=["Notification_Chat"])

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

logger = logging.getLogger(__name__)

# A lock per LINE user keeps replies in the same order as incoming messages,
# while still allowing different users to be handled concurrently.
user_message_locks: dict[str, asyncio.Lock] = {}

# LINE can retry a webhook when it does not receive a prompt 2xx response.
# Keep the event IDs already accepted by this process so a retry does not
# generate a duplicate answer.
processed_webhook_event_ids: set[str] = set()
MAX_PROCESSED_EVENT_IDS = 10_000



# animation chat

def send_loading(chat_id, seconds=15):
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

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        response.raise_for_status()
    except requests.RequestException:
        logger.exception("Unable to start LINE loading animation for user_id=%s", chat_id)
    
# ตอบกลับ line dev
@app.post("/callback")
async def callback(request: Request, x_line_signature: str = Header(None,alias="X-Line-Signature")):
    body = await request.body()
    body_str = body.decode('utf-8')
    try:
        # Parse here only to verify LINE's signature and obtain the events.
        # Do not call handler.handle(): it runs the RAG/LLM synchronously and
        # makes LINE wait for the whole answer before receiving HTTP 200.
        payload = handler.parser.parse(body_str, x_line_signature, as_payload=True)
    except InvalidSignatureError:
        logger.warning("Rejected LINE webhook with an invalid signature")
        raise HTTPException(status_code=400, detail="Invalid signature.")

    for event in payload.events:
        if isinstance(event, MessageEvent) and isinstance(event.message, TextMessageContent):
            event_id = getattr(event, "webhook_event_id", None)
            if event_id and event_id in processed_webhook_event_ids:
                logger.info("Ignored duplicate LINE webhook event_id=%s", event_id)
                continue

            if event_id:
                processed_webhook_event_ids.add(event_id)
                if len(processed_webhook_event_ids) > MAX_PROCESSED_EVENT_IDS:
                    # This is only a bounded in-memory retry guard. For multiple
                    # application instances, store event IDs in Redis/MongoDB.
                    processed_webhook_event_ids.clear()

            asyncio.create_task(queue_message_for_user(event))
        elif isinstance(event, FollowEvent):
            asyncio.create_task(asyncio.to_thread(handle_follow, event))

    # LINE receives 200 immediately; all slow work continues in the background.
    return PlainTextResponse("OK", status_code=200)


def handle_follow(event: FollowEvent):
    messaging_user_id = event.source.user_id
    print(f"LINE userId: {messaging_user_id}")

    user = notify_collection.find_one({"userId": messaging_user_id})  

    if user:
        name = user.get("Firstname", "คุณ")
        push_flex_notification(
            user_id=messaging_user_id,
            title=f"สวัสดีคุณ {name}! 👋",
            message="ระบบแจ้งเตือนพร้อมแล้ว \nยินดีต้อนรับเข้าสู่ระบบ😊",
            color="#00B900"
        )
    else:
        push_flex_notification(
            user_id=messaging_user_id,
            title="ยังไม่พบข้อมูลการสมัคร ❌",
             message="กรุณาสมัครสมาชิกในระบบจอง 😊\nเพื่อรับการแจ้งเตือนคิวและนัดหมาย\nในระหว่างนี้ท่านสามารถใช้แชทบอทสอบถามได้",
            color="#FF4444"
        )

def handle_message(event: MessageEvent):
    user_text = event.message.text
    user_id = event.source.user_id

    send_loading(user_id, seconds=20)

    answer, current_pdf_name = query_rag(user_text)

    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)

        messages = []

        # 1 ข้อความคำตอบจาก LLM มาก่อนเสมอ (สำคัญที่สุด)
        reply_message_AI = respone_message_LLM(answer)
        if reply_message_AI:
            messages.append(reply_message_AI)

        # 2 ดึงรูปเท่าที่ slot เหลือ ไม่ให้เกิน LINE limit
        MAX_LINE_MESSAGES = 5
        remaining_slots = MAX_LINE_MESSAGES - len(messages)

        if remaining_slots > 0:
            gridfs_ids = id_image(answer, collection, current_pdf_name)
            line_image = send_image(gridfs_ids)
            if line_image:
                messages.extend(line_image[:remaining_slots])

            
        messages = messages[:MAX_LINE_MESSAGES]

        if not messages:
            print(f"[WARN] no messages to reply for user_id={user_id}, text={user_text!r}")
            return None

        # A reply token is short-lived. This message may have waited behind an
        # earlier request from the same user, so use Push API instead.
        # line_bot_api.reply_message(
        #     ReplyMessageRequest(
        #         reply_token=event.reply_token,
        #         messages=messages,
        #     )
        # )
        line_bot_api.push_message(
            PushMessageRequest(
                to=user_id,
                messages=messages,
            )
        )
        print(event)


async def queue_message_for_user(event: MessageEvent):
    """Run blocking RAG work outside the webhook and serialize it per user."""
    user_id = event.source.user_id
    lock = user_message_locks.setdefault(user_id, asyncio.Lock())

    async with lock:
        try:
            await asyncio.to_thread(handle_message, event)
        except Exception:
            # Do not let a failed request stop later messages from this user.
            logger.exception("Failed to process LINE message for user_id=%s", user_id)

@app.get("/health")
async def health():
    return {"status": "ok"}
