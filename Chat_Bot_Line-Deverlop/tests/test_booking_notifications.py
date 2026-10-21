import unittest
from unittest.mock import Mock, patch

from app.notification.services import trickgerBooking


class BookingNotificationTests(unittest.TestCase):
    def test_failed_booking_notification_logs_once_and_remains_retryable(self):
        booking = {"_id": "booking-1", "UserId": "U1", "AdvisorId": "U2"}
        failure_key = ("booking-1", "CompletionNotified")
        trickgerBooking._logged_notification_failures.discard(failure_key)
        delivery = {"status": "error", "sent": 0, "failed": 2, "skipped": 0}

        with patch.object(trickgerBooking, "send_flex_notifications", return_value=delivery) as send, patch.object(
            trickgerBooking.collection_BookingOnline, "update_one"
        ) as update, self.assertLogs(level="WARNING") as logs:
            trickgerBooking.template_notify(
                booking, "CompletionNotified", "Done", "#00B900", "Completed"
            )
            trickgerBooking.template_notify(
                booking, "CompletionNotified", "Done", "#00B900", "Completed"
            )

        self.assertEqual(len(logs.output), 1)
        self.assertEqual(send.call_count, 2)
        update.assert_not_called()


if __name__ == "__main__":
    unittest.main()
