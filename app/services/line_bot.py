import asyncio
import logging
from collections import deque
from collections.abc import Callable
from typing import Any

import requests
from linebot.v3 import WebhookHandler
from linebot.v3.messaging import ApiClient, Configuration, MessagingApi, ReplyMessageRequest,PushMessageRequest
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
        query_rag: Callable[[str], tuple[str, str | None]],
        make_text_message: Callable[[str], Any],
        find_image_ids: Callable[[str, str | None], list[Any]],
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
        self.find_image_ids = find_image_ids
        self.make_image_messages = make_image_messages
        self.find_notification_user = find_notification_user
        self.push_notification = push_notification
        self.user_message_locks: dict[str, asyncio.Lock] = {}
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
            asyncio.create_task(asyncio.to_thread(self.handle_follow, event))

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

    def process_message(self, event: MessageEvent) -> None:
        """Run RAG and push one LINE response. Called in a worker thread."""
        user_id = event.source.user_id
        self.start_loading(user_id)
        answer, current_pdf_name = self.query_rag(event.message.text)

        messages = [self.make_text_message(answer)]
        image_ids = self.find_image_ids(answer, current_pdf_name)
        messages.extend(self.make_image_messages(image_ids)[: MAX_LINE_MESSAGES - len(messages)])
        messages = [message for message in messages if message is not None][:MAX_LINE_MESSAGES]
        if not messages:
            logger.warning("No LINE messages produced for user_id=%s", user_id)
            return

        with ApiClient(self.configuration) as api_client:
            MessagingApi(api_client).push_message(
                PushMessageRequest(to=user_id, messages=messages)
            )

    async def queue_message_for_user(self, event: MessageEvent) -> None:
        """Keep each user's messages ordered while allowing bounded parallel work."""
        user_id = event.source.user_id
        lock = self.user_message_locks.setdefault(user_id, asyncio.Lock())
        async with lock:
            try:
                async with self.rag_semaphore:
                    await asyncio.to_thread(self.process_message, event)
            except Exception:
                logger.exception("Failed to process LINE message for user_id=%s", user_id)
