import os
from pathlib import Path
from typing import ClassVar

from pydantic import ConfigDict
from pydantic_settings import BaseSettings


class FeatureSettings(BaseSettings):
    """Feature-scoped settings from shared env sources; replace FEATURE_ prefix."""

    env_file_path: ClassVar[Path] = Path(
        os.getenv("ENV_FILE", str(Path(__file__).resolve().parents[2] / ".env"))
    ).expanduser()

    model_config = ConfigDict(
        env_prefix="FEATURE_",
        env_file=str(env_file_path) if env_file_path.exists() else None,
    )


feature_settings = FeatureSettings()
