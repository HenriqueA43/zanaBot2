from __future__ import annotations

import nextcord as nc 
from nextcord.ext import commands
import logging
import re
import difflib
import aiohttp
from bs4 import BeautifulSoup as bs 

logger = logging.getLogger(__name__)


_WIKI_TIMEOUT = aiohttp.ClientTimeout(total=5)

wikilink    = "http://www.poewiki.net/wiki/"
wikipure    = "http://www.poewiki.net/"
searchlink  = "http://www.poewiki.net/w/api.php"

wikilink2   = "http://www.poe2wiki.net/wiki/"
wikipure2   = "http://www.poe2wiki.net/"
searchlink2 = "http://www.poe2wiki.net/w/api.php"

_WIKIS = {
    "poe": [wikilink, wikipure, searchlink, "Wiki: "],
    "poe2": [wikilink2, wikipure2, searchlink2, "Wiki POE2: "]
}


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

async def create_embed_from_wiki(title: str, url: str, source: str = "poe") -> nc.Embed:
    wikipure_internal = _WIKIS[source][1]
    async with aiohttp.ClientSession(timeout=_WIKI_TIMEOUT) as session:
        async with session.get(url) as resp:
            if resp.status == 200:
                data = await resp.text()
                soup = bs(data, 'html.parser')
                allp = soup.find('div', class_='mw-parser-output').find_all('p')
                text_snippet = '\n'.join([p.get_text() for p in allp])
                if len(text_snippet) > 700:
                    text_snippet = text_snippet[:700] + '...' # grabs 700 initial characters
                # checks if there is an item card
                title_embed = _WIKIS[source][3]
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

class WikiCommands(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot


    async def _lookup_and_reply(self, ctx: nc.Interaction, query:str, source: str = "poe"):
        cfg = _WIKIS[source]
        logger.info(f"User {ctx.user} searched for {query} for {source}")
        await ctx.response.defer(ephemeral=True)
        try:
            url = f"{cfg[0]}{query.replace(" ", "_")}"
            embed = await create_embed_from_wiki(query, url, source)
        except Exception as e:
            logger.warning(f"{cfg[3]} failed. {e}")
            return await ctx.followup.send("Search failed. please try again later", ephemeral=True)
        if embed is None:
            return await ctx.followup.send("No wiki page found for {url}.", ephemeral=True)
        await ctx.followup.send(embed=embed, ephemeral=True)

    async def _autocomplete_helper(self, ctx: nc.Interaction, current: str, source: str = "poe"):
        current = current.strip()
        if not current:
            return []
        return await search_wiki_titles(current, limit = 5, searchlink_internal=_WIKIS[source][2])

    @nc.slash_command(name="wiki", description="Searches poewiki.net for the term.")
    async def wiki(self, ctx: nc.Interaction, query: str):
        await self._lookup_and_reply(ctx, query, "poe")

    @wiki.on_autocomplete("query")
    async def wiki_autocomplete(self, ctx: nc.Interaction, current: str):
        return await self._autocomplete_helper(ctx, current, "poe")

    @nc.slash_command(name="wiki2", description="Searches poewiki.net for the term.")
    async def wiki2(self, ctx: nc.Interaction, query: str):
        await self._lookup_and_reply(ctx, query, "poe2")

    @wiki2.on_autocomplete("query")
    async def wiki2_autocomplete(self, ctx: nc.Interaction, current: str):
        return await self._autocomplete_helper(ctx, current, "poe2")
    

    async def _reply_inline_wiki(self, msg: nc.message.Message, pattern: str, source: str):
        cfg = _WIKIS[source]
        if msg.author.bot or not (matches:=match_all(pattern, msg.content)):
            return
        logger.info(f"User {msg.author} searched for {m} in {source} wiki.")
        for m in matches[:10]:
            if ret := await search_wiki_titles(m,limit = 5, searchlink_internal=cfg[2]):
                url = f"{cfg[0]}{ret[0].replace(' ', '_')}"
                if embed := await create_embed_from_wiki(ret[0], url, source):
                    await msg.channel.send(embed=embed)


    @commands.Cog.listener(name="on_message")
    async def poe1wiki(self, msg: nc.message.Message):
        await self._reply_inline_wiki(msg, r'\[\[([^<\]]*?)\]\]', "poe")

    @commands.Cog.listener(name="on_message")
    async def poe2wiki(self, msg: nc.message.Message):
        await self._reply_inline_wiki(msg, r'<<([^<\]]*?)>>', "poe2")

def setup(bot: commands.Bot):
    bot.add_cog(WikiCommands(bot))
