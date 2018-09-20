# ArchivistBot.py
# Version 0.1
# Purpose:
# For the indexing and querying of text

import discord
import asyncio
import pickle
import random
import secrets
import re
import time
import threading
from Objs.DiscordSwitchboard.DiscordSwitchboard import DiscordSwitchboard, PriorityLevel
from Objs.CardsAgainstGovernance.CardsAgainstGovernance import CardsAgainstGovernance
from Objs.Deck.Deck import Card
from Configs.CardList import QuestionsList, AnswersList

ADMIN_ID = "192729741395099648"
CHANNEL = "484621382810992661"

HELP_MESSAGE = """```
Welcome to Cards Bot
```"""


class Cardsbot:
    def __init__(self):
        # For now we assume only one game at a time. We can try doing more in the future as necessary.
        self.game_started = False
        self.game = None
        self.game_lock = threading.Lock()

    @staticmethod
    def MakeCards():
        questions_list = []
        # Make cards
        for card_param in QuestionsList:
            for _ in range(card_param[1]):
                questions_list.append(Card(card_param[0]))
        answers_list = []
        for card_param in AnswersList:
            for _ in range(card_param[1]):
                answers_list.append(Card(card_param[0]))
        return questions_list, answers_list
        
    def main(self):
        client = discord.Client()
        
        @client.event
        async def on_ready():
            self.switchboard = DiscordSwitchboard()
            self.switchboard.MustHave(channel_id=CHANNEL)   # We're not using it for any other channel right now, so let's just ahead and do this.

        @client.event
        async def on_message(message):
            this_message = message.content.lower()
            if this_message == "!help cardbot":
                await client.send_message(message.channel, HELP_MESSAGE)
                return
            if this_message == '!cardshutdown' and message.author.id == ADMIN_ID:
                await client.logout()
                return
            # We do this explicitly here for clarity but in the future the class can take care of it.
            if this_message == '!cardpreparegame' and message.channel.id == CHANNEL and not self.game_started:
                with self.game_lock:
                    self.game = CardsAgainstGovernance(self.switchboard, message.channel, client, self.MakeCards())
                    self.game_started = True
                return
            await self.switchboard.on_message(message)                  
                
        # Blocking. Must be last.
        client.run(secrets.BOT_TOKEN)

if __name__ == '__main__':
    bot = Cardsbot()
    bot.main()
    
    


