from abc import ABC, abstractmethod
from collections import Counter, defaultdict
from typing import DefaultDict, Dict, Generic, Iterable, List, Optional, Tuple, TypeVar

from goldenballs.util import pop_random


ContextType = TypeVar("ContextType")


class Ball(ABC):
    @abstractmethod
    def describe(self) -> str:
        raise NotImplementedError

class KillerBall(Ball):
    def describe(self) -> str:
        return "Killer Ball"

class CashBall(Ball):
    value: int

    def __init__(self, value: int):
        super().__init__()
        self.value = value
    
    def __str__(self) -> str:
        return f"Ball({self.value})"
    
    def describe(self) -> str:
        return f"£{self.value} Ball"

    @staticmethod
    def generate_pool() -> List["CashBall"]:
        entries = [
            # limit, step
            (    10,    10),
            (    20,     5),
            (   100,    10),
            ( 1_500,    50),
            ( 2_500,   100),
            (10_000,   250),
            (50_000, 2_500),
            (75_000, 5_000),
        ]

        balls = []
        val = 0
        for entry in entries:
            limit, step = entry
            assert (limit - val) % step == 0, f"{entry} won't hit limit from {val}"
            while val < limit:
                val += step
                balls.append(CashBall(val))
        
        assert len(balls) == 100, f"Got {len(balls)} balls: {balls}"
        
        return balls


class Player(Generic[ContextType]):
    # Display name of the player
    name: str

    # Game that this player is currently in
    current_game: Optional["Game"]

    # User code context for this player
    context: ContextType

    def __init__(self, name: str, context: ContextType = None):
        self.name = name
        self.current_game = None
        self.context = context

    def is_busy(self):
        """Checks if the player is in a name"""

        return self.current_game is not None

    def get_name(self):
        """Gets the display name for the player"""

        return self.name

    def join_game(self, game: "Game"):
        self.current_game = game
        game.players.append(self)

    def __repr__(self):
        return f"{self.get_name()}[{self.current_game is not None}]"


# New state, response message
StateRet = Tuple["GameState", Optional[str]]


class GameState(ABC):
    game: "Game"

    def __init__(self, game: "Game"):
        self.game = game

    def on_join(self, player: Player) -> StateRet:
        """Update function for when a player tries to join"""

        return self, "The game is not joinable."

    def on_vote(self, player: Player, target: Player) -> StateRet:
        """Update function for when a player tries to vote"""

        return self, "The game is not in a voting stage."


class WaitingState(GameState):
    PLAYER_COUNT = 4

    def on_join(self, player: Player) -> StateRet:
        # Check player can join
        if player in self.game.players:
            return self, "You're already in this game."
        if player.is_busy():
            return self, "You're already in a game."

        # Add player to game
        player.join_game(self.game)

        # Start game if enough players are gathered
        if len(self.game.players) == self.PLAYER_COUNT:
            self.game.send_channel_message(
                f"Game starting with {', '.join(player.get_name() for player in self.game.players)}"
            )
            state = FourPlayerState(self.game)
        else:
            state = self

        return state, "You joined the game."


