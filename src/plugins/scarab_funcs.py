from __future__ import annotations

import nextcord as nc
from nextcord.ext import commands
import logging
import asyncio

from plugins.utils import scarab_regex_lib as srl

logger = logging.getLogger(__name__)

class ScarabCommands(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
    
    sr = srl.scarab_regexer()

    def list_price(self, price_list: dict[str, float], names: list[str]) -> str:
        returnstr = "```python\n"
        prices = price_list.items()
        names = [n[1:-1] for n in names] # Removes regex anchors from names
        largest_name = len(max(names, key=len))
        for p in prices:
            if p[0][1:-1] in names:
                returnstr += f"{p[0][1:-1]: <{largest_name}} = {p[1]:.2f}c\n"
        return returnstr + "```"

    @nc.slash_command(name="scarab_regex", description="Generates regex to vendor scarabs.")
    async def scarab_regex(self, interaction: nc.Interaction, threshold: float = 1.0):
        await interaction.response.defer(ephemeral=True) # acknowledges to discord that the message was received. Ephemeral so only the person who sent the message can see it
        self.sr.update_value_threshold(threshold) if self.sr.get_threshold() != threshold else None
        text = await asyncio.to_thread(self.sr.gen_scarab_regex, print_now=False)
        embed = nc.Embed(title="Regex generated",
                        description=f"```{text}```",
                        colour=0xf5ed00,
                        timestamp=self.sr.get_last_updated())
        embed.add_field(name="Price Threshold",
                        value=f"{self.sr.get_threshold()}c\nLast updated:",
                        inline=False)
        embed.set_thumbnail(url="https://web.poecdn.com/gen/image/WzI1LDE0LHsiZiI6IjJESXRlbXMvQ3VycmVuY3kvU2NhcmFicy9TdXBlclNjYXJhYjMiLCJzY2FsZSI6MX1d/64d9f06e78/SuperScarab3.png")
        logger.info(f"User {interaction.user} used scarab_regex with threshold {threshold}")
        await interaction.followup.send(embed=embed)

    @nc.slash_command(name="scarab_prices", description="Lists the latest scarab prices.")
    async def scarab_prices(self, interaction: nc.Interaction):
        await interaction.response.defer(ephemeral=True) # acknowledges to discord that the message was received. Ephemeral so only the person who sent the message can see it
        pricesList = self.sr.prices.items()
        pricesList = [i[1] for i in pricesList]
        middle_of_list = pricesList[int(len(pricesList)/2)]
        orig_threshold = self.sr.get_threshold()
        await asyncio.to_thread(self.sr.update_value_threshold, middle_of_list)
        await asyncio.to_thread(self.sr.update_lists)

        embedb = nc.Embed(
            title="First half:",
            description=f"{self.list_price(self.sr.prices, self.sr.sell)}",
            colour=0x24c1ff
            )
        embedb.set_thumbnail(url="https://web.poecdn.com/gen/image/WzI1LDE0LHsiZiI6IjJESXRlbXMvQ3VycmVuY3kvU2NhcmFicy9TdXBlclNjYXJhYjciLCJzY2FsZSI6MX1d/28b95bae7b/SuperScarab7.png")
        embeda = nc.Embed(
            title="Second half:",
            description=f"{self.list_price(self.sr.prices, self.sr.keep)}\nLast updated:",
            colour=0x24c1ff,
            timestamp=self.sr.get_last_updated()
            )
        logger.info(f"User {interaction.user} used scarab_prices.")
        await asyncio.to_thread(self.sr.update_value_threshold, orig_threshold)
        await interaction.followup.send(embed=embedb)
        await interaction.followup.send(embed=embeda, ephemeral=True)

    @nc.slash_command(name="scarab_flip", description="Provides regex with the cheapest N scarabs. Default 5")
    async def scarab_flip(self, interaction: nc.Interaction, n: int = 5):
        await interaction.response.defer(ephemeral=True) # acknowledges to discord that the message was received. Ephemeral so only the person who sent the message can see it
        await asyncio.to_thread(self.sr.update_lists)
        text = await asyncio.to_thread(self.sr.get_cheapest_n, n, False)
        embed = nc.Embed(
            title="Scarab Faustus Flipper!",
            colour=nc.Colour.brand_red(),
            description=f"```{text}```\nLast updated:",
            timestamp=self.sr.get_last_updated()
        )
        embed.set_thumbnail(url="https://web.poecdn.com/gen/image/WzI1LDE0LHsiZiI6IjJESXRlbXMvQ3VycmVuY3kvU2NhcmFicy9TdXBlclNjYXJhYjEiLCJzY2FsZSI6MX1d/acc1b258a3/SuperScarab1.png")
        logger.info(f"User {interaction.user} used scarab_flip with cutoff of {n} scrabs.")
        await interaction.followup.send(embed=embed)

def setup(bot: commands.Bot):
    bot.add_cog(ScarabCommands(bot))
