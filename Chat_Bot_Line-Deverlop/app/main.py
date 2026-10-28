import asyncio
import os

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from linebot.v3.exceptions import InvalidSignatureError

from app.notification.DB.database_noti import collection as notify_collection
from app.notification.routers.GetLine_id import router as notify_login_router
from app.notification.services.trickgerBooking import booking_notification_loop
from app.notification.users.Advisor.NotifyQueue import router as advisor_queue_router
from app.notification.users.Advisor.NotifyQueueCancelled import router as advisor_cancelled_router
from app.notification.users.Advisor.NotifyRecheduleAdvisor import router as advisor_reschedule_router
from app.notification.users.Admin.NotifyPendding import router as admin_pending_login_router
from app.notification.users.Student.NotifyQueueStudent import router as student_queue_router
from app.notification.users.Student.NotifyReaheduleStudent import router as student_reschedule_router
from app.notification.users.Student.NotifyUrl_Student import router as student_chat_router
from app.notification.users.Student.NotifyUrl_Students_Group import router as student_group_chat_router
from app.retriever import query_rag, respone_message_LLM, send_image
from app.routers import deleteFile, extractPDF, getData
from app.services.line_bot import LineBotService
from app.security import require_api_key

load_dotenv(override=True)
app = FastAPI()


def get_secret_value(name: str, default: str | None = None) -> str | None:
    secret_path = f"/secrets/{name}"
    if os.path.exists(secret_path):
        with open(secret_path, encoding="utf-8") as secret_file:
            return secret_file.read().strip()
    return os.getenv(name, default)


configured_origins = [
    "http://localhost:5173",
    "http://localhost:8000",
    "http://localhost:5000",
    *filter(None, [
        os.getenv("Frontend_BORC_URL"),
        os.getenv("Backend_BORC_URL"),
        os.getenv("ChatBot_URL"),
    ]),
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=configured_origins,
    # allow_origin_regex=r"https://.*\.up\.railway\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

api_key_required = [Depends(require_api_key)]

for router in (extractPDF.router, deleteFile.router, getData.router):
    app.include_router(router, dependencies=api_key_required)

app.include_router(notify_login_router, prefix="/NotifyFristLogin", tags=["Notification"], dependencies=api_key_required)
app.include_router(admin_pending_login_router, prefix="/NotifyFristLogin", tags=["Notification"], dependencies=api_key_required)
app.include_router(student_queue_router, prefix="/NotifyQueueStudent", tags=["Notification"], dependencies=api_key_required)
app.include_router(student_reschedule_router, prefix="/NotifyQueueStudent", tags=["Notification"], dependencies=api_key_required)
app.include_router(advisor_queue_router, prefix="/NotifyQueueAdivsor", tags=["Notification"], dependencies=api_key_required)
app.include_router(advisor_cancelled_router, prefix="/NotifyCancelled", tags=["Notification"], dependencies=api_key_required)
app.include_router(advisor_reschedule_router, prefix="/NotifyQueueAdivsor", tags=["Notification"], dependencies=api_key_required)
app.include_router(student_chat_router, prefix="/NotifyChat", tags=["Notification_Chat"], dependencies=api_key_required)
app.include_router(student_group_chat_router, prefix="/NotifyChatGroup", tags=["Notification_Chat"], dependencies=api_key_required)

line_bot = LineBotService(
    access_token=get_secret_value("ACCESS_TOKEN") or "",
    channel_secret=get_secret_value("CHANNEL_SECRET") or "",
    query_rag=query_rag,
    make_text_message=respone_message_LLM,
    make_image_messages=send_image,
    find_notification_user=lambda user_id: notify_collection.find_one({"userId": user_id}),
)


@app.post("/callback")
async def callback(
    request: Request,
    x_line_signature: str = Header(alias="X-Line-Signature"),
):
    try:
        payload = line_bot.parse_webhook(
            (await request.body()).decode("utf-8"),
            x_line_signature,
        )
    except InvalidSignatureError as exc:
        raise HTTPException(status_code=400, detail="Invalid LINE signature") from exc

    for event in payload.events:
        line_bot.schedule_event(event)
    return PlainTextResponse("OK")


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.on_event("startup")
async def start_booking_notifications():
    app.state.booking_notification_task = asyncio.create_task(booking_notification_loop())


@app.on_event("shutdown")
async def stop_booking_notifications():
    task = getattr(app.state, "booking_notification_task", None)
    if task:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
