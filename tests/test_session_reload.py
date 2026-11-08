import importlib


def test_reload_preserves_live_session_identity_and_state():
    session_module = importlib.import_module("core.session")
    live_ref = session_module.session
    state = {
        "aes_key": live_ref.aes_key,
        "is_authenticated": live_ref.is_authenticated,
        "selected_person_id": live_ref.selected_person_id,
        "selected_account_id": live_ref.selected_account_id,
        "selected_fy": live_ref.selected_fy,
        "privacy_mode": live_ref.privacy_mode,
        "theme": live_ref.theme,
        "sidebar_open": live_ref.sidebar_open,
    }
    test_key = b"test-only-session-key"

    try:
        live_ref.login(test_key)
        live_ref.set_person(41)
        live_ref.set_account(73)
        live_ref.set_financial_year("2025-26")
        live_ref.set_privacy_mode(True)
        live_ref.set_theme("dark")
        live_ref.sidebar_open = False

        reloaded = importlib.reload(session_module)

        assert reloaded.session is live_ref
        assert isinstance(live_ref, reloaded.Session)
        assert live_ref.aes_key == test_key
        assert live_ref.is_authenticated is True
        assert live_ref.selected_person_id == 41
        assert live_ref.selected_account_id == 73
        assert live_ref.selected_fy == "2025-26"
        assert live_ref.privacy_mode is True
        assert live_ref.theme == "dark"
        assert live_ref.is_sidebar_open() is False

        # Methods from the reloaded class remain usable on the retained object.
        live_ref.set_theme("light")
        assert live_ref.theme == "light"

        live_ref.logout()
        assert live_ref.aes_key is None
        assert live_ref.is_authenticated is False
        assert live_ref.selected_person_id is None
        assert live_ref.selected_account_id is None
        assert live_ref.privacy_mode is False
    finally:
        live_ref.aes_key = state["aes_key"]
        live_ref.is_authenticated = state["is_authenticated"]
        live_ref.selected_person_id = state["selected_person_id"]
        live_ref.selected_account_id = state["selected_account_id"]
        live_ref.selected_fy = state["selected_fy"]
        live_ref.privacy_mode = state["privacy_mode"]
        live_ref.theme = state["theme"]
        live_ref.sidebar_open = state["sidebar_open"]
