import tg_service
from telethon import errors


class FakeFloodWaitError(Exception):
    pass


class FakeUsernameInvalidError(Exception):
    pass


class FakeUserPrivacyRestrictedError(Exception):
    pass


def test_error_reason_flood_wait(monkeypatch):
    monkeypatch.setattr(errors, "FloodWaitError", FakeFloodWaitError)
    exc = FakeFloodWaitError()
    assert tg_service._telethon_error_reason(exc) == "flood_wait"


def test_error_reason_username_invalid(monkeypatch):
    monkeypatch.setattr(errors, "UsernameInvalidError", FakeUsernameInvalidError)
    exc = FakeUsernameInvalidError()
    assert tg_service._telethon_error_reason(exc) == "invalid"


def test_error_reason_privacy_restricted(monkeypatch):
    monkeypatch.setattr(errors, "UserPrivacyRestrictedError", FakeUserPrivacyRestrictedError)
    exc = FakeUserPrivacyRestrictedError()
    assert tg_service._telethon_error_reason(exc) == "blocked_privacy"


def test_error_reason_default():
    assert tg_service._telethon_error_reason(Exception("x")) == "unknown_error"
