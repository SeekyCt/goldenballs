from abc import ABC, abstractmethod
from collections import Counter, defaultdict
from enum import Enum, IntEnum
from operator import countOf
from typing import DefaultDict, Dict, Generic, Iterable, List, Optional, Tuple, Type, TypeVar

from goldenballs.messages import get_msg
from goldenballs.util import pop_random


PlayerCtx = TypeVar("PlayerCtx")

# New state, response message
StateRet = Tuple["GameState", str]

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
        return get_msg("ball.killer")
    
    def apply(self, prize: int) -> int:
        return round(prize / 10)

class CashBall(Ball):
    """A ball that adds cash to the prize"""

    # Cash value of this ball
    value: int

    def __init__(self, value: int):
        super().__init__()

        self.value = value
    
    def __repr__(self) -> str:
        return f"Ball({self.value})"
    
    def describe(self) -> str:
        return get_msg("ball.cash", value=self.value)

    def apply(self, prize) -> int:
        return prize + self.value

    @staticmethod
    def generate_pool() -> List["CashBall"]:
        """Generates the initial pool of 100 cash balls"""

        values = [
                10,    20,      25,     30,     40,    50,      60,     70,
                75,    80,      90,    100,    125,   150,     175,    200,
               250,   300,     350,    400,    450,   500,     550,    600,
               650,   700,     750,    800,    850,   900,     950,  1_000,
             1_100,  1_200,  1_250,  1_300,  1_400,  1_500,  1_600,  1_700,
             1_750,  1_800,  1_900,  2_000,  2_500,  3_000,  4_000,  5_000,
             5_500,  6_000,  6_500,  7_000,  7_500,  8_000,  8_500,  9_000,
             9_500, 10_000, 11_000, 12_000, 13_000, 14_000, 15_000, 16_000,
            17_000, 18_000, 19_000, 20_000, 21_000, 22_000, 23_000, 24_000,
            25_000, 26_000, 27_000, 28_000, 29_000, 30_000, 31_000, 32_000,
            33_000, 34_000, 35_000, 37_000, 38_000, 40_000, 42_000, 44_000,
            45_000, 48_000, 49_000, 50_000, 51_000, 53_000, 55_000, 57_000,
            60_000, 61_000, 65_000, 67_000, 70_000, 75_000,
        ]

        return [CashBall(val) for val in values]


class Player(Generic[PlayerCtx]):
    """A player, who may exist in a game"""

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
        """Checks if the player is in a game"""

        return self.current_game is not None

    def get_name(self):
        """Gets the display name for the player"""

        return self.name

    def __repr__(self):
        return f"{self.get_name()}[{self.current_game is not None}]"


class GameState(ABC):
    """Abstract state for the golden ball game

    Default event handlers - all stubbed except for leaving"""

    game: "Game"

    def __init__(self, game: "Game"):
        self.game = game

    def _require_playing(self, player: Player, you=True) -> Optional[StateRet]:
        """Returns an error if the player is not playing"""

        if player.current_game != self.game:
            msg = "player.err.not_in_game" if you else "player.err.not_in_game.other"
            return self, get_msg(msg, name=player.get_name())
        else:
            return None

    def on_join(self, player: Player) -> StateRet:
        """Update function for when a player tries to join"""

        return self, get_msg("game.err.not_joinable")

    def on_vote(self, player: Player, target: Player) -> StateRet:
        """Update function for when a player tries to vote"""

        return self, get_msg("game.err.not_votable")

    def on_view_balls(self, player: Player) -> StateRet:
        """Update function for when a player tries to view their hidden balls"""

        return self, get_msg("game.err.not_viewable")

    def on_pick(self, player: Player, ball_id: int) -> StateRet:
        """Update function for when a player tries to pick a ball"""

        return self, get_msg("game.err.not_pickable")
    
    def on_split(self, player: Player) -> StateRet:
        """Update function for when a player tries to split"""

        return self, get_msg("game.err.not_split_steal")
    
    def on_steal(self, player: Player) -> StateRet:
        """Update function for when a player tries to steal"""

        return self, get_msg("game.err.not_split_steal")
    
    def on_leave(self, player: Player) -> StateRet:
        """Update function for when a player tries to leave"""

        # Check player is in the game
        if ret := self._require_playing(player):
            return ret

        # Remove the player
        self.game._remove_player(player)

        # Cancel the game if no players are left
        if len(self.game.players) == 0:
            self.game._send_channel_message(get_msg("game.cancelled"))
            state = FinishedState(self.game)
        else:
            state = self

        return self, get_msg("game.left")


