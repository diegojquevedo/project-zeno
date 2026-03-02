from typing import Callable

_renderers: dict[str, Callable] = {}


def register_renderer(action_type: str, renderer: Callable) -> None:
    _renderers[action_type] = renderer


def get_renderer(action_type: str) -> Callable | None:
    return _renderers.get(action_type)


def get_primary_action_types() -> frozenset[str]:
    return frozenset(_renderers.keys())
