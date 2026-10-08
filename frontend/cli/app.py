from __future__ import annotations

from pathlib import Path
from typing import Optional

from backend.service import DotaCoreService
from backend.workflow import WorkflowEngine
from .styles import Style, paint
from .ui import TerminalUI


class CLIApp:
    """CLI application controller for DotaCore."""

    def __init__(self, api_key: Optional[str] = None):
        self.ui = TerminalUI()
        self.service = DotaCoreService(api_key=api_key)
        self.workflow = WorkflowEngine(ui=self.ui, service=self.service)

    @property
    def api(self):
        return self.service.api

    @property
    def downloader(self):
        return self.service.downloader

    @property
    def output_directory(self) -> Path:
        return self.workflow.output_directory

    @output_directory.setter
    def output_directory(self, value: Path) -> None:
        self.workflow.output_directory = value

    @property
    def auto_decompress(self) -> bool:
        return self.workflow.auto_decompress

    @auto_decompress.setter
    def auto_decompress(self, value: bool) -> None:
        self.workflow.auto_decompress = value

    @property
    def keep_archive(self) -> bool:
        return self.workflow.keep_archive

    @keep_archive.setter
    def keep_archive(self, value: bool) -> None:
        self.workflow.keep_archive = value

    def start(self) -> None:
        """Entry point for CLI execution."""
        self.workflow.run()

    def _run_single_match(self) -> None:
        """Run single match workflow."""
        self.workflow._run_single_match()


# Backwards compatibility alias
DotaCoreApp = CLIApp


def run_cli(api_key: Optional[str] = None) -> None:
    """Convenience launcher for the CLI application."""
    app = CLIApp(api_key=api_key)
    app.start()
