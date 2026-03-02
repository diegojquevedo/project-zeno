from typing import Callable

_prompt_block_providers: list[Callable[[], str]] = []


def register_prompt_block(provider: Callable[[], str]) -> None:
    _prompt_block_providers.append(provider)


def get_all_custom_prompt_blocks() -> str:
    return "\n".join(p() for p in _prompt_block_providers if p())
