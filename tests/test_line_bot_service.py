import asyncio
import time
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from linebot.v3.messaging import ImageMessage, TextMessage

from app.services.line_bot import LineBotService


def make_service(**overrides):
    defaults = {
        "access_token": "test-token",
        "channel_secret": "test-secret",
        "query_rag": Mock(return_value=("answer", "guide.pdf")),
        "make_text_message": Mock(return_value=TextMessage(text="answer")),
        "find_image_ids": Mock(return_value=[]),
        "make_image_messages": Mock(return_value=[]),
        "find_notification_user": Mock(return_value=None),
        "push_notification": Mock(),
    }
    defaults.update(overrides)
    return LineBotService(**defaults)


def message_event(user_id="U1", text="hello", event_id=None):
    return SimpleNamespace(
        webhook_event_id=event_id,
        reply_token="reply-token",
        source=SimpleNamespace(user_id=user_id),
        message=SimpleNamespace(text=text),
    )


class LineBotServiceTests(unittest.TestCase):
    def test_event_is_processed_only_once(self):
        service = make_service(max_processed_event_ids=2)
        event = message_event(event_id="event-1")

        self.assertTrue(service.accept_event(event))
        self.assertFalse(service.accept_event(event))

    def test_old_event_ids_expire_from_bounded_cache(self):
        service = make_service(max_processed_event_ids=2)
        first = message_event(event_id="event-1")
        self.assertTrue(service.accept_event(first))
        self.assertTrue(service.accept_event(message_event(event_id="event-2")))
        self.assertTrue(service.accept_event(message_event(event_id="event-3")))
        self.assertTrue(service.accept_event(first))

    def test_message_reply_contains_text_and_at_most_four_images(self):
        images = [
            ImageMessage(
                original_content_url=f"https://example.com/{index}.jpg",
                preview_image_url=f"https://example.com/{index}.jpg",
            )
            for index in range(6)
        ]
        service = make_service(
            find_image_ids=Mock(return_value=["1", "2", "3", "4", "5", "6"]),
            make_image_messages=Mock(return_value=images),
        )
        service.start_loading = Mock()

        with patch("app.services.line_bot.ApiClient") as api_client, patch(
            "app.services.line_bot.MessagingApi"
        ) as messaging_api:
            service.process_message(message_event())

        service.start_loading.assert_called_once_with("U1")
        request = messaging_api.return_value.reply_message.call_args.args[0]
        self.assertEqual(request.reply_token, "reply-token")
        self.assertEqual(len(request.messages), 5)
        self.assertIsInstance(request.messages[0], TextMessage)

    def test_follow_event_sends_registered_user_welcome(self):
        notify = Mock()
        service = make_service(
            find_notification_user=Mock(return_value={"Firstname": "Ada"}),
            push_notification=notify,
        )

        service.handle_follow(SimpleNamespace(source=SimpleNamespace(user_id="U1")))

        notify.assert_called_once()
        self.assertEqual(notify.call_args.kwargs["user_id"], "U1")
        self.assertIn("Ada", notify.call_args.kwargs["title"])

    def test_same_user_messages_are_processed_in_order(self):
        service = make_service(max_concurrent_jobs=2)
        processed = []

        def process(event):
            processed.append(event.message.text)
            time.sleep(0.02)

        service.process_message = process

        async def run_queue():
            await asyncio.gather(
                service.queue_message_for_user(message_event(text="first")),
                service.queue_message_for_user(message_event(text="second")),
            )

        asyncio.run(run_queue())
        self.assertEqual(processed, ["first", "second"])


if __name__ == "__main__":
    unittest.main()
