from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

@dataclass
class Config:
    TOKEN: str
    owner_id: str = "268128065618444289"

    @classmethod
    def from_dict(cls, data: dict) -> Config:
        return cls(
            TOKEN=data["discord_token"],
        )

def load_config(config_path: Path) -> Config:
    if not config_path.exists():
        logger.error(f"Config file not found: {config_path}.\nMake sure it exists before running zana bot.")
        raise FileNotFoundError(f"Config file not found: {config_path}.\nMake sure it exists before running zana bot.")
    with open(config_path, 'r') as cfh:
        data = json.load(cfh)
    if "discord_token" not in data:
        logger.error("Incomplete config.json missing core config \"discord_token\". Refer to example file config.TEMPLATE.json and fix it.")
        raise ValueError("Incomplete config.json missing core config \"discord_token\". Refer to example file config.TEMPLATE.json and fix it.")
    return Config.from_dict(data)
