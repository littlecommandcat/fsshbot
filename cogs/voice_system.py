import os
import asyncio

import discord
from discord.ext import commands

DYNAMIC_CHANNEL = os.getenv("DYNAMIC_CHANNEL")

class DynamicVoice(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.endcmd = "-dynamic-voice"

    async def clean_up_dynamic(self, guild: discord.Guild):
        vcchannels = guild.voice_channels
        if not vcchannels:
            return
        
        for vcchannel in vcchannels:
            if not vcchannel.name.endswith(self.endcmd):
                continue

            if len([m for m in vcchannel.members if not m.bot]) == 0:
                await vcchannel.delete(reason="Delete dynamic voice channel")
                print(f"Delete dynamic voice: {vcchannel.name}")
                await asyncio.sleep(0.3)

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        if not DYNAMIC_CHANNEL:
            return
        
        if not member.guild.me.guild_permissions.manage_channels or not member.guild.me.guild_permissions.move_members:
            print("No permission for bot to manage")
            return

        await self.clean_up_dynamic(member.guild)
        
        if after.channel is not None:
            channel = after.channel
            if str(channel.id) == str(DYNAMIC_CHANNEL):
                dy_channel = await channel.category.create_voice_channel(f"{member.name}{self.endcmd}", reason="Create dynamic voice channel")
                await member.move_to(dy_channel)
                print(f"Create dynamic voice: {channel.name}")

        elif (before.channel is not None and after.channel is None) or (before.channel is not None and after.channel is not None and before.channel != after.channel):
            channel = before.channel
            if not channel.name.endswith(self.endcmd):
                return
            
            if len([m for m in channel.members if not m.bot]) != 0:
                return

            await channel.delete(reason="Delete dynamic voice channel")
            print(f"Delete dynamic voice: {channel.name}")


async def setup(bot: commands.Bot):
    await bot.add_cog(DynamicVoice(bot))