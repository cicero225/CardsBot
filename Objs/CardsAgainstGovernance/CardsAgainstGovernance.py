import asyncio
import discord
import threading
import random
from ..DiscordSwitchboard.DiscordSwitchboard import PriorityLevel
from ..Deck.Deck import Card, Deck, PlayingArea
from ..Player.Player import Player

# We don't worry about getting asynchronocity issues here, as the switchboard will take card of that.

CARDS_PER_PLAYER = 10

class CardsAgainstGovernance:   # cards here should be passed in as a unique copy for this class.
    def __init__(self, switchboard, channel, client, cards):
        self.switchboard = switchboard
        self.channel = channel
        self.client = client
        self.players = []
        
        self.playing_area = PlayingArea()
        self.questions_deck = Deck(cards[0])
        self.answers_deck = Deck(cards[1])
        
        # Setup.
        asyncio.run_coroutine_threadsafe(
            self.client.send_message(self.channel, "Cards against Governance is now in setup. Register with the game by mentioning the bot. Start the game with !startcardsgame."),
            asyncio.get_event_loop())
        setup_id = self.switchboard.RegisterOutput(self.SetupPlayers, PriorityLevel.PRIORITY, channel_id=channel.id, mentions=self.client.user.id)
        self.switchboard.RegisterOutput(self.StartGame, PriorityLevel.PRIORITY, channel_id=channel.id, starts_with="!startcardsgame",
                                        remove_self_when_done=True, remove_when_done=[(setup_id, PriorityLevel.PRIORITY)])
                                        
                                        
    
    # Handles setup and getting players.
    async def SetupPlayers(self, message):
        for player in self.players:
            if player.id == message.author.id:
                return False
        self.players.append(Player(message.author, self.switchboard, self.client))
        return True
        
    # Handles starting the game itself.
    async def StartGame(self, message):
        # Deal a hand to each player. Note that it doesn't matter that we haven't determined turn order yet, as this is all randomized anyway.
        for player in self.players:
            player.hand = self.answers_deck.Deal(CARDS_PER_PLAYER)
            player.DisplayHand()
        asyncio.run_coroutine_threadsafe(
            self.client.send_message(self.channel, "Game is started, your hand has been PM'd to you."),
            asyncio.get_event_loop())
        # Determine turn order:
        random.shuffle(list(self.players))
        asyncio.run_coroutine_threadsafe(
            self.client.send_message(self.channel, "Turn order is: " + ", ".join(player.user.name for player in self.players)),
            asyncio.get_event_loop())
        return True