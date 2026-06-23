from __future__ import annotations

import logging
from pathlib import Path

from nextcord.ext.commands import Bot

logger = logging.getLogger(__name__)

class PluginManager:
    
    def __init__(self, bot: Bot) -> None:
        self.bot = bot
        self.plugin_dir = Path(__file__).parent / "plugins"

    def discover(self) -> list[str]:
        """Return a list of all available plugins on disk (without .py)"""
        available = sorted(f.stem for f in self.plugin_dir.glob("*.py") if f.stem not in ["__init__", "__main__"])
        logger.info(f"Discovered plugins:\n\t- {'\t -'.join(available)}")
        return available

    async def load_all(self) -> None:
        available = self.discover()
        for p in available:
            try: 
                if (pname:=f"plugins.{p}") not in self.bot.extensions:
                    self.bot.load_extension(pname)
                logger.info(f"Successfully loaded {p}.")
            except Exception as e:
                logger.exception(f"Failed to load {p}: {e}")

    async def load(self, name: str) -> str:
        """Load a single plugin. Returns status message"""
        try: 
            if (pname:=f"plugins.{name}") not in self.bot.extensions:
                self.bot.load_extension(pname)
                msg = f"Extension {name} successfully loaded."
                logger.info(msg)
                return msg
            else:
                msg = f"Already loaded. {name}"
                logger.warning(msg)
                return msg

        except Exception as e:
            logger.exception(f"Failed to load {name}: {e}")
            return f"Failed to load {name}: {e}"

    async def unload(self, name) -> str:
        try:
            if (pname:=f"plugins.{name}") in self.bot.extensions:
                self.bot.unload_extension(pname)
                msg = f"Successfully unloaded {pname}."
                logger.info(msg)
                return msg
            else:
                msg = f"Plugin {pname} is not loaded."
                logger.warning(msg)
                return msg
        except Exception as e:
            msg = f"Failed to unload Extension {name}: {e}"
            logger.exception(msg)
            return msg

    async def unload_all(self):
        for p in self.bot.extensions:
            try:
                self.bot.unload_extension(p)
                logger.info(f"Successfully unloaded extension {p}.")
            except Exception as e:
                logger.exception(f"Failed to unload extension {p}: {e}.")

    async def _reload_single(self, name):
        try:
            if (pname:=f"plugins.{name}") in self.bot.extensions:
                self.bot.reload_extension(pname)
                msg = f"Successfully reloaded {pname}."
                logger.info(msg)
                return msg
            else:
                msg = f"Plugin {pname} is not loaded."
                logger.warning(msg)
                return msg
        except Exception as e:
            msg = f"Failed to reload Extension {name}: {e}"
            logger.exception(msg)
            return msg

    async def reload(self, name) -> str:
        if name == "all":
            ret = ""
            for p in self.discover():
                ret_rs = await self._reload_single(p)
                ret += ret_rs
            return ret
        else:
            return await self._reload_single(name)

