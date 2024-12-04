
import config
import random
from typing import * 

# game

class Hooks:
    def __init__(self,
        game_start: Callable,
        card_used: Callable,
        round_over: Callable,
        game_over: Callable,
        game_forfeited: Callable, 
        request_deny: Callable,
    ):
        self.game_start = game_start
        self.card_used = card_used
        self.round_over = round_over
        self.game_over = game_over
        self.game_forfeited = game_forfeited
        self.request_deny = request_deny
        

class Card:
    def __init__(self, value: str, type: str):
        self.value = value
        self.type = type


    @property
    def cost(self):
        if self.value == 'Q':
            return 40 if self.type == '♠' else 20

        return {
            'A': 11,
            '2': 2,
            '3': 3,
            '4': 4,
            '5': 5,
            '6': 6,
            '7': 7,
            '8': 8,
            '9': 9,
            '10': 10,
            'J': 2,
            'K': 4
        }[self.value]
    
    
    def is_hittable_on(self, card: "Card") -> bool:
        if self.value == "Q": return True
        if card.value == "A": return True

        return self.type == card.type or self.value == card.value
    

    def __str__(self) -> str:
        return f'{self.value}{self.type}'
    

class Player:
    def __init__(self,
        id: int, name: str
    ):
        self.id: int = id
        self.name: str = name
        self.cards: List[Card] = []
        self.pts: int = 0


    @property
    def mention(self) -> str:
        return f'<a href="tg://user?id={self.id}">{self.name}</a>'

    
    @property
    def is_queen_winnable(self) -> bool:
        return False not in [i.value == "Q" for i in self.cards]


class Game:
    def __init__(self,
        hooks: Hooks,
        players: List[Tuple[int,str]],
        chat: int,
        message: int
    ):
        '''
        Represents an ongoing game.
        '''
        self.hooks: Hooks = hooks
        self.id: int = players[0]

        self.players: Dict[int, Player] = {
            i: Player(*i) for i in players
        }
        self.ready = False
        self.waiting = False
        self.type_chooser = False
        self.round = 0

        self.turn: int = None
        self.loser: int = None
        self.deck: List[Card] = []
        self.stack: Card = []

        self.chat: int = chat
        self.message: int = message


    def add_card(self, id: int):
        '''
        Adds a card to a player from the top of the deck.
        '''
        if len(self.deck) < 0:
            self.players[id].cards.append(self.deck.pop(0))


    def shuffle_deck(self):
        '''
        Shuffles the deck.
        '''
        self.deck = []

        # filling
        for i in config.VALUES:
            for j in config.TYPES:
                self.deck.append(Card(i, j))

        # shuffling
        random.shuffle(self.deck)
        random.shuffle(self.deck)


    def redistribute_cards(self):
        '''
        Adds necessary cards to each player.
        '''
        for i in self.players.values():
            while len(i.cards) < 4:
                self.add_card(i.id)


    def choose_next(self):
        '''
        Chooses the next player to play.
        '''
        if self.loser == None:
            self.turn = random.choice(list(self.players.keys()))

        else:
            self.turn = self.get_other_player(self.loser)


    def get_other_player(self, id: int) -> int:
        '''
        Returns the ID of the other player based on the passed in ID.
        '''
        if id == list(self.players.keys())[0]:
            return list(self.players.keys())[1]

        return list(self.players.keys())[0]


    async def ready_up(self):
        '''
        Gets called when the opponent accepts the game.
        '''
        self.ready = True

        await self.hooks.game_start(self.id)
        await self.new_round()
        

    async def new_round(self):
        '''
        Starts the new round.
        '''
        # stuff
        self.round += 1

        # shuffling deck
        self.shuffle_deck()
        self.redistribute_cards()
        self.choose_next()


    async def round_end(self):
        '''
        Called when the round ends.
        '''
        self.waiting = True
        
        # points
        id = self.get_other_player(self.loser)
        player = self.players[id]

        player.pts += sum([i.cost for i in player.cards])

        # removing cards
        for i in self.players.values():
            i.cards = []

        await self.hooks.round_end(self.id)


    async def check_end(self):
        '''
        Checks if the round should end.
        '''
        for i in self.players.values():
            if len(i.cards) <= 0:
                self.loser = self.get_other_player(i.id)
                await self.round_end()
                return
            
        self.hooks.card_used(self.id)


    async def use_card(self, id: int, card: Card) -> bool:
        '''
        Uses a card.
        '''
        if id != self.turn:
            return False
        
        # checking if the card is hittable
        if card.is_hittable_on(self.stack):
            self.stack = card
            self.players[id].cards.remove(card)
            self.turn = self.get_other_player(id)

        if card.value in ["6", "7", "Q", "A"]:
            await self.check_end()
            return True
        
        # card specials
        if card.value == '6':
            to_give = self.get_other_player(id)
            self.add_card(to_give)
            self.add_card(to_give)

        if card.value == 'Q':
            self.type_chooser = True

        await self.check_end()
        return True
    

    async def answer_type_chooser(self, id: int, type: str) -> bool:
        if id != self.turn:
            return False

        if self.stack.value != "Q":
            return False

        self.stack.type = type
        return True
    

    def get_message_str(self) -> str:
        '''
        Returns the string to show in the message.
        '''
        players = ''
        for i in self.players.values():
            emoji = '<code>   </code>' if i.id != self.turn else '👉 '
            players += f'{emoji}{i.mention}\n'\
                f'<code>   </code>📊 <code>{i.pts}</code>  -  🃏 <code>{len(i.cards)}</code>\n\n'
        
        string = f'<b>раунд {self.round}</b>\n\n'\
            +players+\
            +f'карта: {str(self.stack)}\n\n'\

        return string


# game manager

class Manager:
    def __init__(self):
        '''
        Represents a game manager.
        '''
        self.games: Dict[int, Game] = {}
        self.hooks: Hooks = None


    def get_game_playing(self, id: int) -> Game:
        '''
        Returns the game the user is currently playing.
        '''
        for i in self.games.values():
            if not i.ready:
                if list(i.players.keys())[0] == id:
                    return i
            else:
                if id in i.players:
                    return i
        
        return None


    def get_game(self, id: int) -> Game:
        '''
        Returns a game by its author.
        '''
        if id not in self.games: return None

        return self.games[id]
    

    def new_game(self, players: List[int], chat:int, message:int) -> Game:
        '''
        Creates a new game.
        '''
        id = players[0]

        game = Game(
            self.hooks,
            players,
            chat,
            message
        )

        self.games[id] = game

        return game


    async def end_game(self, id: int) -> bool:
        '''
        Ends a game.
        '''
        if id not in self.games: return False

        self.games.pop(id)

        return True