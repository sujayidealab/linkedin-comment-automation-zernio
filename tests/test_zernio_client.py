"""Offline tests for the Zernio LinkedIn client."""
from __future__ import annotations

import unittest
from unittest import mock

from lib.zernio_client import ZernioClient, _linkedin_post_id
from lib.backend_selector import active_backend


class UrnParsing(unittest.TestCase):
    def test_activity_url(self):
        url = "https://www.linkedin.com/posts/jane-doe-activity-7381122334455-AbCd"
        self.assertEqual(_linkedin_post_id(url), "urn:li:activity:7381122334455")

    def test_passthrough_urn(self):
        urn = "urn:li:activity:1"
        self.assertEqual(_linkedin_post_id(urn), urn)


class Backend(unittest.TestCase):
    def test_manual_without_key(self):
        with mock.patch.dict("os.environ", {}, clear=True):
            self.assertEqual(active_backend(), "manual")

    def test_zernio_with_key(self):
        with mock.patch.dict("os.environ", {"ZERNIO_API_KEY": "sk_test"}, clear=True):
            self.assertEqual(active_backend(), "zernio")


class FetchCommentsHttp(unittest.TestCase):
    def test_comments_request(self):
        client = ZernioClient.__new__(ZernioClient)
        client.timeout = 5
        client._session = mock.Mock()
        resp = mock.Mock()
        resp.status_code = 200
        resp.content = b"{}"
        resp.json.return_value = {
            "comments": [
                {"id": "c1", "message": "hi", "from": {"name": "Ada"}},
            ]
        }
        client._session.get.return_value = resp
        with mock.patch.object(client, "resolve_linkedin_account_id", return_value="acc1"):
            rows = client.fetch_post_comments(post_id="urn:li:activity:9", max_items=10)
        self.assertEqual(rows[0]["authorName"], "Ada")
        args, kwargs = client._session.get.call_args
        self.assertIn("inbox/comments/urn%3Ali%3Aactivity%3A9", args[0])
        self.assertEqual(kwargs["params"]["accountId"], "acc1")
        self.assertIn("limit", kwargs["params"])


if __name__ == "__main__":
    unittest.main()
