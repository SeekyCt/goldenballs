from goldenballs.game import Player, Game

if __name__ == '__main__':
    game, msg = Game.start_game(Player("Host"))
    assert game is not None
    print(msg)
    for player in [Player(f"Player {i}") for i in range(1, 4)]:
        print(game.on_join(player))

    # Round 1
    print(game.on_vote(game.players[0], game.players[1]))
    for player in game.players[1:]:
        print(game.on_vote(player, game.players[0]))
    while msg := game.get_channel_message():
        print(msg)

    # Round 2
    print(game.on_vote(game.players[0], game.players[1]))
    for player in game.players[1:]:
        print(game.on_vote(player, game.players[0]))
    while msg := game.get_channel_message():
        print(msg)
    
    # Round 3
    for i in range(11):
        player = game.players[(i // 2) % 2]
        print(game.on_pick(player, 1))
    while msg := game.get_channel_message():
        print(msg)
    
    # Round 4
    for player in game.players:
        game.on_split(player)
    while msg := game.get_channel_message():
        print(msg)
    
    print(game.get_results())
    assert game.is_finished()
    