class FourPlayerState(GameState):
    CASH_BALL_COUNT = 12
    KILLER_COUNT = 4

    SHOWN_COUNT = 2
    HIDDEN_COUNT = 2
    PLAYER_COUNT = 4

    assert CASH_BALL_COUNT + KILLER_COUNT == (SHOWN_COUNT + HIDDEN_COUNT) * PLAYER_COUNT

    shown_balls: Dict[Player, List[Ball]]
    hidden_balls: Dict[Player, List[Ball]]
    votes: Dict[Player, Player]

    def __init__(self, game: "Game"):
        super().__init__(game)

        # Setup the initial balls
        for _ in range(self.CASH_BALL_COUNT):
            ball = pop_random(self.game.machine_balls)
            self.game.active_balls.append(ball)
        for _ in range(self.KILLER_COUNT):
            self.game.add_ball(KillerBall())

        # Assign balls to players
        self.shown_balls = {}
        self.hidden_balls = {}
        balls = self.game.active_balls[:]
        for player in self.game.players:
            self.shown_balls[player] = [
                pop_random(balls)
                for _ in range(self.SHOWN_COUNT)
            ]
            self.hidden_balls[player] = [
                pop_random(balls)
                for _ in range(self.HIDDEN_COUNT)
            ]

        # Announce the shown balls
        ball_list = lambda balls: ', '.join(ball.describe() for ball in balls)
        self.game.send_channel_message('\n'.join((
            "Everyone has been given 4 balls, 2 hidden and 2 shown.",
            "The shown balls are:",
            '\n'.join(
                f"    {player.get_name()} - {ball_list(self.shown_balls[player])}"
                for player in self.game.players
            ),
            "Your hidden balls will be sent in dms."
        )))

        # Send players their hidden balls
        for player in self.game.players:
            self.game.send_dm(player, f"Your hidden balls are: {ball_list(self.hidden_balls[player])}")

        # Init votes
        self.votes = {}

    def on_vote(self, player: Player, target: Player) -> StateRet:
        # Check player hasn't already voted
        if player in self.votes:
            return self, "You already voted."
        
        # Check player isn't voting for themself
        if player == target:
            return self, "You can't vote for yourself"

        # Register vote
        self.votes[player] = target

        # Check for all votes being ready
        if len(self.votes) == self.PLAYER_COUNT:
            # TODO: handle ties
            
            # Find who was voted off
            loser = Counter(self.votes.values()).most_common()[0][0]

            # Announce the votes
            self.game.send_channel_message('\n'.join((
                "The votes are in:",
                '\n'.join(
                    f"    - {player.get_name()}"
                    for player in self.votes.values()
                ),
                f"{loser.get_name()} has been voted off."
            )))

            # Reveal all balls
            ball_list = lambda balls: ', '.join(ball.describe() for ball in balls)
            self.game.send_channel_message('\n'.join((
                "The hidden balls were:",
                '\n'.join(
                    f"    {player.get_name()} - {ball_list(self.hidden_balls[player])}"
                    for player in self.game.players
                ),
            )))

        return self, "Vote registered."


class Game:
    players: List[Player]
    state: GameState
    channel_messages: List[str]
    dms: DefaultDict[Player, List[str]]

    # The pool of balls in the machine
    machine_balls: List[CashBall]

    # The balls chosen for this game, including killers
    active_balls: List[Ball]

    def __init__(self):
        self.players = []
        self.state = WaitingState(self)
        self.channel_messages = []
        self.dms = defaultdict(list)
        self.machine_balls = CashBall.generate_pool()
        self.active_balls = []
    
    def __str__(self) -> str:
        return f"Game({', '.join(str(player) for player in self.players)})"

    def add_ball(self, ball: Ball):
        self.active_balls.append(ball)

    @staticmethod
    def start_game(host: Player) -> Tuple[Optional["Game"], Optional[str]]:
        # Check game can be started
        if host.is_busy():
            return None, "You're already in a game."

        # Create a game with the host playing
        game = Game()
        host.join_game(game)

        return game, "Game started."

    def on_join(self, player: Player) -> Optional[str]:
        self.state, response = self.state.on_join(player)
        return response

    def on_vote(self, player: Player, target: Player) -> Optional[str]:
        self.state, response = self.state.on_vote(player, target)
        return response

    def send_channel_message(self, msg: str):
        self.channel_messages.append(msg)

    def has_channel_message(self) -> bool:
        return len(self.channel_messages) > 0

    def get_channel_message(self) -> str:
        return self.channel_messages.pop(0)

    def send_dm(self, player: Player, msg: str):
        self.dms[player].append(msg)
    
    def get_dm_subjects(self) -> Iterable[Player]:
        return self.dms.keys()
    
    def has_dm(self, player: Player) -> bool:
        return len(self.dms[player]) > 0
    
    def get_dm(self, player: Player) -> str:
        return self.dms[player].pop(0)
