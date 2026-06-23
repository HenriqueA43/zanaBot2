import nextcord as nc
from nextcord.ext import commands

class testCog(commands.Cog):

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @nc.slash_command(name="test", description="test a command")
    async def test(self, ctx: nc.Interaction):
        await ctx.send(f"Testing! latency: {round(self.bot.latency * 1000)}ms")

def setup(bot: commands.Bot ):
    bot.add_cog(testCog(bot))
