"""
Zana Bot v2
Discord bot with path of exile utilities
"""

import logging
from pathlib import Path

import nextcord as nc
from nextcord.ext import commands

from .config import Config, load_config
from .logger import setup_logging
from .plugin_manager import PluginManager

logger = logging.getLogger(__name__)

class ZanaBot(commands.Bot):
    def __init__(self, config: Config):
        intents = nc.Intents.default()
        super().__init__(intents=intents)
        self.zana_config= config
        self.plugin_manager = PluginManager(self)

    async def on_ready(self):
        assert self.user != None
        logger.info(f"Logged in as {self.user} (ID: {self.user.id})")

        self.plugin_manager.discover()
        await self.plugin_manager.load_all()
        logger.info(f"Loaded {len(self.extensions)} plugin(s).")
        [logger.info(f"\t- {ext.removeprefix('plugins.')}") for ext in list(self.extensions)] if self.extensions else None

        @self.slash_command(name="list_plugins", description="List available and loaded plugins")
        async def list_plugins(ctx: nc.Interaction):
            available = self.plugin_manager.available_plugins
            loaded = [ext.removeprefix('plugins.') for ext in list(self.extensions)]
            msg = (
                f"```txt\n**LOADED**\n{'\n'.join(loaded) or 'none'}```\n"
                f"```txt\n**AVAILABLE***\n{'\n'.join(available) or 'none'}```"
            )
            await ctx.send(msg, ephemeral=True)

    async def on_connect(self):
        pass

    async def on_disconnect(self):
        pass

    async def close(self):
        pass

