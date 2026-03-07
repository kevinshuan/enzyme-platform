from collections.abc import AsyncGenerator

from src.database import get_session


async def get_feature_session() -> AsyncGenerator:
    """
    Feature-local DB dependency wrapper.
    Keep this only when the feature needs additional dependency behavior.
    """
    async for session in get_session():
        yield session
