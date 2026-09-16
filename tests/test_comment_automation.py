import tempfile
import unittest
from pathlib import Path
from unittest import mock

from lib.comment_automation import (
    _is_owner,
    _put_comment,
    activity_urn_from_comment_id,
    collect_targets,
    load_state,
    save_state,
)


class OwnerAndUrns(unittest.TestCase):
    def test_owner_person_id(self):
        self.assertTrue(_is_owner({"id": "urn:li:person:X5ie8NmZTi", "name": "Sujay Viston"}))
        self.assertFalse(_is_owner({"id": "urn:li:person:e4BDZVi4fs", "name": "relaxing nature"}))

    def test_activity_urn_from_comment(self):
        cid = "urn:li:comment:(urn:li:activity:7505699050781073409,7505712495253344256)"
        self.assertEqual(
            activity_urn_from_comment_id(cid),
            "urn:li:activity:7505699050781073409",
        )


class MergeComments(unittest.TestCase):
    def test_prefers_thread_with_replies(self):
        merged: dict = {}
        _put_comment(merged, {"id": "c1", "replies": [], "replyCount": 0})
        _put_comment(merged, {"id": "c1", "replies": [{"from": {"id": "x"}}], "replyCount": 1})
        _put_comment(merged, {"id": "c1", "replies": [], "replyCount": 0})
        self.assertEqual(len(merged["c1"]["replies"]), 1)


class CollectDedupe(unittest.TestCase):
    def test_same_thread_queued_once(self):
        share = "urn:li:share:1"
        activity = "urn:li:activity:2"
        cid = "urn:li:comment:(urn:li:activity:2,99)"
        comment = {
            "id": cid,
            "message": "hello",
            "from": {"id": "other", "name": "Ada"},
            "replies": [],
        }

        class Fake:
            def list_inbox_posts(self, **_kwargs):
                return [{"id": share, "content": "post", "permalink": "https://lnkd.in/x"}]

            def list_posts(self, **_kwargs):
                return []

            def get_inbox_comments_raw(self, post_id, **_kwargs):
                return [comment]

        with mock.patch("lib.comment_automation.known_post_pairs", return_value=[(share, activity)]):
            targets = collect_targets(Fake(), {"repliedCommentIds": [], "postAliases": {}})
        ids = [t["commentId"] for t in targets]
        self.assertEqual(ids.count(cid), 1)


class StateRoundtrip(unittest.TestCase):
    def test_corrupt_state_falls_back(self):
        import lib.comment_automation as mod

        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "automation-state.json"
            path.write_text("{not json", encoding="utf-8")
            with mock.patch.object(mod, "STATE_PATH", path):
                state = load_state()
                self.assertTrue(state["enabled"])
                self.assertEqual(state["repliedCommentIds"], [])
                save_state({**state, "enabled": False})
            self.assertTrue(path.is_file())


if __name__ == "__main__":
    unittest.main()
