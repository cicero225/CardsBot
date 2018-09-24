import random
import warnings

# A very basic card, might have additional features in the future. Mainly, if just warns if destroyed without being flagged for destruction, indicating illogical destruction.
class Card:
    def __init__(self, description, data):
        self.description = description
        self.okay_to_delete = False
        self.owner = None   # Will be referenced to return cards to by PlayingArea
        self.data = data
        
    def __del__(self):
        if not self.okay_to_delete:
            warnings.warn("Card Object destroyed abnormally!")
            
    def Return(self):
        self.owner.Return(self)

# A very basic card deck. Feel free to extend or inherit as desired.
class Deck:
    def __init__(self, cards, initial_shuffle = True):
        self.draw_pool = cards
        self.discard = []
        for card in cards:
            card.owner = self  # Set owner
        if initial_shuffle:
            self.Reshuffle()
            
    def __del__(self):
        # None of these cards will ever be deleted while this Deck still exists, so this guarantees that okay_to_delete is set before their destructors are called.
        for card in self.draw_pool:
            card.okay_to_delete = True
        for card in self.discard:
            card.okay_to_delete = True
    
    def Reshuffle(self):
        self.draw_pool.extend(self.discard)
        self.discard.clear()
        random.shuffle(self.draw_pool)
    
    # Returns cards dealt AND ALSO REMOVES THEM FROM THE DECK. Make sure to take ownership.
    # If reshuffle is True, it will reshuffle the deck to draw the remaining cards if not enough
    # cards left. If False, it will deal out the remaining cards and return.
    def Deal(self, number, reshuffle=True):
        # Check for reshuffle
        output_list = []
        if number > len(self.draw_pool):
            # Deal out remaining cards
            output_list.extend(self.draw_pool)
            self.draw_pool.clear()
            if not reshuffle:
                return output_list
            self.Reshuffle()
            number -= len(output_list)
        output_list.extend(self.draw_pool.pop() for _ in range(number))
        return output_list
        
    # Returns card to the deck in the discard pile
    def Return(self, card):
        self.discard.append(card)

# A temporary object for holding played cards. Returns cards to their owning decks when done. Extend for further behavior.
class PlayingArea:
    def __init__(self):
        self.current_cards = {}

    def Play(self, card, source_id):
        self.current_cards[source_id] = card
        
    def EndTurn():
        for card in self.current_cards.values():
            card.Return()
        self.current_cards.clear()