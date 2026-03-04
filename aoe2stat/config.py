from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class AppConfig:
    parser_version: str = "sprint-1.1"
    schema_version: str = "1.0.0"
    default_grid_size: int = 32
    default_window_sec: int = 10

    @staticmethod
    def from_env() -> "AppConfig":
        return AppConfig(
            parser_version=os.getenv("AOE2_PARSER_VERSION", "sprint-1.1"),
            schema_version=os.getenv("AOE2_SCHEMA_VERSION", "1.0.0"),
            default_grid_size=int(os.getenv("AOE2_GRID_SIZE", "32")),
            default_window_sec=int(os.getenv("AOE2_WINDOW_SEC", "10")),
        )

