import asyncio
import discord
import threading
import random
from functools import partial
from ..DiscordSwitchboard.DiscordSwitchboard import PriorityLevel
from ..Deck.Deck import Card, Deck, PlayingArea
from ..Player.Player import Player

# We don't worry about getting asynchronocity issues on registering/unregistering functors here, as the switchboard will take card of that.
# However, the objects own critical areas need protection in certain cases. Fortunately, most individual operations with standard Python objects (inserting, etc.) are threadsafe.

DEBUG = True  # Currently, allows the card czar to play on his own turn and allows for one-player games.
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
        self.new_question = None
        
        # Setup.
        asyncio.run_coroutine_threadsafe(
            self.client.send_message(self.channel, "Cards against Governance is now in setup. Register with the game by mentioning the bot. Start the game with !startcardsgame."),
            asyncio.get_event_loop())
        setup_id = self.switchboard.RegisterOutput(self.SetupPlayers, PriorityLevel.PRIORITY, channel_id=channel.id, mentions=self.client.user.id)
        self.switchboard.RegisterOutput(self.StartGame, PriorityLevel.PRIORITY, channel_id=channel.id, starts_with="!startcardsgame",
                                        remove_self_when_done=True, remove_when_done=[(setup_id, PriorityLevel.PRIORITY)])
                                        
        self.player_lock = threading.Lock()
        self.has_played = {}
    
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
        
    # Handles starting the game itself.
    async def StartGame(self, message):
        if len(self.players) < 2 and not DEBUG:
            asyncio.run_coroutine_threadsafe(
            self.client.send_message(self.channel, "Not enough players!"),
            asyncio.get_event_loop())
            return False
        # Deal a hand to each player. Note that it doesn't matter that we haven't determined turn order yet, as this is all randomized anyway.
        for player in self.players:
            player.hand = []  # players will get their full hands at start of turn
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
        # Each player draws until they have ten cards.
        for player in self.players:
            player.hand.extend(self.answers_deck.Deal(CARDS_PER_PLAYER - len(player.hand)))
            player.DisplayHand()
        self.cur_czar = next(self.turn_generator)
        new_question = self.questions_deck.Deal(1)
        self.new_question = new_question[0]
        self.question_area.Play(self.new_question, self.cur_czar.user.id)
        asyncio.run_coroutine_threadsafe(
            self.client.send_message(self.channel,
                                     ''.join(["Current Card Czar: ", self.cur_czar.user.name, "\n\nQuestion card:```", new_question[0].description, "```\n\nSubmit your reply by PM using !submit (number) (number)"])),
            asyncio.get_event_loop())
        for player in self.players:
            if not DEBUG and player.user == self.cur_czar.user:
                continue
            player.AddResponse("WaitForCardPlay", partial(self.WaitForCardPlay, player))
        
    async def WaitForCardPlay(self, player, message):
        words = message.content.lower().split()
        if words[0] != "!submit":            
            return
        if len(words) < 2:
            return
        card_choices = []
        for word in words[1:]:
            try:
                card_choice = int(word)
            except (ValueError, TypeError):
                player.SendMessage("Command improperly formatted! Try again.")
                return
            if card_choice < 0 or card_choice > len(player.hand) - 1:
                player.SendMessage("Card # out of range! Try Again.")
                return
            card_choices.append(card_choice)
        if len(card_choices) != self.new_question.data["num_answers"]:
            player.SendMessage("Wrong number of answers!")
        for card_choice in card_choices:
            self.playing_area.Play(self.player.hand[card_choice], player.user.id)
        # TODO: turn this into a player method
        self.player.hand = [card for x, card in enumerate(self.player.hand) if x not in card_choice]
        with self.player_lock:
            self.has_played[player.user.id] = True
            for id, has_played in self.has_played.items():
                if (id != self.cur_czar.user.id or DEBUG) and not has_played:
                    return
            # Clear has_played and remove functors
            self.ResolveTurn()
            
    def ResolveTurn(self):
        pass

    def EndGame(self):
        pass
    