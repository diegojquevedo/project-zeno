from abc import ABC, abstractmethod
from typing import Any, Dict, List

from src.agents.schemas import DataPullResult


class DataSourceHandler(ABC):
    """Abstract base class for data source handlers"""

    @abstractmethod
    def can_handle(self, dataset: Any) -> bool:
        """Check if this handler can process the given dataset"""
        pass

    @abstractmethod
    async def pull_data(
        self,
        query: str,
        aoi: Dict,
        subregion_aois: List[Dict],
        subregion: str,
        subtype: str,
        dataset: Dict,
        start_date: str,
        end_date: str,
    ) -> DataPullResult:
        """Pull data from the source"""
        pass
