from ..DiscordSwitchboard.DiscordSwitchboard import PriorityLevel
import asyncio

# An object that manages PM interaction with the player of a card game, and holds their cards.

# Takes immediate ownership of the PM channel
class Player:
    def __init__(self, user, switchboard, client):
        self.user = user
        self.switchboard = switchboard
        switchboard.RegisterOutput(self.on_message, PriorityLevel.PRIORITY, is_private=True, author_id=self.user.id)
        self.hand = None
        self.input_responses = {}
        self.client = client
    
    def __del__(self):
        for card in self.hand:
            card.okay_to_delete = True
        
    async def on_message(self, message):
        for func in self.input_responses.values():
             asyncio.run_coroutine_threadsafe(func(message), asyncio.get_event_loop())
             
    def DisplayHand(self):
        card_list_string = "\n".join(str(x) + ": " + card.description for x, card in enumerate(self.hand))
        asyncio.run_coroutine_threadsafe(
            self.client.send_message(self.user, "Your Hand:\n" + card_list_string),
            asyncio.get_event_loop())