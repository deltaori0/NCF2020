
from s2clientprotocol import sc2api_pb2 as sc_pb
from sc2.player import Computer
import logging
logger = logging.getLogger(__name__)


# sc2.controller.Controller 클래스 재정의
async def create_game(self, game_map, players, realtime, random_seed=None):
    assert isinstance(realtime, bool)

    # MOD START: hspark8312 #
    if type(game_map) is str:
        # 문자열로 입력된 파일 경로 처리
        import os
        from collections import namedtuple
        gm = namedtuple('game_map', 'relative_path, name')
        if game_map.endswith('.SC2Map'):
            game_map = gm(
                os.path.abspath(game_map), 
                os.path.basename(game_map).split('.')[0])
        else:
            game_map = gm(
                os.path.abspath(game_map) + '.SC2Map', 
                os.path.basename(game_map))
    # MOD END: hspark8312 #

    req = sc_pb.RequestCreateGame(
        local_map=sc_pb.LocalMap(
            map_path=str(game_map.relative_path)
        ),
        realtime=realtime
    )
    if random_seed is not None:
        req.random_seed = random_seed

    for player in players:
        p = req.player_setup.add()
        p.type = player.type.value
        if isinstance(player, Computer):
            p.race = player.race.value
            p.difficulty = player.difficulty.value

    logger.info("Creating new game")
    logger.info(f"Map:     {game_map.name}")
    logger.info(f"Players: {', '.join(str(p) for p in players)}")
    result = await self._execute(create_game=req)
    return result
