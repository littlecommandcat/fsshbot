import asyncio
import json
from dataclasses import dataclass
from pathlib import Path
from typing import cast
import os

import aiohttp
import discord
from discord.ext import commands, tasks
from dotenv import load_dotenv

load_dotenv()
KBOOK_CHANNEL_ID = os.getenv("KBOOK_CHANNEL")
DATA_FILE = Path("kbook_data.json")
DEFAULT_LAST_ID = 0
API_URL = "https://kbook.fssh.khc.edu.tw/api/announcements"

HEADERS = {
    "Content-Type": "application/json",
    "X-KLib-Key": "Fs2026-KLib-9xmP7nQr2vBs-FsSh",
    "Referer": "https://kbook.fssh.khc.edu.tw/",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "zh-TW,zh;q=0.9,en-US;q=0.8",
}


@dataclass
class KBookAnnouncement:
    id: int
    title: str
    content: str
    is_pinned: bool
    author_name: str
    created_at: str
    updated_at: str

    @classmethod
    def from_payload(cls, payload: dict) -> "KBookAnnouncement":
        return cls(
            id=int(payload.get("id", -1)),
            title=str(payload.get("title", "")),
            content=str(payload.get("content", "")),
            is_pinned=bool(payload.get("is_pinned", False)),
            author_name=str(payload.get("author_name", "")),
            created_at=str(payload.get("created_at", "")),
            updated_at=str(payload.get("updated_at", ""))
        )


class KBookAnnounce(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.session: aiohttp.ClientSession | None = None
        self.last_id, self.seen_ids = self.load_data()
        self.channel: discord.ForumChannel | None = None
        self.grab_data.start()

    def cog_unload(self):
        if self.grab_data.is_running():
            self.grab_data.cancel()
        asyncio.create_task(self.close())

    def load_data(self) -> tuple[int, set[int]]:
        if not DATA_FILE.exists():
            return DEFAULT_LAST_ID, set()

        try:
            data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
            last_id = int(data["last_id"])
            seen_ids = {int(news_id) for news_id in data.get("seen_ids", [])}
            return last_id, seen_ids
        except (json.JSONDecodeError, KeyError, ValueError, TypeError):
            return DEFAULT_LAST_ID, set()

    def save_data(self):
        DATA_FILE.write_text(
            json.dumps(
                {"last_id": self.last_id, "seen_ids": sorted(self.seen_ids)},
                ensure_ascii=False,
                indent=2
            ),
            encoding="utf-8"
        )

    async def _init(self, *, force: bool = False) -> None:
        if self.session and not self.session.closed and not force:
            return
        if self.session:
            await self.close()
        self.session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30))

    async def close(self) -> None:
        if self.session and not self.session.closed:
            await self.session.close()

        self.session = None

    async def fetch_announcements(self) -> list[KBookAnnouncement]:
        await self._init()

        async with self.session.get(API_URL, headers=HEADERS) as resp:
            if resp.status != 200:
                print(f"[K書公告] API 回應異常: {resp.status}")
                return []

            payload = await resp.json(content_type=None)

        if not isinstance(payload, list):
            print(f"[K書公告] API 資料格式異常: {type(payload).__name__}")
            return []

        return [KBookAnnouncement.from_payload(item) for item in payload]

    @tasks.loop(minutes=10)
    async def grab_data(self):
        try:
            all_news = await self.fetch_announcements()

            if not all_news:
                return

            news_map = {int(news.id): news for news in all_news}
            all_news = list(news_map.values())

            new_news = [
                news for news in all_news
                if int(news.id) > self.last_id and int(news.id) not in self.seen_ids
            ]
            new_news.sort(key=lambda news: int(news.id))

            if not new_news:
                print(f"[K書公告] 沒有新公告 (Last ID: {self.last_id})")
                return

            print(f"[K書公告] 發現 {len(new_news)} 篇新公告")

            for news in new_news:
                news = cast(KBookAnnouncement, news)
                print(
                    f"[新K書公告] "
                    f"[{news.created_at}] "
                    f"{news.title} "
                    f"ID: {news.id}"
                )
                await self.create_forum_post(news)

                # 發布後立即記錄，避免重啟或 last_id 遺失時重複發布
                self.seen_ids.add(int(news.id))
                self.last_id = max(self.last_id, int(news.id))
                self.save_data()

                await asyncio.sleep(1)

            print(f"[K書公告] Last ID 更新為 {self.last_id}")

        except Exception as e:
            print(f"[K書公告] 抓取失敗: {type(e).__name__}: {e}")

    def build_embed(self, news: KBookAnnouncement) -> discord.Embed:
        embed = discord.Embed(
            title=str(news.title),
            color=discord.Color.blurple(),
            description=news.content[:3500] if news.content else "<None-Content>"
        )
        embed.add_field(name="公告時間：", value=f"> {str(news.created_at)}", inline=True)
        embed.add_field(name="最後更新：", value=f"> {str(news.updated_at)}", inline=True)
        embed.add_field(name="發布者：", value=f"> {str(news.author_name)}", inline=True)
        embed.add_field(
            name="置頂：",
            value=f"> {'是' if news.is_pinned else '否'}",
            inline=True
        )
        embed.set_footer(text=f"公告ID：{news.id}")
        return embed

    async def create_forum_post(self, news: KBookAnnouncement):
        if self.channel is None:
            print("[K書公告] Channel 尚未設定")
            return

        embed = self.build_embed(news)

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

        if not KBOOK_CHANNEL_ID:
            print("[K書公告] 未設定 KBOOK_CHANNEL 環境變數")
            return

        channel = self.bot.get_channel(int(KBOOK_CHANNEL_ID))
        print("[K書公告] Get channel")

        if not isinstance(channel, discord.ForumChannel):
            print(
                f"{KBOOK_CHANNEL_ID} 不是 Discord Forum Channel"
            )
            return

        self.channel = channel
        print(f"[K書公告] 已連接 Forum: {channel.name}")
        print(f"[K書公告] Last ID: {self.last_id}")


async def setup(bot: commands.Bot):
    await bot.add_cog(KBookAnnounce(bot))
