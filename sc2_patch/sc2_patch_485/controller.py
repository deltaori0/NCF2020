
"""
코드 내부에 주석으로 변경된 부분 표시
"""

__author__ = "박현수(hspark8312@ncsoft.com), NCSOFT Game AI Lab"


from s2clientprotocol import sc2api_pb2 as sc_pb
from sc2.player import Computer
import logging
logger = logging.getLogger(__name__)


# sc2.controller.Controller 클래스 재정의
async def create_game(self, game_map, players, realtime, random_seed=None):
    assert isinstance(realtime, bool)

    # hspark: start #
    if type(game_map) is str:
        # 기존플랫폼은 반드시 StarCraftII/Maps 폴더에 지도가 있어야 하지만,
        # 문자열로 직접 경로를 입력해도 처리 할 수 있도록 수정
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
    # hspark: end #

    req = sc_pb.RequestCreateGame(local_map=sc_pb.LocalMap(map_path=str(game_map.relative_path)), realtime=realtime)
    if random_seed is not None:
        req.random_seed = random_seed

    for player in players:
        p = req.player_setup.add()
        p.type = player.type.value
        if isinstance(player, Computer):
            p.race = player.race.value
            p.difficulty = player.difficulty.value
            p.ai_build = player.ai_build.value

    logger.info("Creating new game")
    logger.info(f"Map:     {game_map.name}")
    logger.info(f"Players: {', '.join(str(p) for p in players)}")
    result = await self._execute(create_game=req)
    return result
