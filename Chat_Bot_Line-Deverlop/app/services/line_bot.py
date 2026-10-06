import asyncio
import logging
from threading import Thread
from collections import deque
from collections.abc import Callable
from typing import Any
from weakref import WeakValueDictionary

import requests
from linebot.v3 import WebhookHandler
from linebot.v3.messaging import ApiClient, Configuration, MessagingApi, PushMessageRequest
from linebot.v3.webhooks import FollowEvent, MessageEvent, TextMessageContent

logger = logging.getLogger(__name__)
MAX_LINE_MESSAGES = 5

class LineBotService:
    """Owns LINE webhook parsing, message ordering, and Push API delivery."""

    def __init__(
        self,
        *,
        access_token: str,
        channel_secret: str,
        query_rag: Callable[[str], tuple[str, str | None, list[str]]],
        make_text_message: Callable[[str], Any],
        make_image_messages: Callable[[list[Any]], list[Any]],
        find_notification_user: Callable[[str], dict[str, Any] | None],
        push_notification: Callable[..., Any],
        max_concurrent_jobs: int = 8,
        max_processed_event_ids: int = 10_000,
    ) -> None:
        self.access_token = access_token
        self.handler = WebhookHandler(channel_secret=channel_secret)
        self.configuration = Configuration(access_token=access_token)
        self.query_rag = query_rag
        self.make_text_message = make_text_message
        self.make_image_messages = make_image_messages
        self.find_notification_user = find_notification_user
        self.push_notification = push_notification
        self.user_message_locks: WeakValueDictionary[str, asyncio.Lock] = WeakValueDictionary()
        self.rag_semaphore = asyncio.Semaphore(max_concurrent_jobs)
        self._processed_event_ids: set[str] = set()
        self._processed_event_order: deque[str] = deque(maxlen=max_processed_event_ids)

    def parse_webhook(self, body: str, signature: str):
        return self.handler.parser.parse(body, signature, as_payload=True)

    def accept_event(self, event: MessageEvent) -> bool:
        """Return false when LINE redelivers an already accepted event."""
        event_id = getattr(event, "webhook_event_id", None)
        if not event_id:
            return True
        if event_id in self._processed_event_ids:
            logger.info("Ignoring duplicate LINE webhook event_id=%s", event_id)
            return False

        if len(self._processed_event_order) == self._processed_event_order.maxlen:
            self._processed_event_ids.discard(self._processed_event_order.popleft())
        self._processed_event_order.append(event_id)
        self._processed_event_ids.add(event_id)
        return True

    def schedule_event(self, event: Any) -> None:
        if isinstance(event, MessageEvent) and isinstance(event.message, TextMessageContent):
            if self.accept_event(event):
                asyncio.create_task(self.queue_message_for_user(event))

        elif isinstance(event, FollowEvent):
            asyncio.create_task(
                asyncio.to_thread(
                    self.handle_follow,
                    event
                )
            )

    def start_loading(self, chat_id: str, seconds: int = 20) -> None:
        try:
            response = requests.post(
                "https://api.line.me/v2/bot/chat/loading/start",
                headers={"Authorization": f"Bearer {self.access_token}"},
                json={"chatId": chat_id, "loadingSeconds": seconds},
                timeout=10,
            )
            response.raise_for_status()
        except requests.RequestException:
            logger.exception("Unable to start LINE loading animation for user_id=%s", chat_id)

    def handle_follow(self, event: FollowEvent) -> None:
        user_id = event.source.user_id
        user = self.find_notification_user(user_id)
        if user:
            self.push_notification(
                user_id=user_id,
                title=f"สวัสดีคุณ {user.get('Firstname', 'คุณ')}! 👋",
                message="ระบบแจ้งเตือนพร้อมแล้ว\nยินดีต้อนรับเข้าสู่ระบบ 😊",
                color="#00B900",
            )
            return

        self.push_notification(
            user_id=user_id,
            title="ยังไม่พบข้อมูลการสมัคร ❌",
            message="กรุณาสมัครสมาชิกในระบบจองเพื่อรับการแจ้งเตือนคิวและนัดหมาย\nระหว่างนี้สามารถใช้แชทบอทสอบถามได้",
            color="#FF4444",
        )

    async def queue_message_for_user(self, event: MessageEvent) -> None:
        user_id = event.source.user_id
        if not user_id:
            logger.warning("Ignoring LINE message without a user_id")
            return

        # Keep ordering locks only while that user has queued or active work.
        lock = self.user_message_locks.get(user_id)
        if lock is None:
            lock = asyncio.Lock()
            self.user_message_locks[user_id] = lock
        async with lock, self.rag_semaphore:
            try:
                await asyncio.to_thread(self.process_message, event)
            except Exception:
                logger.exception("Unable to process LINE message for user_id=%s", user_id)

    def process_message(self, event: MessageEvent) -> None:
        user_id = event.source.user_id
        Thread(target=self.start_loading, args=(user_id,), daemon=True).start()

        try:
            answer, _current_pdf_name, image_results = self.query_rag(
                event.message.text
            )
        except Exception:
            logger.exception(
                "Unable to generate RAG answer for user_id=%s", user_id
            )
            answer = (
                "ระบบกำลังตอบช้าหรือบริการค้นหาขัดข้อง "
                "กรุณาลองส่งคำถามอีกครั้ง"
            )
            image_results = []

        max_image_messages = MAX_LINE_MESSAGES - 1

        if len(image_results) > max_image_messages:
            answer = (
                f"{answer}\n\n"
                "📷 พบรูปภาพที่เกี่ยวข้องทั้งหมด "
                f"{len(image_results)} รูป "
                "แต่ไม่สามารถแสดงรูปภาพทั้งหมดได้ "
                "เนื่องจากข้อจำกัดของ LINE "
                f"(ส่งได้สูงสุด {max_image_messages} รูปต่อข้อความ)"
            )
            image_results = image_results[:max_image_messages]

        messages = [self.make_text_message(answer)]
        messages.extend(self.make_image_messages(image_results))
        messages = [message for message in messages if message is not None][:MAX_LINE_MESSAGES]

        if not messages:
            logger.warning("No LINE messages produced for user_id=%s", user_id)
            return

        with ApiClient(self.configuration) as api_client:
            MessagingApi(api_client).push_message(
                PushMessageRequest(to=user_id, messages=messages)
            )
