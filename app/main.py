import os

from dotenv import load_dotenv
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from linebot.v3.exceptions import InvalidSignatureError

from app.notification.DB.database_noti import collection as notify_collection
from app.notification.routers.GetLine_id import router as notify_login_router
from app.notification.routers.line_notify import push_flex_notification
from app.notification.users.Advisor.NotifyQueue import router as advisor_queue_router
from app.notification.users.Advisor.NotifyQueueCancelled import router as advisor_cancelled_router
from app.notification.users.Advisor.NotifyRecheduleAdvisor import router as advisor_reschedule_router
from app.notification.users.Student.NotifyQueueStudent import router as student_queue_router
from app.notification.users.Student.NotifyReaheduleStudent import router as student_reschedule_router
from app.notification.users.Student.NotifyUrl_Student import router as student_chat_router
from app.retriever import id_image, query_rag, respone_message_LLM, send_image
from app.routers import deleteFile, extractPDF, getData, views
from app.services.line_bot import LineBotService

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
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

for router in (views.router, extractPDF.router, deleteFile.router, getData.router):
    app.include_router(router)

app.include_router(notify_login_router, prefix="/NotifyFristLogin", tags=["Notification"])
app.include_router(student_queue_router, prefix="/NotifyQueueStudent", tags=["Notification"])
app.include_router(student_reschedule_router, prefix="/NotifyQueueStudent", tags=["Notification"])
app.include_router(advisor_queue_router, prefix="/NotifyQueueAdivsor", tags=["Notification"])
app.include_router(advisor_cancelled_router, prefix="/NotifyCancelled", tags=["Notification"])
app.include_router(advisor_reschedule_router, prefix="/NotifyQueueAdivsor", tags=["Notification"])
app.include_router(student_chat_router, prefix="/NotifyChat", tags=["Notification_Chat"])

line_bot = LineBotService(
    access_token=get_secret_value("ACCESS_TOKEN") or "",
    channel_secret=get_secret_value("CHANNEL_SECRET") or "",
    query_rag=query_rag,
    make_text_message=respone_message_LLM,
    find_image_ids=id_image,
    make_image_messages=send_image,
    find_notification_user=lambda user_id: notify_collection.find_one({"userId": user_id}),
    push_notification=push_flex_notification,
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
