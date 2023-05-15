MESSAGES = {
    # extension.py

    "err.dm.fail" : "Error sending dm to {name}: {exception}",

    "err.channel.no_game" : "Error: there's no game in this channel.",
    "err.channel.game" : "Error: there's already a game in this channel.",

    "err.user.no_game" : "Error: you're not in a game.",

    # game.py

    "ball.killer" : "Killer Ball",
    "ball.cash" : "£{value} Ball",

    # TODO: -> err.player
    "err.game.player_in" : "You're already in this game,",
    "err.game.player_in.other" : "You're already in another game.",
    "err.game.player_not_in" : "{name} is not in this game.",
    "err.game.player_not_in.youre" : "You're not in this game.",
    "err.game.player_not_picking" : "It's not your turn to pick",
    "err.game.invalid_ball" : "That's not a valid ball.",

    "err.game.not_joinable" : "The game is not joinable.",
    "err.game.not_votable" : "The game is not in the voting stage.",
    "err.game.not_viewable" : "You don't have any hidden balls to view.",
    "err.game.not_pickable" : "The game is not in the picking stage.",
    "err.game.not_split_steal" : "The game is not in the split/steal stage.",

    "err.player.voted" : "You already voted.",
    "err.player.vote_self" : "You can't vote for yourself.",
    "err.player.action_done" : "You already chose your action.",

    "game.join" : "You joined the game.",
    "game.left" : "You left the game.",
    "game.start_response" : "Game started.",
    "game.start" : "Game starting with {players}",
    
    "round1_2.announce" : '\n'.join((
        "Everyone has been given {total} balls, {hidden} hidden and {shown} shown.",
        "The shown balls are:",
        "{shown_list}",
        "Your hidden balls will be sent in dms.",
        "Use /vote to pick a player to remove from the game, along with their balls."
    )),
    "round1_2.hidden" : "Your hidden balls are: {balls}",
    "round1_2.voted" : "{name} has voted.",
    "round1_2.voted_response" : "Vote registered.",
    "round1_2.vote_entry" : "    - {name}",
    "round1_2.done" : '\n'.join((
        "The votes are in:",
        "{votes}",
        "{loser} has been voted off.",
        "The hidden balls were:",
        "{hidden}",
    )),

    "round3.pick.win" : "{name}, pick a ball from 1-{max} to win.",
    "round3.pick.bin" : "{name}, pick a ball from 1-{max} to bin.",
    "round3.picked.win" : "{name} wins the {ball}",
    "round3.picked.bin" : "{name} bins the {ball}",
    "round3.win_so_far" : "Balls to win so far: {balls}",
    "round3.final_bin" : "The last balled binned is the {ball}",
    "round3.final_win" : "Final balls to win: {balls}",

    "round4.announce" : "The final prize money is £{prize}. Choose whether to /split or /steal.",
    "round4.lose" : "Both players stole, the money is lost.",
    "round4.steal" : "{winner} steals all £{prize}.",
    "round4.split" : "Both players split, they get £{prize}.",
    "round4.action_response" : "Action chosen.",

    "player.ball_list" : "    {name} - {balls}",
}

def get_msg(message_id: str, **kwargs) -> str:
    msg = MESSAGES.get(message_id)
    if msg is None:
        msg = "[Missing message]"
        print(f"Error: missing message {message_id}")
    return msg.format(**kwargs)
