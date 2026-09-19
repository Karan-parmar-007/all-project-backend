# app/live_apps/registry.py
"""Code-backed live apps available to link from admin projects."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any


ShutdownHook = Callable[[], None]


@dataclass
class LiveAppDefinition:
    key: str
    name: str
    description: str
    # Invoked when admin disables access / unlinks the app / changes roles.
    shutdown_hook: ShutdownHook | None = None


_REGISTRY: dict[str, LiveAppDefinition] = {}
_RUNTIME_SHUTDOWNS: dict[str, list[ShutdownHook]] = {}


def register_live_app(
    key: str,
    *,
    name: str,
    description: str,
    shutdown_hook: ShutdownHook | None = None,
) -> LiveAppDefinition:
    definition = LiveAppDefinition(
        key=key,
        name=name,
        description=description,
        shutdown_hook=shutdown_hook,
    )
    _REGISTRY[key] = definition
    return definition


def list_live_apps() -> list[dict[str, Any]]:
    return [
        {
            "key": app.key,
            "name": app.name,
            "description": app.description,
        }
        for app in sorted(_REGISTRY.values(), key=lambda a: a.name.lower())
    ]


def get_live_app(key: str | None) -> LiveAppDefinition | None:
    if not key:
        return None
    return _REGISTRY.get(key)


def is_known_app_key(key: str | None) -> bool:
    return bool(key) and key in _REGISTRY


def register_runtime_shutdown(app_key: str, hook: ShutdownHook) -> None:
    _RUNTIME_SHUTDOWNS.setdefault(app_key, []).append(hook)


def shutdown_app(app_key: str | None) -> None:
    """Stop all active runtime for a linked live app."""
    if not app_key:
        return
    definition = _REGISTRY.get(app_key)
    if definition and definition.shutdown_hook is not None:
        definition.shutdown_hook()
    for hook in list(_RUNTIME_SHUTDOWNS.get(app_key, [])):
        hook()


# Built-in apps. Shutdown hooks are wired by each module on import.
register_live_app(
    "advance_scraper",
    name="Advance Maps Scraper",
    description=(
        "Search Google Maps by location and stream company leads. "
        "50 companies per user per day."
    ),
)
