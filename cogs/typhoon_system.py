import os
import asyncio
import time
import json
from pathlib import Path

import datetime
import aiohttp
from bs4 import BeautifulSoup
import discord
from discord.ext import commands, tasks

TYPHOON_CHANNEL = os.getenv("TYPHOON_CHANNEL")
DATA_FILE = Path("typhoon_data.json")

class TyphoonAlert(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._channel: discord.TextChannel | None=None
        self._session: aiohttp.ClientSession | None=None
        self.data_grabber.start()


    async def cog_unload(self):
        if self.data_grabber.is_running(): 
            self.data_grabber.cancel()

        if isinstance(self._session, aiohttp.ClientSession) and not self._session.closed:
            await self._session.close()

    def load_data(self) -> tuple[int, str]:
        if not DATA_FILE.exists():
            return time.time(), ""

        try:
            data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
            updated_at = int(data.get("updated_at", time.time()))
            last_status = str(data.get("last_status", "尚未宣布消息"))
            return updated_at, last_status
        except (json.JSONDecodeError, KeyError, ValueError, TypeError):
            return time.time(), ""

    def save_data(self, last_status: str):
        DATA_FILE.write_text(
            json.dumps(
                {"updated_at": int(time.time()), "last_status": last_status},
                ensure_ascii=False,
                indent=2
            ),
            encoding="utf-8"
        )

    async def _get_channel(self) -> bool:
        try:
            self._channel = self.bot.get_channel(int(TYPHOON_CHANNEL)) or await self.bot.fetch_channel(TYPHOON_CHANNEL)
            if not isinstance(self._channel, discord.TextChannel):
                self._channel = None
            else:
                return True
        except:
            pass

        return False

    async def _get_kaoshuing_data(self) -> str | None:
        url = "https://www.dgpa.gov.tw/typh/daily/nds.html"

        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()

        try:
            print("[颱風] 開始連線")

            async with self._session.get(
                url,
                timeout=aiohttp.ClientTimeout(total=10),
                ssl=False # Python3.14 但我這邊用3.12
            ) as response:
                print(f"[颱風] HTTP：{response.status}")
                response.raise_for_status()
                html = await response.text(encoding="utf-8")

            soup = BeautifulSoup(html, "html.parser")
            table = soup.find("table", id="Table")

            if table is None:
                print("[颱風] 找不到資料表")
                return None

            for row in table.find_all("tr"):
                texts = [
                    col.get_text(" ", strip=True)
                    for col in row.find_all("td")
                ]

                if "高雄市" in texts:
                    index = texts.index("高雄市")
                    return texts[index + 1]

            return None

        except asyncio.TimeoutError:
            print("[颱風] 連線逾時")

        except aiohttp.ClientError as e:
            print(f"[颱風] HTTP 請求失敗：{type(e).__name__}: {e}")

        except Exception as e:
            print(f"[颱風] 未知錯誤：{type(e).__name__}: {e}")

        return None
        
    @tasks.loop(minutes=5)
    async def data_grabber(self):
        print("[颱風] 定時任務開始")
        status = await self._get_kaoshuing_data()
        if not status:
            return

        print(f"[颱風] 資料取得：{status}")

        updated_at, old_status = self.load_data()
        if old_status != status:
            self.save_data(status)
            if isinstance(self._channel, discord.TextChannel):
                embed = discord.Embed(
                    title="停班停課更新",
                    color=discord.Color.gold(),
                    timestamp=datetime.datetime.now(),
                    description=f"```{status}```"
                )
                embed.set_thumbnail(url="https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcRnMeGjOEFZNvspIVtV83u02XT9DdfAb-DeWdNlf4-QLOW4lKlDazQlFE_Z&s=10")
                embed.set_footer(text=f"更新間隔：{int(time.time() - updated_at if updated_at != 0 else 0)}s｜地區：高雄市")
                embed.add_field(
                    name="狀態變更",
                    value=f"```\n{old_status if old_status else '無狀態'} -> {status}```",
                    inline=False
                )
                await self._channel.send(embed=embed)

    @data_grabber.before_loop
    async def before_grab_data(self):
        await self.bot.wait_until_ready()
        if await self._get_channel():
            print(f"[颱風] 取得發送頻道成功")
        else:
            print(f"[颱風] 取得頻道失敗")

async def setup(bot: commands.Bot):
    await bot.add_cog(TyphoonAlert(bot))