from __future__ import annotations

import nextcord as nc 
from nextcord.ext import commands
import logging
import re
import difflib
import aiohttp
from bs4 import BeautifulSoup as bs 

logger = logging.getLogger(__name__)

wikilink    = "http://www.poewiki.net/wiki/"
wikipure    = "http://www.poewiki.net/"
searchlink  = "http://www.poewiki.net/w/api.php"

wikilink2   = "http://www.poe2wiki.net/wiki/"
wikipure2   = "http://www.poe2wiki.net/"
searchlink2 = "http://www.poe2wiki.net/w/api.php"

def match_all(reg: str, string) -> list[str]:
    m = re.findall(reg, string)
    return m if m else []

# Searches the wiki for titles, given a query
async def search_wiki_titles(query: str, limit: int = 15, searchlink_internal: str = searchlink) -> list[str]:
    """Search the POE wiki for titles matching any of the words in `query`.

    Returns a list of (title, score) tuples ordered by descending score.
    The scoring considers both string similarity and how many query words appear in the title.
    """
    query = (query or "").strip()
    if not query:
        return []

    words = [w for w in re.split(r"\s+", query.lower()) if w]
    # Build a search that matches any of the words in the title (prefix match)
    if words:
        srsearch = " OR ".join([f"intitle:{w}*" for w in words])
    else:
        srsearch = query

    titles = []
    async with aiohttp.ClientSession() as session:
        async with session.get(
            searchlink_internal,
            params={
                "action": "query",
                "list": "search",
                "srsearch": srsearch,
                "srlimit": limit,
                "format": "json"
            }
) as resp:
            if resp.status == 200:
                data = await resp.json()
                results = data.get("query", {}).get("search", [])
                more = [s.get('title') for s in results if s.get('title') and not re.search(r"may refer to", s.get('snippet', ''))]
                titles.extend(more)

    # deduplicate while preserving order
    seen = set()
    uniq = []
    for t in titles:
        if t not in seen:
            seen.add(t)
            uniq.append(t)

    # rank: combine sequence matcher ratio and word overlap
    ranked = []
    qlow = query.lower()
    for t in uniq:
        tlow = t.lower()
        ratio = difflib.SequenceMatcher(a=qlow, b=tlow).ratio()
        words_in = sum(1 for w in words if w in tlow)
        overlap = words_in / max(len(words), 1)
        score = ratio * 0.6 + overlap * 0.4
        ranked.append((t, score))

    ranked.sort(key=lambda x: x[1], reverse=True)
    # returns only the titles in rankingorder
    return [r[0] for r in ranked] 

async def create_embed_from_wiki(title: str, url: str, poe2: bool = False) -> nc.Embed:
    wikipure_internal = wikipure if not poe2 else wikipure2 
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status == 200:
                data = await resp.text()
                soup = bs(data, 'html.parser')
                allp = soup.find('div', class_='mw-parser-output').find_all('p')
                text_snippet = '\n'.join([p.get_text() for p in allp])
                if len(text_snippet) > 700:
                    text_snippet = text_snippet[:700] + '...' # grabs 700 initial characters
                # checks if there is an item card
                title_embed = f"Wiki: {title}" if not poe2 else f"Wiki poe2: {title}"
                embed = nc.Embed(
                    color=nc.Color.blurple(),
                    title=title_embed,
                    description=text_snippet,
                    url=url
                )
                item_card = soup.find('div', class_="infobox-page-container")
                item_card = item_card.find("span", class_ = lambda c: c and c.startswith("item-box")) if item_card else None
                if item_card:
                    imglink = item_card.find('img').get('src').strip('/')
                    logger.info(f"image: {wikipure_internal}{imglink}")
                    embed.set_image(url=f"{wikipure_internal}{imglink}")
            else:
                return None
    return embed

class wiki_cogs(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @nc.slash_command(name="wiki", description="Searches poewiki.net for the term.")
    async def wiki(self, ctx: nc.Interaction, query: str):
        # tells discord to wait while it process.
        await ctx.response.defer(ephemeral=True)
        try:
            url = f"{wikilink}{query.replace(' ', '_')}"
            embed = await create_embed_from_wiki(query, url)
        except Exception as e:
            await ctx.followup.send("Search failed. please try again later")
            logger.warning(f"Wiki1 failed with message: {e}")
            return
        logger.info(f"User {ctx.user} searched wiki1 for {query}")
        await ctx.followup.send(embed=embed, ephemeral=True)

    @wiki.on_autocomplete("query")
    async def wiki_autocomplete(self, ctx: nc.Interaction, current: str):
        current = current.strip()
        if not current:
            return []
        ranked = await search_wiki_titles(current, limit=5)
        return ranked

    @nc.slash_command(name="wiki2", description="Searches poewiki.net for the term.")
    async def wiki2(self, ctx: nc.Interaction, query: str):
        # tells discord to wait while it process.
        await ctx.response.defer(ephemeral=True)
        try:
            url = f"{wikilink2}{query.replace(' ', '_')}"
            embed = await create_embed_from_wiki(query, url)
        except Exception as e:
            await ctx.followup.send("Search failed. please try again later")
            logger.warning(f"Wiki2 failed with message: {e}")
            return
        logger.info(f"User {ctx.user} searched wiki2 for {query}")
        await ctx.followup.send(embed=embed, ephemeral=True)

    @wiki2.on_autocomplete("query")
    async def wiki2_autocomplete(self, ctx: nc.Interaction, current: str):
        current = current.strip()
        if not current:
            return []
        ranked = await search_wiki_titles(current, limit=5, searchlink_internal=searchlink2)
        return ranked
    

    @commands.Cog.listener(name="on_message")
    async def poe1wiki(self, msg: nc.message.Message):
        if msg.author == self.bot.user:
            return
        if matches:=match_all(r'\[\[([^<\]]*?)\]\]', msg.content):
            logger.info(f'Got poe1 message: author={msg.author}, query={msg.content}')
            for m in matches:
                if ret := await search_wiki_titles(m, limit=5):
                    wiki_link_exists = f'{wikilink}{ret[0].replace(' ', '_')}'
                    if embed := await create_embed_from_wiki(ret[0], wiki_link_exists, False):
                        await msg.channel.send(embed=embed)

    @commands.Cog.listener(name="on_message")
    async def poe2wiki(self, msg: nc.message.Message):
        if msg.author == self.bot.user:
            return
        if matches:=match_all(r'<<([^<\]]*?)>>', msg.content):
            logger.info(f'Got poe2 message: author={msg.author}, query={msg.content}')
            for m in matches:
                if ret := await search_wiki_titles(m, limit=5):
                    wiki_link_exists = f'{wikilink2}{ret[0].replace(' ', '_')}'
                    if embed := await create_embed_from_wiki(ret[0], wiki_link_exists, True):
                        await msg.channel.send(embed=embed)
           
def setup(bot: commands.Bot):
    bot.add_cog(wiki_cogs(bot))
