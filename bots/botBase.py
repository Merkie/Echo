import asyncio
import discord
import time

from discord.ext import commands, tasks

from minecraft.networking.packets import Packet, serverbound

class botBase(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.channel = None
        self.forward_task.start()
        self.last_mess = 0

    @commands.Cog.listener()
    async def on_ready(self):
        print("[ Connected to Discord ]")
        self.channel = self.bot.get_channel(self.bot.config["CHANNELID"])

    @commands.Cog.listener('on_message')
    async def on_message(self, message):
        if message.author.id == self.bot.user.id:
            return
        if message.channel.id == self.channel.id:
            print(f"<{message.author}> {message.content}")
            msg = f"<{message.author}> {message.content}"
            if len(msg) > 100: # Isn't max chat len 128 or 256?
                await message.add_reaction("❌")
            elif time.time() - self.last_mess < 3:
                await message.add_reaction("⏳")
            else:
                packet = serverbound.play.ChatPacket()
                packet.message = msg
                self.bot.connection.write_packet(packet)
                self.last_mess = time.time()

    @tasks.loop(seconds=0.5) # On tick, maybe too fast?
    async def forward_task(self):
        # Shit but at least this never stops
        #   To better catch disconnects
        #   we would need to modify pyCraft
        #   more. Done that, can redo that
        if self.channel is None:
            return # Fucking before loop not working!
        while len(self.bot.mess_queue) > 0:
            author, message = self.bot.mess_queue.pop()
            e = discord.Embed()
            e.description = message
            if author != "CONNECTION" and author != "SYSTEM":
                e.set_author(name=author, icon_url=f"https://minotar.net/avatar/{author}",
                                        url=f"https://namemc.com/profile/{author}")
                if (message.startswith(">")):
                    e.colour = 0x61cc49
                else:
                    e.colour = 0xadadad
            else:
                e.colour = 0xa34bd6
            await self.channel.send(embed=e, delete_after=3600)

    @forward_task.before_loop
    async def before_forward_task(self):
        await self.bot.wait_until_ready()

def setup(bot):
    bot.add_cog(botBase(bot))
