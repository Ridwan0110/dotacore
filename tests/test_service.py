from __future__ import annotations

import ast
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from backend.interfaces import BaseUI
from backend.models import MatchDetails, ReplaySource
from backend.service import DotaCoreService
from backend.workflow import WorkflowEngine


def test_backend_independence_from_frontend():
    """Verify that backend modules never import from frontend or ui."""
    backend_dir = Path(__file__).parent.parent / "backend"
    python_files = list(backend_dir.glob("*.py"))
    assert len(python_files) > 0

    for py_file in python_files:
        tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert not alias.name.startswith("frontend"), (
                        f"{py_file.name} imports from frontend: {alias.name}"
                    )
                    assert not alias.name.startswith("dotacore.ui"), (
                        f"{py_file.name} imports from dotacore.ui: {alias.name}"
                    )
            elif isinstance(node, ast.ImportFrom):
                mod = node.module or ""
                assert not mod.startswith("frontend"), (
                    f"{py_file.name} imports from frontend: from {mod} import ..."
                )
                assert not mod.startswith("dotacore.ui"), (
                    f"{py_file.name} imports from dotacore.ui: from {mod} import ..."
                )


def test_dotacore_service_delegations():
    service = DotaCoreService(api_key="mock_key")
    assert service.api.api_key == "mock_key"
    assert service.downloader is not None

    with patch.object(service.api, "fetch_match", return_value="mock_match"):
        assert service.fetch_match(12345) == "mock_match"

    with patch.object(service.downloader, "detect_format", return_value="zstd"):
        assert service.detect_format(Path("fake.bz2")) == "zstd"


def test_workflow_engine_with_mock_ui():
    mock_ui = MagicMock(spec=BaseUI)
    mock_ui.prompt_match_input.return_value = None  # user quits immediately

    service = DotaCoreService()
    workflow = WorkflowEngine(ui=mock_ui, service=service)

    workflow.run()

    mock_ui.show_banner.assert_called_once()
    mock_ui.prompt_match_input.assert_called_once()
    mock_ui.print_info.assert_called()
