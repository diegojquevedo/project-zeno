from langchain_core.tools import BaseTool

_custom_tools: list[BaseTool] = []


def register_tool(tool: BaseTool) -> None:
    _custom_tools.append(tool)


def get_all_custom_tools() -> list[BaseTool]:
    return list(_custom_tools)
