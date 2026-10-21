import unittest

from app.services.image_selection import select_image_urls


class RetrieverImageTests(unittest.TestCase):
    def test_single_advisor_photo_requests_choose_one_retrieved_image(self):
        results = [
            {"metadata": {"type": "text"}},
            {"metadata": {"type": "image", "image_url": "https://example.com/advisor.jpg"}},
        ]

        for query in ("ขอรูปอาจารย์ท่านนี้", "ส่งภาพอาจารย์คนนี้ให้หน่อย"):
            with self.subTest(query=query):
                self.assertEqual(
                    select_image_urls(query, results, []),
                    ["https://example.com/advisor.jpg"],
                )

    def test_explicit_multiple_advisor_request_does_not_attach_image(self):
        results = [{"metadata": {"type": "image", "image_url": "https://example.com/advisor.jpg"}}]
        self.assertEqual(select_image_urls("ขอรูปอาจารย์ทุกคน", results, []), [])


if __name__ == "__main__":
    unittest.main()
