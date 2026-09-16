import unittest

from lib.comment_automation import _is_owner, activity_urn_from_comment_id


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


if __name__ == "__main__":
    unittest.main()
