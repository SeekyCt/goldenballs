from abc import ABC, abstractmethod
from collections import Counter, defaultdict
from enum import Enum
from operator import countOf
from typing import DefaultDict, Dict, Generic, Iterable, List, Optional, Tuple, Type, TypeVar

from goldenballs.util import pop_random


PlayerCtx = TypeVar("PlayerCtx")


class Ball(ABC):
    """Abstract ball class, can be a killer or have a cash value"""

    @abstractmethod
    def describe(self) -> str:
        """Gets the text to describe this ball"""

        raise NotImplementedError

    @abstractmethod
    def apply(self, current_prize: int) -> int:
        """Applies the value / effefct of this ball to the prize"""

        raise NotImplementedError

    @staticmethod
    def describe_list(balls: List["Ball"]) -> str:
        """Describes a list of balls"""

        return ', '.join(ball.describe() for ball in balls)

class KillerBall(Ball):
    """A ball that divides the prize by 10"""

    def __repr__(self):
        return "Ball(Killer)"

    def describe(self) -> str:
        return "Killer Ball"
    
    def apply(self, prize: int) -> int:
        return round(prize / 10)

class CashBall(Ball):
    # Cash value of this ball
    value: int

    def __init__(self, value: int):
        super().__init__()

        self.value = value
    
    def __repr__(self) -> str:
        return f"Ball({self.value})"
    
    def describe(self) -> str:
        return f"£{self.value} Ball"

    def apply(self, prize) -> int:
        return prize + self.value

    @staticmethod
    def generate_pool() -> List["CashBall"]:
        """Generates the initial pool of 100 cash balls"""

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
        for limit, step in entries:
            assert (limit - val) % step == 0, f"Limit {limit} won't hit limit from {val} with step {step}"
            while val < limit:
                val += step
                balls.append(CashBall(val))
        
        assert len(balls) == 100, f"Got {len(balls)} balls: {balls}"
        
        return balls


class Player(Generic[PlayerCtx]):
    # Display name of the player
    name: str

    # Game that this player is currently in
    current_game: Optional["Game"]

    # User code context for this player
    context: PlayerCtx

    def __init__(self, name: str, context: PlayerCtx = None):
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

    def leave_game(self) -> str:
        self.current_game.on_leave(self)

    def __repr__(self):
        return f"{self.get_name()}[{self.current_game is not None}]"


# New state, response message
StateRet = Tuple["GameState", str]


class GameState(ABC):
    game: "Game"

    def __init__(self, game: "Game"):
        self.game = game

    def on_join(self, player: Player) -> StateRet:
        """Update function for when a player tries to join"""

        return self, "The game is not joinable."

    def on_vote(self, player: Player, target: Player) -> StateRet:
        """Update function for when a player tries to vote"""

        return self, "The game is not in the voting stage."
    
    def on_pick(self, player: Player, ball_id: int) -> StateRet:
        """Update function for when a player tries to pick a ball"""

        return self, "The game is not in the picking stage."
    
    def on_split(self, player: Player) -> StateRet:
        """Update function for when a player tries to split"""

        return self, "The game is not in the split/steal stage"
    
    def on_steal(self, player: Player) -> StateRet:
        """Update function for when a player tries to steal"""

        return self, "The game is not in the split/steal stage"
    
    def on_leave(self, player: Player) -> StateRet:
        """Update function for when a player tries to leave"""

        if player not in self.game.players:
            return self, "You're not in this game."
        
        self.game.remove_player(player)


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


