import json
import threading
import asyncio
import discord
from discord.ext import commands

ext_folder = "bots."

def prepare_bot(exts, queue, conn):
    with open("config.json") as f:
        config = json.load(f)
    bot = commands.Bot(config["BOT_PREFIXES"])
    bot.config = config
    bot.mess_queue = queue # the message queue
    bot.connection = conn  # the pyCraft connection object

    bot.extension_list = exts
    bot.ext_folder = ext_folder
    for ext in exts:
        bot.load_extension(ext_folder + ext)
    return bot

def parse_chat_item(msg):
    out = ""
    if "text" in msg:
        out += msg["text"]
    if "with" in msg:
        for elem in msg["with"]:
            out += parse_chat_item(elem)
    if "extra" in msg:
        for elem in msg["extra"]:
            out += parse_chat_item(elem)
    return out

def parse_message(msg):
    author = msg.split(" ")[0].replace("<","").replace(">","")
    message = " ".join(msg.split(" ")[1:])
    if message != "":
        return (author, message)
    else:
        return ("", "")


class DiscordBotThread(threading.Thread):
    def __init__(self, queue, conn):
        threading.Thread.__init__(self) # THREAD constructor
        self.queue = queue
        self.conn = conn

    def run(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        extensions = [ "botBase" ] # A list of bot extensions that should be loaded
        bot = prepare_bot(extensions, self.queue, self.conn) # Stuff to prep bot
        try:              
            loop.run_until_complete(bot.start(bot.config["TOKEN"]))
        except KeyboardInterrupt:
            loop.run_until_complete(bot.logout())
        finally:
            loop.run_until_complete(loop.shutdown_asyncgens())
            loop.close()
        exit()
