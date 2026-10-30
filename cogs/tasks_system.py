import os
import json
import time
import uuid
import re
import asyncio
from pathlib import Path
from datetime import datetime, timedelta, timezone

import discord
from discord import app_commands
from discord.ext import commands, tasks

TASKS_CHANNEL_ID = os.getenv("TASKS_CHANNEL")
TZ = timezone(timedelta(hours=8))

WEEKDAY_MAP = {
    "mon": 0, "tue": 1, "wed": 2, "thu": 3,
    "fri": 4, "sat": 5, "sun": 6,
}
WEEKDAY_NAMES = ["一", "二", "三", "四", "五", "六", "日"]
REPEAT_CHOICES = {
    "none": "不重複",
    "daily": "每天",
    "weekly_mon": "每週一",
    "weekly_tue": "每週二",
    "weekly_wed": "每週三",
    "weekly_thu": "每週四",
    "weekly_fri": "每週五",
    "weekly_sat": "每週六",
    "weekly_sun": "每週日",
}


class TaskSystem(commands.Cog):
    task = app_commands.Group(name="task", description="定時任務管理")

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.tasks_channel: discord.TextChannel | None = None
        self._data_file = Path("tasks_data.json")
        self._lock = asyncio.Lock()

    def load_data(self) -> dict:
        if not self._data_file.exists():
            return {"tasks": []}
        try:
            data = json.loads(self._data_file.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {"tasks": []}
        except (json.JSONDecodeError, ValueError, TypeError):
            return {"tasks": []}

    def save_data(self, data: dict):
        self._data_file.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def get_tasks(self) -> list[dict]:
        return self.load_data().get("tasks", [])

    def parse_time(self, value: str) -> int | None:
        try:
            dt = datetime.strptime(value, "%Y-%m-%d %H:%M")
            return int(dt.replace(tzinfo=TZ).timestamp())
        except ValueError:
            return None

    def valid_time(self, timestamp: int) -> bool:
        return timestamp >= int(time.time()) + 60

    def normalize_timestamp(self, value) -> int | None:
        try:
            timestamp = int(value)
            if timestamp > 9999999999:
                timestamp //= 1000
            return timestamp
        except (TypeError, ValueError):
            return None

    def clean_tasks(self, data: dict) -> bool:
        current = int(time.time())
        original = data.get("tasks", [])
        remaining = [
            task for task in original
            if (timestamp := self.normalize_timestamp(task.get("timestamp"))) is not None
            and timestamp > current
        ]
        if len(remaining) != len(original):
            data["tasks"] = remaining
            return True
        return False

    @staticmethod
    def parse_repeat(value: str) -> tuple[str | None, int | None]:
        if value == "daily":
            return "daily", None
        if value.startswith("weekly_"):
            suffix = value.split("_", 1)[1]
            return "weekly", WEEKDAY_MAP.get(suffix)
        return None, None

    @staticmethod
    def describe_repeat(repeat, weekday) -> str:
        if repeat == "daily":
            return "每天"
        if repeat == "weekly" and weekday is not None:
            return f"每週{WEEKDAY_NAMES[weekday]}"
        return "不重複"

    @staticmethod
    def compute_next_time(timestamp: int, repeat, weekday) -> int | None:
        if repeat == "daily":
            return timestamp + 86400
        if repeat == "weekly" and weekday is not None:
            dt = datetime.fromtimestamp(timestamp, TZ)
            days_ahead = (weekday - dt.weekday()) % 7
            if days_ahead == 0:
                days_ahead = 7
            return timestamp + days_ahead * 86400
        return None

    async def repeat_autocomplete(self, interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
        current = current.lower()
        return [
            app_commands.Choice(name=label, value=value)
            for value, label in REPEAT_CHOICES.items()
            if current in label.lower() or current in value
        ]

    async def time_autocomplete(self, interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
        now = datetime.now(TZ).replace(second=0, microsecond=0)
        current = current.strip().lower()
        choices = []
        time_match = re.search(r"(\d{1,2}):(\d{2})", current)
        if time_match:
            hour, minute = int(time_match.group(1)), int(time_match.group(2))
            if hour < 24 and minute < 60:
                for day_offset in range(7):
                    candidate = (now + timedelta(days=day_offset)).replace(
                        hour=hour, minute=minute, second=0, microsecond=0
                    )
                    if candidate >= now:
                        text = candidate.strftime("%Y-%m-%d %H:%M")
                        label = candidate.strftime("%m/%d %H:%M")
                        choices.append(app_commands.Choice(name=label, value=text))
                        if len(choices) >= 25:
                            break
                return choices
            
        candidates = []
        for day_offset in range(5):
            day_start = (now + timedelta(days=day_offset)).replace(hour=0, minute=0, second=0, microsecond=0)
            for hour in range(0, 24, 2):
                candidates.append(day_start.replace(hour=hour, minute=0))
        candidates.append((now + timedelta(hours=1)).replace(minute=0))
        candidates = sorted({c for c in candidates if c >= now})
        for c in candidates:
            text = c.strftime("%Y-%m-%d %H:%M")
            label = c.strftime("%m/%d %H:%M")
            if current in text or current in label:
                choices.append(app_commands.Choice(name=label, value=text))
            if len(choices) >= 25:
                break
        return choices


    async def task_autocomplete(self, interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
        async with self._lock:
            data = self.load_data()
            self.clean_tasks(data)
            self.save_data(data)
            task_list = data.get("tasks", [])
        current = current.lower()
        now = int(time.time())
        choices = []
        for task in task_list:
            timestamp = self.normalize_timestamp(task.get("timestamp"))
            if timestamp is None or timestamp <= now:
                continue
            task_id = str(task.get("id", ""))
            title = str(task.get("title", "未命名任務"))
            if current not in title.lower() and current not in task_id.lower():
                continue
            display_time = datetime.fromtimestamp(timestamp, TZ).strftime("%m/%d %H:%M")
            choices.append(app_commands.Choice(name=f"{title[:60]} | {display_time}", value=task_id))
            if len(choices) >= 25:
                break
        return choices

    async def get_channel(self) -> discord.TextChannel | None:
        if self.tasks_channel:
            return self.tasks_channel
        if not TASKS_CHANNEL_ID:
            print("[Task] 未設定 TASKS_CHANNEL 環境變數")
            return None
        try:
            channel_id = int(TASKS_CHANNEL_ID)
            channel = self.bot.get_channel(channel_id) or await self.bot.fetch_channel(channel_id)
            if isinstance(channel, discord.TextChannel):
                self.tasks_channel = channel
                print(f"[Task] 已連接頻道: {channel.name}")
                return channel
        except (discord.HTTPException, ValueError) as error:
            print(f"[Task] 取得頻道失敗: {type(error).__name__}: {error}")
        return None

    async def cog_load(self):
        if not self.tasks_manager.is_running():
            self.tasks_manager.start()
            print("[Task] 任務管理器已啟動")

    async def cog_unload(self):
        self.tasks_manager.cancel()
        print("[Task] 任務管理器已停止")

    @tasks.loop(minutes=1)
    async def tasks_manager(self):
        async with self._lock:
            data = self.load_data()
            task_list = data.get("tasks", [])
            if not task_list:
                return
            now = int(time.time())
            channel = await self.get_channel()
            if not channel:
                return
            remaining = []
            for task in task_list:
                timestamp = self.normalize_timestamp(task.get("timestamp"))
                if timestamp is None:
                    continue
                if timestamp > now:
                    remaining.append(task)
                    continue
                if channel is None:
                    continue
                content = task.get("content")
                if not content:
                    continue
                title = task.get("title", "未命名任務")
                author_id = task.get("author_id", 0)
                mentions = task.get("mentions", [])
                author_name = "Unknown Member"
                avatar_url = None
                if author_id:
                    try:
                        user = self.bot.get_user(int(author_id)) or await self.bot.fetch_user(int(author_id))
                        author_name = user.name
                        avatar_url = user.display_avatar.url
                    except (discord.HTTPException, ValueError):
                        pass

                markdown = task.get("markdown", False)
                embed = discord.Embed(
                    title=title,
                    description=content if markdown else f"```{content}```",
                    color=discord.Color.blue(),
                    timestamp=datetime.fromtimestamp(timestamp, timezone.utc),
                )
                embed.set_author(name=author_name, icon_url=avatar_url)
                embed.set_footer(text=f"{author_name}｜定時任務", icon_url=avatar_url)
                mentions_message = " ".join(
                    str(m) if str(m).startswith("<@") else f"<@&{m}>"
                    for m in mentions
                )
                try:
                    await channel.send(
                        content=mentions_message or None,
                        embed=embed,
                        allowed_mentions=discord.AllowedMentions(everyone=False, users=True, roles=True),
                    )
                    print(f"[Task] 已送出任務: {title}")
                except discord.HTTPException as error:
                    print(f"[Task] 送出任務失敗: {type(error).__name__}: {error}")
                next_time = self.compute_next_time(timestamp, task.get("repeat"), task.get("weekday"))
                if next_time is not None:
                    next_task = dict(task)
                    next_task["timestamp"] = next_time
                    next_task["id"] = uuid.uuid4().hex[:12]
                    remaining.append(next_task)
                    repeat_desc = self.describe_repeat(task.get("repeat"), task.get("weekday"))
                    print(f"[Task] 循環任務已排程: {title} ({repeat_desc}) -> {datetime.fromtimestamp(next_time, TZ).strftime('%Y-%m-%d %H:%M')}")
            data["tasks"] = remaining
            self.save_data(data)

    @tasks_manager.before_loop
    async def before_tasks_manager(self):
        await self.bot.wait_until_ready()
        now = datetime.now(timezone.utc)
        next_minute = (now.replace(second=0, microsecond=0) + timedelta(minutes=1))
        delay = (next_minute - now).total_seconds()
        if delay > 0:
            await asyncio.sleep(delay)
        print("[Task] 任務管理器準備中...")

    @task.command(name="add", description="新增定時任務")
    @app_commands.describe(
        title="任務標題",
        content="任務內容",
        execute_time="執行時間（可用自動建議）",
        repeat="循環選項（不重複 / 每天 / 每週X）",
        mention="要通知的身分組",
        markdown="是否需要markdown"
    )
    @app_commands.autocomplete(execute_time=time_autocomplete)
    @app_commands.autocomplete(repeat=repeat_autocomplete)
    async def task_add(self, interaction: discord.Interaction, title: str, content: str, execute_time: str, repeat: str = "none", mention: discord.Role | None = None, markdown: bool=False):
        timestamp = self.parse_time(execute_time)
        if timestamp is None:
            await interaction.response.send_message("時間格式錯誤，請使用`YYYY-MM-DD HH:MM`")
            return
        if not self.valid_time(timestamp):
            await interaction.response.send_message("執行時間必須至少在目前時間的1分鐘後")
            return
        repeat_mode, weekday = self.parse_repeat(repeat)
        task_id = uuid.uuid4().hex[:12]
        new_task = {
            "id": task_id,
            "title": title,
            "content": content,
            "timestamp": timestamp,
            "author_id": interaction.user.id,
            "mentions": [str(mention.id)] if mention else [],
            "repeat": repeat_mode,
            "weekday": weekday,
            "markdown": markdown
        }
        async with self._lock:
            data = self.load_data()
            self.clean_tasks(data)
            data.setdefault("tasks", []).append(new_task)
            self.save_data(data)
        repeat_desc = self.describe_repeat(repeat_mode, weekday)
        print(f"[Task] 建立任務: {title} (ID: {task_id}, 循環: {repeat_desc})")
        embed = discord.Embed(title="任務建立成功", color=discord.Color.green())
        embed.add_field(name="標題", value=title, inline=False)
        embed.add_field(name="內容", value=content[:1024] if markdown else f"```{content[:1024]}```", inline=False)
        embed.add_field(name="執行時間", value=f"<t:{timestamp}:F> (<t:{timestamp}:R>)", inline=False)
        embed.add_field(name="循環", value=repeat_desc, inline=False)
        embed.add_field(name="任務 ID", value=f"`{task_id}`", inline=False)
        await interaction.response.send_message(embed=embed)

    @task.command(name="remove", description="刪除定時任務")
    @app_commands.describe(task_id="選擇要刪除的任務")
    @app_commands.autocomplete(task_id=task_autocomplete)
    async def task_remove(self, interaction: discord.Interaction, task_id: str):
        async with self._lock:
            data = self.load_data()
            self.clean_tasks(data)
            task_list = data.get("tasks", [])
            target = next((task for task in task_list if task.get("id") == task_id), None)
            if target is None:
                self.save_data(data)
                await interaction.response.send_message("找不到該任務，可能已過期或被刪除")
                return
            if target.get("author_id") != interaction.user.id and not interaction.user.guild_permissions.manage_guild:
                await interaction.response.send_message("你只能刪除自己的任務")
                return
            data["tasks"] = [task for task in task_list if task.get("id") != task_id]
            self.save_data(data)
        print(f"[Task] 刪除任務: {target.get('title')} (ID: {task_id})")
        await interaction.response.send_message(f"已刪除任務：**{target.get('title')}**")

    @task.command(name="list", description="查看所有註冊待執行任務")
    async def task_list(self, interaction: discord.Interaction):
        async with self._lock:
            data = self.load_data()
            self.clean_tasks(data)
            self.save_data(data)
            task_list = sorted(
                data.get("tasks", []),
                key=lambda t: self.normalize_timestamp(t.get("timestamp")) or 0,
            )
        if not task_list:
            await interaction.response.send_message("目前沒有待執行任務")
            return
        repeat_tasks = [t for t in task_list if t.get("repeat")]
        oneoff_tasks = [t for t in task_list if not t.get("repeat")]
        embed = discord.Embed(title="待執行任務", color=discord.Color.blue())

        def add_section(title: str, tasks: list[dict]):
            if not tasks:
                return
            blocks = [self._format_task(task) for task in tasks]
            for i in range(0, len(blocks), 5):
                embed.add_field(
                    name=title if i == 0 else f"{title}（續）",
                    value="\n\n".join(blocks[i:i + 5]),
                    inline=False,
                )

        add_section(f"循環任務（{len(repeat_tasks)}）", repeat_tasks)
        add_section(f"單次任務（{len(oneoff_tasks)}）", oneoff_tasks)
        total = len(task_list)
        if total > 20:
            embed.set_footer(text=f"共{total}個任務，僅顯示前20個")
        await interaction.response.send_message(embed=embed)

    def _format_task(self, task: dict) -> str:
        timestamp = self.normalize_timestamp(task.get("timestamp"))
        repeat_desc = self.describe_repeat(task.get("repeat"), task.get("weekday"))
        line = f"**{task.get('title', '未命名任務')}**\n<t:{timestamp}:F>\n<t:{timestamp}:R>\n`{task.get('id', '無')}`"
        if repeat_desc != "不重複":
            line += f"\n{repeat_desc}"
        return line

    @task.command(name="edit", description="修改定時任務")
    @app_commands.describe(
        task_id="選擇要修改的任務",
        title="新的任務標題",
        content="新的任務內容",
        execute_time="新的執行時間（可用自動建議）",
        repeat="新的循環選項",
        markdown="是否使用markdown"
    )
    @app_commands.autocomplete(task_id=task_autocomplete)
    @app_commands.autocomplete(execute_time=time_autocomplete)
    @app_commands.autocomplete(repeat=repeat_autocomplete)
    async def task_edit(
        self,
        interaction: discord.Interaction,
        task_id: str,
        title: str | None = None,
        content: str | None = None,
        execute_time: str | None = None,
        repeat: str | None = None,
        markdown: bool=False
    ):
        timestamp = None
        if execute_time is not None:
            timestamp = self.parse_time(execute_time)
            if timestamp is None:
                await interaction.response.send_message("時間格式錯誤")
                return
            if not self.valid_time(timestamp):
                await interaction.response.send_message("新時間必須至少在目前時間的 1 分鐘後")
                return
        async with self._lock:
            data = self.load_data()
            self.clean_tasks(data)
            target = next((task for task in data.get("tasks", []) if task.get("id") == task_id), None)
            if target is None:
                self.save_data(data)
                await interaction.response.send_message("找不到該任務")
                return
            if target.get("author_id") != interaction.user.id and not interaction.user.guild_permissions.manage_guild:
                await interaction.response.send_message("你只能修改自己的任務")
                return
            if title is not None:
                target["title"] = title
            if content is not None:
                target["content"] = content
            if timestamp is not None:
                target["timestamp"] = timestamp
            if repeat is not None:
                repeat_mode, weekday = self.parse_repeat(repeat)
                target["repeat"] = repeat_mode
                target["weekday"] = weekday
            target["markdown"] = markdown
            self.save_data(data)
        print(f"[Task] 更新任務: {target.get('title')} (ID: {task_id})")
        await interaction.response.send_message(f"已更新任務：**{target.get('title')}**")


async def setup(bot: commands.Bot):
    await bot.add_cog(TaskSystem(bot))
