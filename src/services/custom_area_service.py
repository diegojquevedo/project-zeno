import json
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.agents.llms import SMALL_MODEL
from src.core.exceptions import ResourceNotFoundError
from src.models import CustomAreaOrm
from src.schemas import (
    CustomAreaCreate,
    CustomAreaModel,
    CustomAreaNameResponse,
)


class CustomAreaService:
    """Service for custom area CRUD and name generation."""

    AREA_NAME_PROMPT = """Name this GeoJSON Features from physical geography.
        Pick name in this order:
        1. Most salient intersecting natural feature (range/peak; desert/plateau/basin; river/lake/watershed; coast/gulf/strait; plain/valley)
        2. If none clear, use a broader natural unit (ecoregion/physiographic province/biome or climate/latitude bands)
        3. If still vague, add a directional qualifier (Northern/Upper/Coastal/etc)
        4. Only if needed, append "near [city/town]" for disambiguation (no countries/states)
        Exclude all geopolitical terms and demonyms; avoid disputed/historical polities and sovereignty language.
        Prefer widely used, neutral physical names; do not invent obscure terms.
        Return a name only, strictly ≤50 characters.

        Features: {features}
        """

    @staticmethod
    def _orm_to_model(area: CustomAreaOrm) -> CustomAreaModel:
        """Convert ORM to Pydantic model."""
        return CustomAreaModel(
            id=area.id,
            user_id=area.user_id,
            name=area.name,
            created_at=area.created_at,
            updated_at=area.updated_at,
            geometries=[json.loads(g) for g in area.geometries],
        )

    @staticmethod
    async def generate_area_name(features: list) -> str:
        """Generate a neutral geographic name for GeoJSON features."""
        response = await SMALL_MODEL.with_structured_output(
            CustomAreaNameResponse
        ).ainvoke(
            CustomAreaService.AREA_NAME_PROMPT.format(features=features[0])
        )
        return response.name

    @staticmethod
    async def create_custom_area(
        user_id: str,
        area: CustomAreaCreate,
        session: AsyncSession,
    ) -> CustomAreaModel:
        """Create a new custom area for the user."""
        custom_area = CustomAreaOrm(
            user_id=user_id,
            name=area.name,
            geometries=[g.model_dump_json() for g in area.geometries],
        )
        session.add(custom_area)
        await session.commit()
        await session.refresh(custom_area)
        return CustomAreaService._orm_to_model(custom_area)

    @staticmethod
    async def list_custom_areas(
        user_id: str,
        session: AsyncSession,
    ) -> list[CustomAreaModel]:
        """List all custom areas belonging to the user."""
        stmt = select(CustomAreaOrm).filter_by(user_id=user_id)
        result = await session.execute(stmt)
        areas = result.scalars().all()
        return [CustomAreaService._orm_to_model(a) for a in areas]

    @staticmethod
    async def get_custom_area(
        area_id: UUID,
        user_id: str,
        session: AsyncSession,
    ) -> CustomAreaModel:
        """Get a specific custom area by ID."""
        stmt = select(CustomAreaOrm).filter_by(id=area_id, user_id=user_id)
        result = await session.execute(stmt)
        area = result.scalars().first()
        if not area:
            raise ResourceNotFoundError("Custom area not found")
        return CustomAreaService._orm_to_model(area)

    @staticmethod
    async def update_custom_area_name(
        area_id: UUID,
        user_id: str,
        name: str,
        session: AsyncSession,
    ) -> CustomAreaModel:
        """Update the name of a custom area."""
        stmt = select(CustomAreaOrm).filter_by(id=area_id, user_id=user_id)
        result = await session.execute(stmt)
        area = result.scalars().first()
        if not area:
            raise ResourceNotFoundError("Custom area not found")
        area.name = name
        await session.commit()
        await session.refresh(area)
        return CustomAreaService._orm_to_model(area)

    @staticmethod
    async def delete_custom_area(
        area_id: UUID,
        user_id: str,
        session: AsyncSession,
    ) -> None:
        """Delete a custom area."""
        stmt = select(CustomAreaOrm).filter_by(id=area_id, user_id=user_id)
        result = await session.execute(stmt)
        area = result.scalars().first()
        if not area:
            raise ResourceNotFoundError("Custom area not found")
        await session.delete(area)
        await session.commit()
