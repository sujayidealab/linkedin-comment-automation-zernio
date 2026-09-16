from unittest.mock import patch

from lib.comment_automation import _is_owner


def test_owner_person_id():
    assert _is_owner({"id": "urn:li:person:X5ie8NmZTi", "name": "Sujay Viston"})
    assert not _is_owner({"id": "urn:li:person:e4BDZVi4fs", "name": "relaxing nature"})
