from base64 import b64encode
from dataclasses import dataclass
from typing import Dict, List, Optional

from src.agents.schemas import CodeActPart, PartType

__all__ = ["CodeActPart", "ExecutionResult", "PartType"]


@dataclass
class ExecutionResult:
    """Result from code execution."""

    parts: List[CodeActPart]
    chart_data: Optional[List[Dict]]
    error: Optional[str] = None

    def get_encoded_parts(self) -> List[Dict]:
        return [
            {
                "type": part.type.value,
                "content": b64encode(part.content.encode("utf-8")).decode(
                    "utf-8"
                ),
            }
            for part in self.parts
        ]
