import nextcord as nc
from nextcord.ext import commands



class printMe(commands.Cog):

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @nc.slash_command(name="print_me", description="prints your id")
    async def print_me(self, ctx: nc.Interaction):
        name = await ctx.guild.fetch_member(id:=ctx.user.id)
        await ctx.send(f"your id is: {id}.\nYour username in this server is {name}")


def setup(bot: commands.Bot) -> None:
    bot.add_cog(printMe(bot))
