
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
        new_round: Callable,
        request_deny: Callable,
    ):
        self.game_start = game_start
        self.card_used = card_used
        self.round_over = round_over
        self.game_over = game_over
        self.new_round = new_round
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
        self.id: int = players[0][0]

        self.players: Dict[int, Player] = {
            i[0]: Player(*i) for i in players
        }
        self.ready = False
        self.waiting = False
        self.type_chooser = False
        self.round = 0

        self.turn: int = None
        self.loser: int = None
        self.loser_earned: str = ''
        self.winner_subbed: str = ''
        self.deck: List[Card] = []
        self.stack: Card = None
        self.took = False

        self.chat: int = chat
        self.message: int = message


    def add_card(self, id: int):
        '''
        Adds a card to a player from the top of the deck.
        '''
        if len(self.deck) > 0:
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
            amount = 4 - len(i.cards)
            for _ in range(amount):
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
        self.waiting = False
        self.type_chooser = False
        self.stack = None

        # shuffling deck
        self.shuffle_deck()
        self.redistribute_cards()
        self.choose_next()

        await self.hooks.new_round(self.id)


    async def round_end(self):
        '''
        Called when the round ends.
        '''
        self.waiting = True
        
        # points
        player = self.players[self.loser]

        player.pts += sum([i.cost for i in player.cards])
        self.loser_earned = ''

        for i in player.cards:
            self.loser_earned += f' {str(i)} - <code>{i.cost}</code>\n'
        self.loser_earned += f'<code>+ {sum([i.cost for i in player.cards])}</code>'

        # removing cards
        for i in self.players.values():
            i.cards = []

        # checking for game end
        for i in self.players.values():
            if i.pts >= 105:
                await self.hooks.game_over(self.id)
                return

        await self.hooks.round_over(self.id)


    async def check_end(self):
        '''
        Checks if the round should end.
        '''
        for i in self.players.values():
            if len(i.cards) <= 0:
                self.loser = self.get_other_player(i.id)
                await self.round_end()
                return
            
        await self.hooks.card_used(self.id)


    async def use_card(self, id: int, index: int) -> bool:
        '''
        Uses a card.
        '''
        if id != self.turn:
            return False
        
        card = self.players[id].cards[index]
        
        # checking if the card is hittable
        if self.stack == None or card.is_hittable_on(self.stack):
            self.stack = card
            self.players[id].cards.remove(card)

        else:
            return False
        
        self.took = False

        if card.value not in ["6", "7", "Q", "A"]:
            self.turn = self.get_other_player(id)
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


    async def queen_end(self, id: int) -> bool:
        '''
        Ends the game with all queens.
        '''
        if id != self.turn:
            return False

        if not self.players[id].is_queen_winnable:
            return
        
        amount = sum([i.cost for i in self.players[id].cards])
        self.winner_subbed = f'\n\n<b>{self.players[id].mention} списал дамами!</b>\n'\
            f'{" ".join([i.type for i in self.players[id].cards])} = <code>-{amount}</code>'

        self.players[id].pts -= amount
        self.players[id].cards = []

        await self.check_end()
        return True


    async def take_card(self, id: int) -> bool:
        '''
        Takes a card.
        '''
        if id != self.turn:
            return False
        
        # taking card
        if not self.took:
            self.add_card(id)
            self.took = True
        else:
            self.turn = self.get_other_player(id)
            self.took = False

        await self.check_end()
        return True
    

    async def answer_type_chooser(self, id: int, type: str) -> bool:
        if id != self.turn:
            return False

        if self.stack.value != "Q":
            return False

        self.stack.type = type
        self.type_chooser = False
        self.turn = self.get_other_player(id)
        
        await self.check_end()
        return True
    

    def get_message_str(self) -> str:
        '''
        Returns the string to show in the message.
        '''
        if self.waiting:
            return f'<b>конец раунда {self.round}</b>\n\n{self.players[self.loser].mention} проиграл!'\
                f'\n\n{self.loser_earned}\n\nслед. раунд через 10 секунд'
        
        if self.type_chooser:
            return f'{self.players[self.turn].mention}, выбери масть!'

        players = ''
        for i in self.players.values():
            emoji = '<code>   </code>' if i.id != self.turn else '👉 '
            players += f'{emoji}{i.mention}\n'\
                f'<code>   </code>📊 <code>{i.pts}</code>  -  🃏 <code>{len(i.cards)}</code>\n\n'
        
        string = players+f'карт в колоде: <code>{len(self.deck)}</code>\n'+\
            (f'карта: {str(self.stack)}' if self.stack != None else '')\

        return string


# game manager

class Manager:
    def __init__(self):
        '''
        Represents a game manager.
        '''
        self.games: Dict[int, Game] = {}
        self.hooks: Hooks = None
        self.rules: str = ''

        self.load_data()


    def load_data(self):
        '''
        Loads rules from a file.
        '''
        with open('rules.html', 'r', encoding='utf-8') as f:
            self.rules = f.read()


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
        id = players[0][0]

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

        await self.games[id].hooks.game_over(id)

        return True