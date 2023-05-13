from abc import ABC
from typing import Generic, List, Optional, Tuple, TypeVar


ContextType = TypeVar("ContextType")

# New state, response message
StateRet = Tuple["GameState", Optional[str]]

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
    
    def __str__(self):
        return f"{self.get_name()}[{self.current_game}]"


class GameState(ABC):
    game: "Game"

    def __init__(self, game: "Game"):
        self.game = game

    def on_join(self, player: Player) -> StateRet:
        """Update function for when a player tries to join"""

        return self, "Game is not joinable."

    def on_dm(self, player: Player, message: str) -> StateRet:
        """Update function for when a player sends a dm"""

        return self, "Not implemented."


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
            state = FourPlayerState(self.game)
            self.game._send_message(
                f"Game starting with {', '.join(player.get_name() for player in self.game.players)}"
            )
        else:
            state = self

        return state, "You joined the game."


class FourPlayerState(GameState):
    async def on_dm(self, player: Player, message: str) -> StateRet:
        return self, message


class Game():
    players: List[Player]
    state: GameState
    messages: List[str]

    def __init__(self):
        self.players = []
        self.state = WaitingState(self)
        self.messages = []

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

    def on_dm(self, player: Player, message) -> Optional[str]:
        self.state, response = self.state.on_dm(player, message)
        return response

    def _send_message(self, msg: str):
        self.messages.append(msg)

    def has_message(self) -> bool:
        return len(self.messages) > 0
    
    def get_message(self) -> str:
        return self.messages.pop(0)