class HiddenShownState(GameState):
    shown_balls: Dict[Player, List[Ball]]
    hidden_balls: Dict[Player, List[Ball]]
    votes: Dict[Player, Player]
    next_state: Type[GameState]

    def __init__(self, game: "Game", initial_balls: Iterable[Ball], new_cash_ball_count: int, new_killer_count: int,
                 shown_count: int, hidden_count: int, next_state: Type[GameState]):
        super().__init__(game)

        # Backup next state
        self.next_state = next_state

        # Setup the initial balls
        balls = list(initial_balls)
        for _ in range(new_cash_ball_count):
            balls.append(self.game.get_machine_ball())
        for _ in range(new_killer_count):
            balls.append(KillerBall())
        assert len(balls) == (shown_count + hidden_count) * len(self.game.players)

        # Assign balls to players
        self.shown_balls = {}
        self.hidden_balls = {}
        for player in self.game.players:
            self.shown_balls[player] = [
                pop_random(balls)
                for _ in range(shown_count)
            ]
            self.hidden_balls[player] = [
                pop_random(balls)
                for _ in range(hidden_count)
            ]

        # Announce the shown balls
        self.game.send_channel_message('\n'.join((
            f"Everyone has been given {shown_count + hidden_count} balls, {hidden_count} hidden and {shown_count} shown.",
            "The shown balls are:",
            '\n'.join(
                f"    {player.get_name()} - {Ball.describe_list(self.shown_balls[player])}"
                for player in self.game.players
            ),
            "Your hidden balls will be sent in dms."
        )))

        # Send players their hidden balls
        for player in self.game.players:
            self.game.send_dm(player, f"Your hidden balls are: {Ball.describe_list(self.hidden_balls[player])}")

        # Init votes
        self.votes = {}

    def on_vote(self, player: Player, target: Player) -> StateRet:
        # Check player hasn't already voted
        if player in self.votes:
            return self, "You already voted."
        
        # Check player isn't voting for themself
        if player == target:
            return self, "You can't vote for yourself"
        
        # Check player is in this game
        if player.current_game != self.game:
            return self, "You can't vote for someone who isn't in the game."

        # Register vote
        self.votes[player] = target

        # Announce vote
        self.game.send_channel_message(f"{player.get_name()} has voted.")

        # Check for all votes being ready
        if len(self.votes) == len(self.game.players):
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
            self.game.send_channel_message('\n'.join((
                "The hidden balls were:",
                '\n'.join(
                    f"    {player.get_name()} - {Ball.describe_list(self.hidden_balls[player])}"
                    for player in self.game.players
                ),
            )))

            # Remove the loser
            self.game.remove_player(loser)

            # Build new ball list
            balls = []
            for player in self.game.players:
                for ball in self.shown_balls[player]:
                    balls.append(ball)
                for ball in self.hidden_balls[player]:
                    balls.append(ball)

            # Move to next state
            state = self.next_state(self.game, balls)
        else:
            state = self

        return state, "Vote registered."


class FourPlayerState(HiddenShownState):
    SHOWN_COUNT = 2
    HIDDEN_COUNT = 2

    CASH_BALL_COUNT = 12
    KILLER_COUNT = 4

    def __init__(self, game: "Game"):
        super().__init__(
            game,
            [],
            self.CASH_BALL_COUNT,
            self.KILLER_COUNT,
            self.SHOWN_COUNT,
            self.HIDDEN_COUNT,
            ThreePlayerState
        )


class ThreePlayerState(HiddenShownState):
    SHOWN_COUNT = 2
    HIDDEN_COUNT = 3

    CASH_BALL_COUNT = 2
    KILLER_COUNT = 1

    def __init__(self, game: "Game", initial_balls: Iterable[Ball]):
        super().__init__(
            game,
            initial_balls,
            self.CASH_BALL_COUNT,
            self.KILLER_COUNT,
            self.SHOWN_COUNT,
            self.HIDDEN_COUNT,
            BinWinState
        )


class BinWinState(GameState):
    ACTION_BIN = 0
    ACTION_WIN = 1
    ACTION_NAMES = ["bin", "win"]

    action: int
    player_id: int
    win_balls: List[Ball]
    available_balls: List[Ball]

    def __init__(self, game: "Game", initial_balls: List[Ball]):
        super().__init__(game)

        self.action = self.ACTION_BIN
        self.player_id = 0
        self.win_balls = []
        self.available_balls = list(initial_balls)
        self.available_balls.append(KillerBall())

        self.announce()
    
    def announce(self):
        self.game.send_channel_message(
            f"{self._get_player().get_name()}, Pick a ball from 1-{len(self.available_balls)} to {self.ACTION_NAMES[self.action]}."
        )

    def _get_player(self):
        return self.game.players[self.player_id]

    def on_pick(self, player: Player, ball_id: int) -> StateRet:
        # Check the player can pick
        if player != self._get_player():
            return self, "It's not your turn to pick."
        
        # Check the ball is valid
        idx = ball_id - 1
        if not (0 <= idx < len(self.available_balls)):
            return self, "That's not a valid ball."
        
        # Remove the ball from the pool
        ball = self.available_balls.pop(idx)
        if self.action == self.ACTION_WIN:
            self.win_balls.append(ball)
            self.game.send_channel_message(
                f"Balls to win so far: {Ball.describe_list(self.win_balls)}"
            )

        # Set message
        message = f"{player.get_name()} {self.ACTION_NAMES[self.action]}s the {ball.describe()}"

        # Move to next action
        if self.action == self.ACTION_BIN:
            self.action = self.ACTION_WIN
        else:
            self.action = self.ACTION_BIN
            self.player_id = (self.player_id + 1) % 2

        if len(self.available_balls) > 1:
            # Move to next input
            self.announce()
            return self, message
        else:
            # Move to next round
            binned = self.available_balls.pop()
            self.game.send_channel_message(f"The last ball binned is the {binned.describe()}")
            self.game.send_channel_message(f"Final balls to win: {Ball.describe_list(self.win_balls)}")
            return SplitStealState(self.game, self.win_balls), message


