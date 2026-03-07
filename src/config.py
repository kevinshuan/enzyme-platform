import os
from pathlib import Path
from typing import ClassVar

from pydantic import ConfigDict
from pydantic_settings import BaseSettings


class GlobalSettings(BaseSettings):
    env_file_path: ClassVar[Path] = Path(
        os.getenv("ENV_FILE", str(Path(__file__).resolve().parents[1] / ".env"))
    ).expanduser()
    model_config = ConfigDict(
        env_prefix="GLOBAL_",
        env_file=str(env_file_path) if env_file_path.exists() else None,
    )
    generator_backend: str = "mock"


global_settings = GlobalSettings()
