import asyncio
import json
from pathlib import Path
from typing import cast
import os

import discord
from discord.ext import commands, tasks
from dotenv import load_dotenv

from fsshclient import AsyncClient, AnnouncementId
from fsshclient.objects import News

load_dotenv()
FORUM_CHANNEL_ID = os.getenv("CHANNEL")
DATA_FILE = Path("data.json")
DEFAULT_LAST_ID = 18080


class GrabAnnounce(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.client = AsyncClient()
        self.last_id: int = self.load_last_id()
        self.channel: discord.ForumChannel | None = None
        self.grab_data.start()

    def cog_unload(self):
        if self.grab_data.is_running():
            self.grab_data.cancel()
        asyncio.create_task(self.client.close())

    def load_last_id(self) -> int:
        if not DATA_FILE.exists():
            return DEFAULT_LAST_ID

        try:
            data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
            return int(data["last_id"])
        except (json.JSONDecodeError, KeyError, ValueError, TypeError):
            return DEFAULT_LAST_ID

    def save_last_id(self):
        DATA_FILE.write_text(
            json.dumps({"last_id": self.last_id}, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

    @tasks.loop(minutes=10)
    async def grab_data(self):
        try:
            all_news = []

            for announcement_id in AnnouncementId:
                results, page = await self.client.get_news(
                    announcement_id,
                    pageinfo=True
                )
                if results:
                    all_news.extend(results)

            if not all_news:
                return

            news_map = {int(news.id): news for news in all_news}
            all_news = list(news_map.values())

            new_news = [news for news in all_news if int(news.id) > self.last_id]
            new_news.sort(key=lambda news: int(news.id))

            if not new_news:
                print(f"[公告] 沒有新公告 (Last ID: {self.last_id})")
                return

            print(f"[公告] 發現 {len(new_news)} 篇新公告")

            for news in new_news:
                news = cast(News, news)
                print(
                    f"[新公告] "
                    f"[{news.time}] "
                    f"{news.title} "
                    f"ID: {news.id}"
                )
                await self.create_forum_post(news)
                await asyncio.sleep(1)

            self.last_id = int(new_news[-1].id)
            self.save_last_id()

            print(f"[公告] Last ID 更新為 {self.last_id}")

        except Exception as e:
            print(f"[公告] 抓取失敗: {type(e).__name__}: {e}")

    async def create_forum_post(self, news: News):
        if self.channel is None:
            print("[公告] Forum Channel 尚未設定")
            return

        embed = discord.Embed(
            title=str(news.title),
            color=discord.Color.blurple(),
            description=f"```{news.content[:3500]}```",
            url=news.url
        )
        embed.add_field(name="公告時間：", value=f"> {str(news.time)}", inline=True)
        embed.add_field(name="公告單位：", value=f"> {str(news.unitname)}", inline=True)
        embed.add_field(name="點閱：", value=f"> {str(news.clicks)}", inline=True)
        embed.add_field(name="發布者：", value=f"> {news.name}({news.issuer})", inline=True)
        embed.set_footer(text=f"公告ID：{news.id}")
        if news.filecount != 0:
            embed.add_field(name="檔案數量：", value=f"> {news.filecount}")
        embed.set_thumbnail(url=news.image_url)

        try:
            await self.channel.create_thread(
                name=str(news.title)[:100],
                embed=embed
            )
            print(f"Create [{str(news.title)[:15]}]")

        except Exception as e:
            print(f"Create [{str(news.title)[:15]}] error: {e}")
            raise

    @grab_data.before_loop
    async def before_grab_data(self):
        await self.bot.wait_until_ready()

        channel = self.bot.get_channel(int(FORUM_CHANNEL_ID))
        print("[公告] Get channel")

        if not isinstance(channel, discord.ForumChannel):
            print(
                f"{FORUM_CHANNEL_ID} 不是 Discord Forum Channel"
            )

        self.channel = channel
        print(f"[公告] 已連接 Forum: {channel.name}")
        print(f"[公告] Last ID: {self.last_id}")

    async def close(self):
        await self.client.close()


async def setup(bot: commands.Bot):
    await bot.add_cog(GrabAnnounce(bot))