class SplitStealState(GameState):
    class Action(Enum):
        SPLIT = 0
        STEAL = 1

    actions: Dict[Player, Action]
    prize: int

    def __init__(self, game: "Game", initial_balls: Iterable[Ball]):
        super().__init__(game)

        self.actions = {}

        self.prize = 0
        for ball in initial_balls:
            self.prize = ball.apply(self.prize)
        
        self.game.send_channel_message(f"The final prize money is £{self.prize}. Choose whether to split or steal.")
    
    def handle_action(self, player: Player, action: Action) -> StateRet:
        if player in self.actions:
            return self, "You already chose your action."
        if player.current_game != self.game:
            return self, "You aren't in this game."
        
        self.actions[player] = action

        if len(self.actions) == len(self.game.players):
            steal_count = countOf(self.actions.values(), self.Action.STEAL)
            if steal_count == 2:
                self.game.send_channel_message(f"Both players stole, the money is lost.")
            elif steal_count == 1:
                if self.actions[self.game.players[0]] == self.Action.STEAL:
                    winner = self.game.players[0]
                else:
                    winner = self.game.players[1]
                
                self.game.send_channel_message(f"{winner.get_name()} steals all £{self.prize}.")
            else:
                prize = self.prize // 2
                self.game.send_channel_message(f"Both players split, they get £{prize}.")
            state = FinishedState(self.game)
        else:
            state = self

        return self, "Action chosen."
            

    def on_split(self, player: Player) -> StateRet:
        return self.handle_action(player, self.Action.SPLIT)

    def on_steal(self, player: Player) -> StateRet:
        return self.handle_action(player, self.Action.STEAL)


class FinishedState(GameState):
    def __init__(self, game: "Game"):
        super().__init__(game)

        for player in self.game.players:
            self.game.remove_player(player)

        self.game.finished = True


class Game(Generic[PlayerCtx]):
    # Current state of the game
    state: GameState

    # Players currently in the game
    players: List[Player[PlayerCtx]]

    # Queued messages to broadcast
    channel_messages: List[str]

    # Queued messages to send personally
    dms: DefaultDict[Player[PlayerCtx], List[str]]

    # The pool of balls in the machine
    machine_balls: List[CashBall]

    # Whether the game is over
    finished: bool

    # The results of the game, if finished
    results: Dict[Player[PlayerCtx], int]

    def __init__(self):
        self.players = []
        self.state = WaitingState(self)
        self.channel_messages = []
        self.dms = defaultdict(list)
        self.machine_balls = CashBall.generate_pool()
        self.finished = False
        self.results = {}

    def __str__(self) -> str:
        return f"Game({', '.join(str(player) for player in self.players)})"

    @staticmethod
    def start_game(host: Player) -> Tuple[Optional["Game"], str]:
        # Check game can be started
        if host.is_busy():
            return None, "You're already in a game."

        # Create a game with the host playing
        game = Game()
        host.join_game(game)

        return game, "Game started."

    def get_machine_ball(self) -> Ball:
        return pop_random(self.machine_balls)
    
    def remove_player(self, player: Player):
        player.current_game = None
        self.players.remove(player)

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
    
    def is_finished(self) -> bool:
        return self.finished

    def get_results(self) -> Dict[Player, int]:
        return self.results

    def on_join(self, player: Player) -> str:
        self.state, response = self.state.on_join(player)
        return response

    def on_vote(self, player: Player, target: Player) -> str:
        self.state, response = self.state.on_vote(player, target)
        return response
    
    def on_pick(self, player: Player, ball_id: int) -> str:
        self.state, response = self.state.on_pick(player, ball_id)
        return response

    def on_split(self, player: Player) -> str:
        self.state, response = self.state.on_split(player)
        return response

    def on_steal(self, player: Player) -> str:
        self.state, response = self.state.on_steal(player)
        return response
    
    def on_leave(self, player: Player) -> str:
        self.state, response = self.state.on_leave(player)
        return response
