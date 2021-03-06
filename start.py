#!/usr/bin/env python

from __future__ import print_function

import getpass
import sys
import re
import json
from optparse import OptionParser

from minecraft import authentication
from minecraft.exceptions import YggdrasilError
from minecraft.networking.connection import Connection
from minecraft.networking.packets import Packet, clientbound, serverbound
from minecraft.compat import input

# Added
from bots.util import parse_chat_item, parse_message, DiscordBotThread
from collections import deque



def get_options():
    with open('config.json') as f:
        configData = json.loads(f.read())

    parser = OptionParser()

    parser.add_option("-u", "--username", dest="username", default=configData["EMAIL"],
                      help="username to log in with")

    parser.add_option("-p", "--password", dest="password", default=configData["PASSWORD"],
                      help="password to log in with")

    parser.add_option("-s", "--server", dest="server", default=configData["SERVER_IP"],
                      help="server host or host:port "
                           "(enclose IPv6 addresses in square brackets)")

    parser.add_option("-o", "--offline", dest="offline", action="store_true",
                      help="connect to a server in offline mode "
                           "(no password required)")

    parser.add_option("-d", "--dump-packets", dest="dump_packets",
                      action="store_true",
                      help="print sent and received packets to standard error")

    (options, args) = parser.parse_args()

    if not options.username:
        options.username = input("Enter your username: ")

    if not options.password and not options.offline:
        options.password = getpass.getpass("Enter your password (leave "
                                           "blank for offline mode): ")
        options.offline = options.offline or (options.password == "")

    if not options.server:
        options.server = input("Enter server host or host:port "
                               "(enclose IPv6 addresses in square brackets): ")
    # Try to split out port and address
    match = re.match(r"((?P<host>[^\[\]:]+)|\[(?P<addr>[^\[\]]+)\])"
                     r"(:(?P<port>\d+))?$", options.server)
    if match is None:
        raise ValueError("Invalid server address: '%s'." % options.server)
    options.address = match.group("host") or match.group("addr")
    options.port = int(match.group("port") or 25565)

    return options


def main():
    options = get_options()

    if options.offline:
        print("Connecting in offline mode...")
        connection = Connection(
            options.address, options.port, username=options.username)
    else:
        auth_token = authentication.AuthenticationToken()
        try:
            auth_token.authenticate(options.username, options.password)
        except YggdrasilError as e:
            print(e)
            sys.exit()
        print("Logged in as %s..." % auth_token.username)
        connection = Connection(
            options.address, options.port, auth_token=auth_token)

    if options.dump_packets:
        def print_incoming(packet):
            if type(packet) is Packet:
                # This is a direct instance of the base Packet type, meaning
                # that it is a packet of unknown type, so we do not print it.
                return
            print('--> %s' % packet, file=sys.stderr)

        def print_outgoing(packet):
            print('<-- %s' % packet, file=sys.stderr)

        connection.register_packet_listener(
            print_incoming, Packet, early=True)
        connection.register_packet_listener(
            print_outgoing, Packet, outgoing=True)

    once = False

    def handle_join_game(join_game_packet):
        message_queue.append(("CONNECTION", "**Connected**"))
        once = True
        print('Connected.')

    connection.register_packet_listener(
        handle_join_game, clientbound.play.JoinGamePacket)

    def print_chat(chat_packet):
        print("[%s]: %s" % (
            chat_packet.field_string('position'), parse_chat_item(json.loads(chat_packet.json_data))))

    connection.register_packet_listener(
        print_chat, clientbound.play.ChatMessagePacket)

    # Add a deque for chat messages and register a method to get them
    message_queue = deque()

    def forward_chat(chat_packet):
        msg = parse_chat_item(json.loads(chat_packet.json_data))
        if msg.startswith("<"):
            author, message = parse_message(msg)
            if (author != auth_token.username and message != ""): # Don't put in queue your own messages!
                message_queue.append((author, message))

    connection.register_packet_listener(
        forward_chat, clientbound.play.ChatMessagePacket)

    # More maybe? Add here shit for a chatbot

    # Auto respawn because we can't send chat while dead
    def auto_respawn(update_health_packet):
        if update_health_packet.health <= 0:
            print("Respawning")
            packet = serverbound.play.ClientStatusPacket()
            packet.action_id = serverbound.play.ClientStatusPacket.RESPAWN
            connection.write_packet(packet)

    connection.register_packet_listener(
        auto_respawn, clientbound.play.UpdateHealthPacket)

    # Start the discord thread and provide the message deque

    botThread = DiscordBotThread(message_queue, connection)
    botThread.daemon = True
    botThread.start()

    connection.connect()

    while True:
        try:
            text = input()
            if text == "/respawn":
                print("respawning...")
                packet = serverbound.play.ClientStatusPacket()
                packet.action_id = serverbound.play.ClientStatusPacket.RESPAWN
                connection.write_packet(packet)
            else:
                packet = serverbound.play.ChatPacket()
                packet.message = text
                connection.write_packet(packet)
        except KeyboardInterrupt:
            print("Bye!")
            sys.exit()


if __name__ == "__main__":
    main()
