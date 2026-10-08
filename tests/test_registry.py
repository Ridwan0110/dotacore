from __future__ import annotations

from unittest.mock import MagicMock
import pytest

from backend.interfaces import BaseUI
from backend.models import MatchDetails
from frontend.registry import (
    get_ui,
    launch_ui,
    list_uis,
    register_ui,
    unregister_ui,
)


def test_registry_default_cli():
    uis = list_uis()
    assert "cli" in uis
    cli_factory = get_ui("cli")
    assert cli_factory is not None


def test_registry_unknown_ui():
    with pytest.raises(KeyError) as exc_info:
        get_ui("nonexistent_ui")
    assert "nonexistent_ui" in str(exc_info.value)


def test_register_and_unregister_custom_ui():
    mock_app = MagicMock()
    register_ui("custom_gui", mock_app)
    try:
        assert "custom_gui" in list_uis()
        assert get_ui("custom_gui") is mock_app
    finally:
        unregister_ui("custom_gui")
        assert "custom_gui" not in list_uis()


def test_launch_ui_with_callable():
    mock_runner = MagicMock(return_value="launched_web")
    register_ui("web_test", mock_runner)
    try:
        res = launch_ui("web_test", api_key="my_key", custom_param=123)
        assert res == "launched_web"
        mock_runner.assert_called_once_with(api_key="my_key", custom_param=123)
    finally:
        unregister_ui("web_test")


def test_launch_ui_with_base_ui_subclass():
    class DummyUI(BaseUI):
        def __init__(self):
            self.banner_called = False

        def show_banner(self) -> None:
            self.banner_called = True

        def print_section(self, title: str) -> None: pass
        def print_info(self, message: str) -> None: pass
        def print_success(self, message: str) -> None: pass
        def print_warning(self, message: str) -> None: pass
        def print_error(self, message: str) -> None: pass
        def prompt_match_input(self): return None  # Exit immediately
        def display_match_card(self, match: MatchDetails) -> None: pass
        def prompt_confirm(self, prompt_text: str, default: bool = True) -> bool: return False
        def prompt_input(self, prompt_text: str, default=None) -> str: return ""
        def display_scoreboard(self, match: MatchDetails) -> None: pass
        def render_download_progress(self, *args, **kwargs) -> None: pass
        def render_parse_tick(self, elapsed_sec: int) -> None: pass
        def format_bytes(self, num_bytes: float) -> str: return "0 KB"

    register_ui("dummy_ui", DummyUI)
    try:
        launch_ui("dummy_ui")
    finally:
        unregister_ui("dummy_ui")
