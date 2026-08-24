from __future__ import annotations

import logging
from pathlib import Path
from sys import excepthook

import nextcord as nc
from nextcord.ext import commands
from nextcord.ext.commands import Bot

logger = logging.getLogger(__name__)

class PluginManager(commands.Cog):
    
    def __init__(self, bot: Bot) -> None:
        self.bot = bot
        self.plugin_dir = Path(__file__).parent.parent / "plugins"

    async def _ensure_dev(self, ctx: nc.Interaction) -> bool:
        if str(ctx.user.id) in self.bot.zana_config.dev_ids:
            return True
        await ctx.send("Unauthorized.", ephemeral=True)
        return False

    @nc.slash_command(name="list_available_plugins", description="Lists available plugins to be loaded.")
    async def list_available_plugins(self, ctx: nc.Interaction) -> None:
        if not self._ensure_dev(ctx):
            logger.info(f"User {ctx.user} tried to run list_available_plugins")
            return
        embed = nc.Embed(
            title="Available plugins:",
            description=f"{'\n'.join(self.discover())}"
        )
        await ctx.send(embed=embed, ephemeral=True)


    def discover(self, quiet=False) -> list[str]:
        """Return a list of all available plugins on disk (without .py)"""
        available = sorted(f.stem for f in self.plugin_dir.glob("*.py") if f.stem not in ["__init__", "__main__"])
        logger.info(f"Discovered plugins:\n\t- {'\n\t - '.join(available)}") if (available and not quiet) else None
        return available

    async def load_all(self, plugin_list: list[str]) -> None:
        available = plugin_list
        for p in available:
            try: 
                if (pname:=f"plugins.{p}") not in self.bot.extensions:
                    self.bot.load_extension(pname)
                logger.info(f"Successfully loaded {p}.")
            except Exception as e:
                logger.exception(f"Failed to load {p}: {e}")
        await self.bot.sync_application_commands()


    @nc.slash_command(name="load_plugin", description="Loads a plugin by name")
    async def load(self, ctx: nc.Interaction, name: str) -> str:
        """Load a single plugin. Returns status message"""
        if not self._ensure_dev(ctx):
            logger.info(f"User {ctx.user} tried to run load")
            return ""
        try: 
            await ctx.response.defer(ephemeral=True)
            if (pname:=f"plugins.{name}") not in self.bot.extensions:
                self.bot.load_extension(pname)
                msg = f"Extension {name} successfully loaded."
                logger.info(msg)
                await self.bot.sync_application_commands()
                await ctx.followup.send(msg, ephemeral=True)
                return msg
            else:
                msg = f"Already loaded. {name}"
                logger.warning(msg)
                await ctx.followup.send(msg, ephemeral=True)
                return msg
        except Exception as e:
            msg=f"Failed to load {name}: {e}"
            logger.exception(msg)
            await ctx.followup.send(msg, ephemeral=True)
            return msg

    @load.on_autocomplete("name")
    async def load_autocomplete(self, Interaction: nc.Interaction, current: str):
        current = current.strip()
        if not current:
            return []
        # get available plugins:
        pl = self.discover(quiet=True)
        return [i for i in pl if current in i]

    @nc.slash_command(name="unload_plugin", description="unloads a plugin from the bot")
    async def unload(self, ctx: nc.Interaction, name: str) -> str:
        if not self._ensure_dev(ctx):
            logger.info(f"User {ctx.user} tried to run unload")
            return ""
        try:
            await ctx.response.defer(ephemeral=True)
            msg = ""
            if (pname:=f"plugins.{name}") in self.bot.extensions:
                self.bot.unload_extension(pname)
                #unloads on_message commands
                msg = f"Successfully unloaded {pname}."
                logger.info(msg)
                await self.bot.sync_application_commands()
                await ctx.followup.send(msg)
                return msg
            else:
                msg = f"Plugin {pname} is not loaded."
                logger.warning(msg)
                await ctx.followup.send(msg)
                return msg
        except Exception as e:
            msg = f"Failed to unload Extension {name}: {e}"
            await ctx.followup.send(msg)
            logger.exception(msg)
            return msg
    
    @unload.on_autocomplete("name")
    async def unload_autocomplete(self, ctx: nc.Interaction, current: str):
        current = current.strip()
        # get loaded plugins:
        pl = [i.replace('plugins.', '') for i in self.bot.extensions if current in i]
        return pl
        

    async def unload_all(self):
        for p in self.bot.extensions:
            if p == "PluginManager":
                continue
            try:
                self.bot.unload_extension(p)
                logger.info(f"Successfully unloaded extension {p}.")
            except Exception as e:
                logger.exception(f"Failed to unload extension {p}: {e}.")
        await self.bot.sync_application_commands()

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
    
    @nc.slash_command(name="reload_plugin", description="Reloads a plugin by name")
    async def reload(self,ctx: nc.Interaction, name: str) -> str:
        if not self._ensure_dev(ctx):
            logger.info(f"User {ctx.user} tried to run reload")
            return ""
        await ctx.response.defer(ephemeral=True)
        if name == "all":
            ret = ""
            for p in self.discover():
                ret_rs = await self._reload_single(p)
                ret += '\n' + ret_rs
            await self.bot.sync_application_commands()
            await ctx.followup.send(ret, ephemeral=True)
            return ret
        else:
            ret = await self._reload_single(name)
            await ctx.followup.send(ret, ephemeral=True)
            await self.bot.sync_application_commands()
            return ret
    
    @reload.on_autocomplete("name")
    async def reload_autocomplete(self, ctx: nc.Interaction, current: str):
        current = current.strip()
        # get loaded plugins:
        pl = [i.replace('plugins.', '') for i in self.bot.extensions if current in i]
        return pl

