import json

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import ResourceNotFoundError
from src.models import UserOrm
from src.schemas import UserModel, UserProfileUpdateRequest


class AuthService:
    """Service for user authentication and profile operations."""

    @staticmethod
    async def update_user_profile(
        user_id: str,
        profile_update: UserProfileUpdateRequest,
        session: AsyncSession,
    ) -> UserModel:
        """Update user profile fields."""
        result = await session.execute(select(UserOrm).where(UserOrm.id == user_id))
        db_user = result.scalars().first()
        if not db_user:
            raise ResourceNotFoundError("User not found")

        update_data = profile_update.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            if field == "topics" and value is not None:
                value = json.dumps(value)
            setattr(db_user, field, value)

        await session.commit()
        await session.refresh(db_user)

        return UserModel(
            id=db_user.id,
            name=db_user.name,
            email=db_user.email,
            created_at=db_user.created_at,
            updated_at=db_user.updated_at,
            user_type=db_user.user_type,
            first_name=db_user.first_name,
            last_name=db_user.last_name,
            profile_description=db_user.profile_description,
            sector_code=db_user.sector_code,
            role_code=db_user.role_code,
            job_title=db_user.job_title,
            company_organization=db_user.company_organization,
            country_code=db_user.country_code,
            preferred_language_code=db_user.preferred_language_code,
            gis_expertise_level=db_user.gis_expertise_level,
            areas_of_interest=db_user.areas_of_interest,
            topics=json.loads(db_user.topics) if db_user.topics else None,
            receive_news_emails=db_user.receive_news_emails,
            help_test_features=db_user.help_test_features,
            has_profile=db_user.has_profile,
        )
