import lava_lyra

# https://github.com/littlecommandcat/Discordpy-Music/blob/main/core/player.py

# Set CustomPlayer
class CustomPlayer(lava_lyra.Player):
    def __init__(self, client, channel, *, node=None):
        super().__init__(client, channel, node=node)
        self.queue = lava_lyra.Queue()

    # Destroy player
    async def destroy(self) -> None:
        self.queue.clear()
        return await super().destroy()

    async def play_next(self, *, volume: int | None=None) -> lava_lyra.Track | None:
        # Play next song in the queue
        # if self.queue.is_empty:
        #     await self.destroy()
        #     return

        # Get next track
        track = self.queue.get()
        self.queue.put(track)

        if volume:
            await self.set_volume(volume)

        # Play the track
        return await self.play(track)