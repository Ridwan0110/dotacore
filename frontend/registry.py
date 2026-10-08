from __future__ import annotations

import inspect
from typing import Any, Callable, Dict, List, Optional, Type, Union

from backend.interfaces import BaseUI
from backend.service import DotaCoreService
from backend.workflow import WorkflowEngine

# Factory type: either a BaseUI subclass/instance, or an App class/runner callable
UIFactory = Union[Type[BaseUI], BaseUI, Callable[..., Any]]

_REGISTRY: Dict[str, UIFactory] = {}


def register_ui(name: str, target: UIFactory) -> None:
    """
    Register a UI frontend in the plug-and-play registry.
    
    `target` can be:
    - A subclass or instance of `backend.interfaces.BaseUI`
    - A custom application class with a `.start()` or `.run()` method
    - A callable function that takes `api_key: Optional[str] = None` and launches the UI
    """
    key = name.strip().lower()
    if not key:
        raise ValueError("UI name cannot be empty.")
    _REGISTRY[key] = target


def unregister_ui(name: str) -> bool:
    """Remove a UI frontend from the registry."""
    key = name.strip().lower()
    return _REGISTRY.pop(key, None) is not None


def list_uis() -> List[str]:
    """Return a sorted list of registered UI frontend identifiers."""
    return sorted(_REGISTRY.keys())


def get_ui(name: str) -> UIFactory:
    """Retrieve the registered UI factory by name."""
    key = name.strip().lower()
    if key not in _REGISTRY:
        available = ", ".join(list_uis()) or "none"
        raise KeyError(f"UI '{name}' is not registered. Available UIs: {available}")
    return _REGISTRY[key]


def launch_ui(
    name: str = "cli",
    api_key: Optional[str] = None,
    service: Optional[DotaCoreService] = None,
    **kwargs: Any,
) -> Any:
    """
    Instantiate and launch the requested UI frontend by name.
    
    If the target is a BaseUI, it will automatically be wrapped in a
    WorkflowEngine and executed.
    """
    target = get_ui(name)

    # 1. If target is a BaseUI class or instance
    if (isinstance(target, type) and issubclass(target, BaseUI)) or isinstance(target, BaseUI):
        ui_instance = target() if isinstance(target, type) else target
        engine = WorkflowEngine(ui=ui_instance, service=service, api_key=api_key, **kwargs)
        return engine.run()

    # 2. If target is a class with start() or run()
    if inspect.isclass(target):
        try:
            instance = target(api_key=api_key, **kwargs)
        except TypeError:
            instance = target(**kwargs)

        if hasattr(instance, "start"):
            return instance.start()
        if hasattr(instance, "run"):
            return instance.run()
        return instance

    # 3. If target is a callable runner function
    if callable(target):
        try:
            return target(api_key=api_key, **kwargs)
        except TypeError:
            return target(**kwargs)

    raise TypeError(f"Invalid UI target registered under '{name}': {type(target)}")


# Auto-register default CLI frontend
from .cli.app import CLIApp
register_ui("cli", CLIApp)
