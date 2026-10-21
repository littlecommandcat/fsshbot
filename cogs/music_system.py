import os
import asyncio

import discord
import lava_lyra
from discord.ext import commands
from dotenv import load_dotenv
from lava_lyra.exceptions import NodeConnectionFailure, NodeCreationError, NoNodesAvailable

from core import CustomPlayer

load_dotenv()

MUSIC_CHANNEL = os.getenv("MUSIC_CHANNEL")
LAVALINK_HOST = os.getenv("LAVALINK_HOST", "localhost").strip()
LAVALINK_PORT = int(os.getenv("LAVALINK_PORT", 443))
LAVALINK_PASSWORD = os.getenv("LAVALINK_PASSWORD", "youshallnotpass")

if LAVALINK_HOST.startswith("https://"):
    LAVALINK_SECURE = True
    LAVALINK_HOST = LAVALINK_HOST[len("https://"):]
elif LAVALINK_HOST.startswith("http://"):
    LAVALINK_SECURE = False
    LAVALINK_HOST = LAVALINK_HOST[len("http://"):]
else:
    LAVALINK_SECURE = LAVALINK_PORT == 443

LAVALINK_HOST = LAVALINK_HOST.rstrip("/")
MUSIC_URL = "https://www.youtube.com/watch?v=sYa0hBivU-8"


class MusicSystem(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.pool = lava_lyra.NodePool()
        self.node: lava_lyra.Node | None = None
        self.music_channel: discord.VoiceChannel | None = None
        self._setup_task: asyncio.Task | None = None
        self._reconnect_task: asyncio.Task | None = None
        self._node_ready = False
        self._connect_lock = asyncio.Lock()

    async def cog_load(self):
        self._setup_task = asyncio.create_task(self._setup_node())

    async def cog_unload(self):
        for task in (self._setup_task, self._reconnect_task):
            if task and not task.done():
                task.cancel()

    async def _setup_node(self):
        await self.bot.wait_until_ready()
        print("[Music] Bot ready, initializing Lavalink")

        try:
            self.node = await self.create_node()
            self._node_ready = True
            await self.setup_channel()
        except asyncio.CancelledError:
            raise
        except Exception as error:
            self._node_ready = False
            print(f"[Music] Initialization failed: {error!r}")

    async def create_node(self) -> lava_lyra.Node:
        try:
            node = await self.pool.create_node(
                bot=self.bot,
                host=LAVALINK_HOST,
                port=LAVALINK_PORT,
                password=LAVALINK_PASSWORD,
                secure=LAVALINK_SECURE,
                identifier="MUSIC",
                lyrics=False,
                search=False,
                fallback=False,
            )
            print(f"[Music] Created node: {node._identifier}")
            return node
        except NodeCreationError as error:
            print(f"[Music] Node creation error: {error!r}")
            raise
        except NodeConnectionFailure as error:
            print(f"[Music] Node connection error: {error!r}")
            raise
        except Exception as error:
            print(f"[Music] Unexpected node error: {error!r}")
            raise

    async def wait_for_node(self, timeout: float = 30.0):
        loop = asyncio.get_running_loop()
        deadline = loop.time() + timeout

        while loop.time() < deadline:
            try:
                node = lava_lyra.NodePool.get_node()
                print(f"[Music] Available node: {node._identifier}")
                return node
            except NoNodesAvailable:
                await asyncio.sleep(1)

        raise TimeoutError("Lavalink node did not become available")

    async def setup_channel(self):
        if not MUSIC_CHANNEL:
            print("[Music] MUSIC_CHANNEL is not configured")
            return

        try:
            channel_id = int(MUSIC_CHANNEL)
            channel = self.bot.get_channel(channel_id) or await self.bot.fetch_channel(channel_id)
        except Exception as error:
            print(f"[Music] Failed to fetch channel: {error!r}")
            return

        if not isinstance(channel, discord.VoiceChannel):
            print(f"[Music] {MUSIC_CHANNEL} is not a voice channel")
            return

        self.music_channel = channel
        await self.wait_for_node()
        await self.join_music(channel.guild)

    async def get_music(self, player: CustomPlayer) -> lava_lyra.Track | None:
        try:
            tracks = await player.get_tracks(MUSIC_URL)
            if not tracks:
                print("[Music] No tracks found")
                return None
            return tracks[0]
        except Exception as error:
            print(f"[Music] Failed to load music: {error!r}")
            return None

    async def join_music(self, guild: discord.Guild):
        if not self._node_ready:
            print("[Music] Lavalink node is not ready")
            return

        if not self.music_channel or guild.id != self.music_channel.guild.id:
            return

        async with self._connect_lock:
            try:
                player = guild.voice_client

                if not isinstance(player, CustomPlayer):
                    if player is not None:
                        await player.disconnect(force=True)

                    player = await self.music_channel.connect(cls=CustomPlayer, reconnect=True)
                    print(f"[Music] Connected to voice channel: {self.music_channel.name}")
                elif player.channel != self.music_channel:
                    await player.move_to(self.music_channel)

                if player.is_playing:
                    return

                music = await self.get_music(player)
                if music is None:
                    return

                player.queue.put(music)
                await player.play_next(volume=50)
                print("[Music] Music playback started")
            except asyncio.CancelledError:
                raise
            except Exception as error:
                print(f"[Music] Failed to join music channel: {error!r}")

    @commands.Cog.listener()
    async def on_lyra_node_connected(self, node_id: str, is_nodelink: bool, reconnect: bool):
        print(f"[Music] Node connected: {node_id} | NodeLink: {is_nodelink} | Reconnect: {reconnect}")

    @commands.Cog.listener()
    async def on_lyra_track_end(self, player: CustomPlayer, track: lava_lyra.Track, reason: str):
        if not isinstance(player, CustomPlayer):
            return

        try:
            await player.play_next()
        except Exception as error:
            print(f"[Music] Failed to play next track: {error!r}")

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        if not self.music_channel or self.bot.user is None:
            return

        if member.id != self.bot.user.id or before.channel is None or after.channel is not None:
            return

        if self.bot.is_closed():
            return

        if self._reconnect_task and not self._reconnect_task.done():
            return

        self._reconnect_task = asyncio.create_task(self._reconnect_music())

    async def _reconnect_music(self):
        await asyncio.sleep(3)

        if self.bot.is_closed() or not self.music_channel:
            return

        try:
            await self.wait_for_node()
            await self.join_music(self.music_channel.guild)
        except asyncio.CancelledError:
            raise
        except Exception as error:
            print(f"[Music] Reconnect failed: {error!r}")


async def setup(bot: commands.Bot):
    await bot.add_cog(MusicSystem(bot))