class WaitingState(GameState):
    """State for waiting for all players to join"""

    PLAYER_COUNT = 4

    def on_join(self, player: Player) -> StateRet:
        # Check player can join
        if player in self.game.players:
            return self, get_msg("player.err.in_game")
        if player.is_busy():
            return self, get_msg("player.err.in_other_game")

        # Add player to game
        self.game._add_player(player)

        # Start game if enough players are gathered
        if len(self.game.players) == self.PLAYER_COUNT:
            self.game._send_channel_message(
                get_msg("game.start", players=', '.join(player.get_name() for player in self.game.players))
            )
            state = FourPlayerState(self.game)
        else:
            state = self

        return state, get_msg("game.join")
    

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
            balls.append(self.game._get_machine_ball())
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
        self.game._send_channel_message(
            get_msg(
                "round1_2.announce",
                total=shown_count + hidden_count,
                hidden=hidden_count,
                shown=shown_count,
                shown_list='\n'.join(
                    get_msg(
                        "player.ball_list",
                        name=player.get_name(),
                        balls=Ball.describe_list(self.shown_balls[player])
                    )
                    for player in self.game.players
                )
            )
        )

        # Send players their hidden balls
        for player in self.game.players:
            self.game._send_dm(player, get_msg("round1_2.hidden", balls=Ball.describe_list(self.hidden_balls[player])))

        # Init votes
        self.votes = {}

    def _start_next(self, loser: Player) -> GameState:
        # Remove the loser
        self.game._remove_player(loser)

        # Build new ball list
        balls = []
        for player in self.game.players:
            for ball in self.shown_balls[player]:
                balls.append(ball)
            for ball in self.hidden_balls[player]:
                balls.append(ball)

        # Move to next state
        return self.next_state(self.game, balls)

    def on_vote(self, player: Player, target: Player) -> StateRet:
        # Check the vote is valid
        if player in self.votes:
            return self, get_msg("player.err.voted")
        if player == target:
            return self, get_msg("player.err.vote_self")
        if ret := self._require_playing(player):
            return ret
        if ret := self._require_playing(target, False):
            return ret

        # Register vote
        self.votes[player] = target

        # Announce vote
        self.game._send_channel_message(get_msg("round1_2.voted", name=player.get_name()))

        # Check for all votes being ready
        if len(self.votes) == len(self.game.players):
            # Find who was voted off
            loser = Counter(self.votes.values()).most_common()[0][0]

            # Announce the votes
            self.game._send_channel_message(
                get_msg(
                    "round1_2.done",
                    votes='\n'.join(
                        get_msg("round1_2.vote_entry", name=player.get_name())
                        for player in self.votes.values()
                    ),
                    loser=loser.get_name(),
                    hidden='\n'.join(
                        get_msg(
                            "player.ball_list",
                            name=player.get_name(),
                            balls=Ball.describe_list(self.hidden_balls[player])
                        )
                        for player in self.game.players
                    ),
                )
            )

            # Move to next state
            state = self._start_next(loser)
        else:
            state = self

        return state, get_msg("round1_2.voted_response")
    
    def on_view_balls(self, player: Player) -> StateRet:
        return self, get_msg("round1_2.hidden", balls=Ball.describe_list(self.hidden_balls[player]))
    
    def on_leave(self, player: Player) -> StateRet:
        # Check player is in the game
        if ret := self._require_playing(player):
            return ret

        # Announce the round ending
        self.game._send_channel_message(
            get_msg(
                "round1_2.done_early",
                loser=player.get_name(),
                hidden='\n'.join(
                    get_msg(
                        "player.ball_list",
                        name=player.get_name(),
                        balls=Ball.describe_list(self.hidden_balls[player])
                    )
                    for player in self.game.players
                ),
            )
        )        

        # Remove player and move to next state
        state = self._start_next(player)

        return state, get_msg("game.left")


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
    class Action(IntEnum):
        BIN = 0
        WIN = 1

        def pick_msg(self):
            return [
                "round3.pick.bin",
                "round3.pick.win"
            ][self]
        
        def picked_msg(self):
            return [
                "round3.picked.bin",
                "round3.picked.win"
            ][self]

    action: Action
    player_id: int
    win_balls: List[Ball]
    available_balls: List[Ball]

    def __init__(self, game: "Game", initial_balls: List[Ball]):
        super().__init__(game)

        self.action = self.Action.BIN
        self.player_id = 0
        self.win_balls = []
        self.available_balls = list(initial_balls)
        self.available_balls.append(KillerBall())

        self._announce()
    
    def _announce(self):
        self.game._send_channel_message(
            get_msg(
                self.action.pick_msg(),
                name=self._get_player().get_name(),
                max=len(self.available_balls),
            )
        )

    def _get_player(self):
        return self.game.players[self.player_id]

    def on_pick(self, player: Player, ball_id: int) -> StateRet:
        # Check the pick is valid
        if ret := self._require_playing(player):
            return ret
        if player != self._get_player():
            return self, get_msg("player.err.not_picking")
        idx = ball_id - 1
        if not (0 <= idx < len(self.available_balls)):
            return self, get_msg("ball.err.invalid")
        
        # Remove the ball from the pool
        ball = self.available_balls.pop(idx)
        if self.action == self.Action.WIN:
            self.win_balls.append(ball)
            self.game._send_channel_message(
                get_msg(
                    "round3.win_so_far",
                    balls=Ball.describe_list(self.win_balls)
                )
            )

        # Set message
        message = get_msg(
            self.action.picked_msg(),
            name=player.get_name(),
            ball=ball.describe(),
        )

        # Move to next action
        if self.action == self.Action.BIN:
            self.action = self.Action.WIN
        else:
            self.action = self.Action.BIN
            self.player_id = (self.player_id + 1) % len(self.game.players)

        if len(self.available_balls) > 1:
            # Move to next input
            self._announce()
            return self, message
        else:
            # Move to next round
            binned = self.available_balls.pop()
            self.game._send_channel_message(
                get_msg("round3.final_bin", ball=binned.describe())
            )
            self.game._send_channel_message(
                get_msg("round3.final_win", balls=Ball.describe_list(self.win_balls))
            )
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

        # Calculate total prize
        self.prize = 0
        for ball in initial_balls:
            self.prize = ball.apply(self.prize)
        
        self.game._send_channel_message(get_msg("round4.announce", prize=self.prize))
 
    def _handle_action(self, player: Player, action: Action) -> StateRet:
        # Check action is valid
        if ret := self._require_playing(player):
            return ret
        if player in self.actions:
            return self, get_msg("player.err.action_done")

        # Set player's action
        self.actions[player] = action

        if len(self.actions) == len(self.game.players):
            state = self._finish_game()
        else:
            state = self

        return state, get_msg("round4.action_response")

    def _finish_game(self) -> GameState:
        # Determine winnings
        if len(self.game.players) == 1:
            winner = self.game.players[0]
            self.game.results = {winner : self.prize}
            self.game._send_channel_message(
                get_msg("round4.only_player", winner=winner.get_name(), prize=self.prize)
            )
        else:
            steal_count = countOf(self.actions.values(), self.Action.STEAL)
            if steal_count == 2:
                self.game.results = {}
                self.game._send_channel_message(get_msg("round4.lose"))
            elif steal_count == 1:
                if self.actions[self.game.players[0]] == self.Action.STEAL:
                    winner = self.game.players[0]
                else:
                    winner = self.game.players[1]
                self.game.results = {winner : self.prize}
                self.game._send_channel_message(
                    get_msg("round4.steal", winner=winner.get_name(), prize=self.prize)
                )
            else:
                prize = self.prize // 2
                self.game.results = {player : prize for player in self.game.players}
                self.game._send_channel_message(
                    get_msg("round4.split", prize=self.prize)
                )

        return FinishedState(self.game)

    def on_split(self, player: Player) -> StateRet:
        return self._handle_action(player, self.Action.SPLIT)

    def on_steal(self, player: Player) -> StateRet:
        return self._handle_action(player, self.Action.STEAL)
    
    def on_leave(self, player: Player) -> StateRet:
        state, msg = super().on_leave(player)

        if len(self.game.players) == 1:
            state = self._finish_game()

        return state, msg


