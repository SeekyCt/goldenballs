MESSAGES = {
    # extension.py

    "dm.err.fail" : "Error sending dm to {name}: {exception}",

    "channel.err.no_game" : "Error: there's no game in this channel.",
    "channel.err.game" : "Error: there's already a game in this channel.",

    "user.err.no_game" : "Error: you're not in a game.",

    # game.py

    "ball.killer" : "Killer Ball",
    "ball.cash" : "£{value} Ball",
    "ball.err.invalid" : "That's not a valid ball.",

    "player.ball_list" : "    {name} - {balls}",
    "player.err.in_game" : "You're already in this game,",
    "player.err.in_other_game" : "You're already in another game.",
    "player.err.not_in_game" : "You're not in this game.",
    "player.err.not_in_game.other" : "{name} is not in this game.",
    "player.err.not_picking" : "It's not your turn to pick",
    "player.err.voted" : "You already voted.",
    "player.err.vote_self" : "You can't vote for yourself.",
    "player.err.action_done" : "You already chose your action.",

    "game.join" : "You joined the game.",
    "game.left" : "You left the game.",
    "game.start_response" : "Game started.",
    "game.start" : "Game starting with {players}",
    "game.cancelled" : "All players have left, game cancelled.",
    "game.err.not_joinable" : "The game is not joinable.",
    "game.err.not_votable" : "The game is not in the voting stage.",
    "game.err.not_viewable" : "You don't have any hidden balls to view.",
    "game.err.not_pickable" : "The game is not in the picking stage.",
    "game.err.not_split_steal" : "The game is not in the split/steal stage.",
    
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
    "round1_2.done_early" : '\n'.join((
        "{loser} left early, moving to the next round.",
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
}

def get_msg(message_id: str, **kwargs) -> str:
    msg = MESSAGES.get(message_id)
    if msg is None:
        msg = "[Missing message]"
        print(f"Error: missing message {message_id}")
    return msg.format(**kwargs)
