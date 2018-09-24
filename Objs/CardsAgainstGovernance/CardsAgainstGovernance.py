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
        self.question_area = PlayingArea()
        self.questions_deck = Deck(cards[0])
        self.answers_deck = Deck(cards[1])
        self.turn_generator = None
        self.cur_czar = None
        
        # Setup.
        asyncio.run_coroutine_threadsafe(
            self.client.send_message(self.channel, "Cards against Governance is now in setup. Register with the game by mentioning the bot. Start the game with !startcardsgame."),
            asyncio.get_event_loop())
        setup_id = self.switchboard.RegisterOutput(self.SetupPlayers, PriorityLevel.PRIORITY, channel_id=channel.id, mentions=self.client.user.id)
        self.switchboard.RegisterOutput(self.StartGame, PriorityLevel.PRIORITY, channel_id=channel.id, starts_with="!startcardsgame",
                                        remove_self_when_done=True, remove_when_done=[(setup_id, PriorityLevel.PRIORITY)])
    
    # TODO: Get current round, etc.
    
    def GetCzar(self):  # A generator that returns the current czar. Changing self.players will change its operation.
        cur_index = -1
        while True:
            cur_index = (cur_index+ 1) % len(self.players)
            yield self.players[cur_index]    
    
    # Handles setup and getting players.
    async def SetupPlayers(self, message):
        for player in self.players:
            if player.id == message.author.id:
                return False
        self.players.append(Player(message.author, self.switchboard, self.client))
        return True
        
    # Handles starting the game itself.  TODO: rule out # of players < 2
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
        self.turn_generator = self.GetCzar()
        self.SetupTurn()
        return True
        
    def SetupTurn(self):
        # TODO: make sure each player has 10 cards
        self.cur_czar = next(self.turn_generator)
        new_question = self.questions_deck.Deal(1)
        self.question_area.Play(new_question[0], self.cur_czar.user.id)
        asyncio.run_coroutine_threadsafe(
            self.client.send_message(self.channel, "Current Card Czar: " + self.cur_czar.user.name + "\nQuestion card:```" + new_question[0].description +"```"),
            asyncio.get_event_loop())
        
        
    async def WaitForCardPlay(self, message):
        pass

    def EndGame(self):
        pass
    