class FinishedState(GameState):
    def __init__(self, game: "Game"):
        super().__init__(game)

        # Remove all players from the game
        for player in self.game.players:
            self.game._remove_player(player)

        # Flag the game as finished
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
        """Tries to start a game with the host included"""

        # Check game can be started
        if host.is_busy():
            return None, get_msg("player.err.in_other_game")

        # Create a game with the host playing
        game = Game()
        game._add_player(host)

        return game, get_msg("game.start_response")

    def _add_player(self, player: Player):
        """Adds a player to the game"""

        player.current_game = self
        self.players.append(player)

    def _remove_player(self, player: Player):
        """Adds a player to the game"""

        player.current_game = None
        self.players.remove(player)

    def _get_machine_ball(self) -> Ball:
        """Gets a random ball from the machine"""

        return pop_random(self.machine_balls)

    def _send_channel_message(self, msg: str):
        """Sends a broadcast message"""

        self.channel_messages.append(msg)

    def get_channel_message(self) -> Optional[str]:
        """Gets a channel message, if any are queued"""

        if len(self.channel_messages) > 0:
            return self.channel_messages.pop(0)
        else:
            return None

    def _send_dm(self, player: Player, msg: str):
        """Sends a personal message to a player"""

        self.dms[player].append(msg)
    
    def get_dm_subjects(self) -> Iterable[Player]:
        """Gets all players who have dms queued"""

        return self.dms.keys()

    def get_dm(self, player: Player) -> Optional[str]:
        """Gets a personal message for a player, if any are queued"""

        if len(self.dms[player]) > 0:
            return self.dms[player].pop(0)
        else:
            return None
    
    def is_finished(self) -> bool:
        """Checks if the game is finised"""
        return self.finished

    def get_results(self) -> Dict[Player, int]:
        """Gets the money given to each plpayer"""

        assert self.is_finished(), f"Can't get results of an unfinished game"
        return self.results

    def on_join(self, player: Player) -> str:
        """Handles a player trying to join the game"""

        self.state, response = self.state.on_join(player)
        return response

    def on_vote(self, player: Player, target: Player) -> str:
        """Handles a player trying to vote in the game"""

        self.state, response = self.state.on_vote(player, target)
        return response
    
    def on_view_balls(self, player: Player) -> str:
        """Handles a player trying to view their hidden balls"""

        self.state, response = self.state.on_view_balls(player)
        return response
    
    def on_pick(self, player: Player, ball_id: int) -> str:
        """Handles a player trying to pick a ball"""

        self.state, response = self.state.on_pick(player, ball_id)
        return response

    def on_split(self, player: Player) -> str:
        """Handles a player trying to split the prize"""

        self.state, response = self.state.on_split(player)
        return response

    def on_steal(self, player: Player) -> str:
        """Handles a player trying to steal the prize"""

        self.state, response = self.state.on_steal(player)
        return response
    
    def on_leave(self, player: Player) -> str:
        """Handles a player trying to leave the game"""

        self.state, response = self.state.on_leave(player)
        return response
