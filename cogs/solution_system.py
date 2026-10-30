import os
import uuid
import discord
from discord.ext import commands

SOLUTION_CHANNEL = os.getenv("SOLUTION_CHANNEL")

class SolutionThread(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.solution_channel: discord.TextChannel | None = None

    async def get_channel(self) -> discord.TextChannel | None:
        if self.solution_channel:
            return self.solution_channel
        if not SOLUTION_CHANNEL:
            print("[Solution] 未設定 SOLUTION_CHANNEL 環境變數")
            return None
        try:
            channel_id = int(SOLUTION_CHANNEL)
            channel = self.bot.get_channel(channel_id) or await self.bot.fetch_channel(channel_id)
            if isinstance(channel, discord.TextChannel):
                self.solution_channel = channel
                print(f"[Solution] 已連接頻道: {channel.name}")
                return channel
        except Exception as error:
            print(f"[Solution] 取得頻道失敗: {error}")
        return None

    async def get_starter_message(self, thread: discord.Thread) -> discord.Message | None:
        if not isinstance(thread.parent, discord.TextChannel):
            return None
        try:
            return await thread.parent.fetch_message(thread.id)
        except Exception:
            return None

    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        if interaction.type != discord.InteractionType.component or not interaction.data:
            return
        custom_id = interaction.data.get("custom_id", "")
        if not isinstance(custom_id, str) or not custom_id.startswith("solution_"):
            return
        if not isinstance(interaction.channel, discord.Thread):
            return await interaction.response.send_message("This is not a valid solution thread", ephemeral=True)

        thread = interaction.channel
        channel = await self.get_channel()
        if not channel or thread.parent_id != channel.id:
            return await interaction.response.send_message("This is not a valid solution thread", ephemeral=True)

        try:
            action, solution_id = custom_id.removeprefix("solution_").split("_", 1)
        except Exception:
            return
        if action not in ("archive", "lock", "unlock", "delete"):
            return
        if thread.name.lower() not in (f"solution-{solution_id}", f"solution-{solution_id}-archived", f"solution-{solution_id}-locked"):
            return await interaction.response.send_message("Invalid solution ID", ephemeral=True)

        # if action == "archive":
        #     if thread.archived or thread.locked or thread.name.lower().endswith(("-locked", "-archived")):
        #         return await interaction.response.send_message("This solution has already been locked or archived", ephemeral=True)
        #     await interaction.response.defer(ephemeral=True)
        #     try:
        #         await thread.edit(name=f"Solution-{solution_id}-archived", archived=True, reason=f"Solution archived by {interaction.user.name}")
        #         await interaction.followup.send("You successfully archived this solution", ephemeral=True)
        #     except discord.HTTPException as error:
        #         await interaction.followup.send(f"Failed to archive this solution: {error}", ephemeral=True)

        if action == "lock":
            if thread.locked or thread.name.lower().endswith("-locked"):
                return await interaction.response.send_message("This solution has already been locked", ephemeral=True)
            await interaction.response.defer(ephemeral=True)
            try:
                await thread.edit(name=f"Solution-{solution_id}-locked", locked=True, reason=f"Solution locked by {interaction.user.name}")
                await interaction.followup.send("You successfully locked this solution", ephemeral=True)
            except Exception as error:
                await interaction.followup.send(f"Failed to lock this solution: {error}", ephemeral=True)

        elif action == "unlock":
            if not thread.locked:
                return await interaction.response.send_message("This solution has never been locked", ephemeral=True)
            # await interaction.response.defer(ephemeral=True)
            await interaction.response.defer(ephemeral=True)
            try:
                await thread.edit(name=f"Solution-{solution_id}", archived=False, locked=False, reason=f"Solution unlocked by {interaction.user.name}")
                await interaction.followup.send("You successfully unlocked this solution", ephemeral=True)
            except Exception as error:
                await interaction.followup.send(f"Failed to unlock this solution: {error}", ephemeral=True)

        elif action == "delete":
            await interaction.response.defer(ephemeral=True)
            starter_message = await self.get_starter_message(thread)
            if not starter_message:
                return await interaction.followup.send("Cannot delete without getting starter message", ephemeral=True)
            if starter_message.author.id != interaction.user.id:
                return await interaction.followup.send("Solutions can only be deleted by their creator", ephemeral=True)

            try:
                await thread.delete(reason=f"Solution deleted by {interaction.user.name}")
                await interaction.followup.send("You successfully deleted this solution", ephemeral=True)
            except Exception as error:
                return await interaction.followup.send(f"Failed to delete this solution: {error}", ephemeral=True)

            if starter_message:
                try:
                    await starter_message.add_reaction("✅")
                except Exception:
                    pass

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or isinstance(message.channel, discord.Thread):
            return

        channel = await self.get_channel()
        if not channel or message.channel.id != channel.id:
            return
        if not message.attachments and "problem" not in message.content.lower() and "issue" not in message.content.lower() and "solution" not in message.content.lower():
            return

        solution_id = uuid.uuid4().hex[:12]
        try:
            thread = await message.create_thread(name=f"Solution-{solution_id}", reason=f"Create solution by {message.author.name}")
            view = discord.ui.View(timeout=None)
            # view.add_item(discord.ui.Button(label="Archive", style=discord.ButtonStyle.blurple, custom_id=f"solution_archive_{solution_id}"))
            view.add_item(discord.ui.Button(label="Lock", style=discord.ButtonStyle.blurple, custom_id=f"solution_lock_{solution_id}"))
            view.add_item(discord.ui.Button(label="Unlock", style=discord.ButtonStyle.blurple, custom_id=f"solution_unlock_{solution_id}"))
            view.add_item(discord.ui.Button(label="Delete", style=discord.ButtonStyle.danger, custom_id=f"solution_delete_{solution_id}"))
            embed = discord.Embed(
                title=f"Solution-{solution_id}",
                description=f'Create solution by {message.author.mention}. You can create solutions automatically if your message includes attachments, or contains "issue" or "problem"'
            )
            await thread.send(
                embed=embed,
                view=view
            )
        except Exception as error:
            print(f"[Solution] 建立討論串失敗: {error}")

async def setup(bot: commands.Bot):
    await bot.add_cog(SolutionThread(bot))