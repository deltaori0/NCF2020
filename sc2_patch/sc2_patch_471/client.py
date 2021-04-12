
from s2clientprotocol import (
    sc2api_pb2 as sc_pb,
    common_pb2 as common_pb,
    query_pb2 as query_pb,
    debug_pb2 as debug_pb,
    raw_pb2 as raw_pb,
)

import logging

from sc2.ids.ability_id import AbilityId
from sc2.ids.unit_typeid import UnitTypeId
from sc2.renderer import Renderer
from sc2.data import Race

logger = logging.getLogger(__name__)


async def join_game(self, name=None, race=None, observed_player_id=None, portconfig=None, rgb_render_config=None):
    ifopts = sc_pb.InterfaceOptions(raw=True, score=True)
    
    # hspark: begin
    from sc2_data import consts
    map_width, map_height = consts.SC2.feature_layer_resolution
    minimap_width, minimap_height = consts.SC2.feature_layer_minimap_resolution

    ifopts.feature_layer.width = consts.SC2.feature_layer_width
    ifopts.feature_layer.resolution.x = map_width
    ifopts.feature_layer.resolution.y = map_height
    ifopts.feature_layer.minimap_resolution.x = minimap_width
    ifopts.feature_layer.minimap_resolution.y = minimap_height
    # hspark: end

    if rgb_render_config:
        assert isinstance(rgb_render_config, dict)
        assert 'window_size' in rgb_render_config and 'minimap_size' in rgb_render_config
        window_size = rgb_render_config['window_size']
        minimap_size = rgb_render_config['minimap_size']
        
        # hspark: begin
        import platform
        if platform.system().lower() != 'windows':
            self._renderer = Renderer(self, window_size, minimap_size)
        # hspark: end
        
        map_width, map_height = window_size
        minimap_width, minimap_height = minimap_size

        ifopts.render.resolution.x = map_width
        ifopts.render.resolution.y = map_height
        ifopts.render.minimap_resolution.x = minimap_width
        ifopts.render.minimap_resolution.y = minimap_height

    if race is None:
        assert isinstance(observed_player_id, int)
        # join as observer
        req = sc_pb.RequestJoinGame(observed_player_id=observed_player_id, options=ifopts)
    else:
        assert isinstance(race, Race)
        req = sc_pb.RequestJoinGame(race=race.value, options=ifopts)

    if portconfig:
        req.shared_port = portconfig.shared
        req.server_ports.game_port = portconfig.server[0]
        req.server_ports.base_port = portconfig.server[1]

        for ppc in portconfig.players:
            p = req.client_ports.add()
            p.game_port = ppc[0]
            p.base_port = ppc[1]

    if name is not None:
        assert isinstance(name, str)
        req.player_name = name

    result = await self._execute(join_game=req)
    self._game_result = None
    self._player_id = result.join_game.player_id
    return result.join_game.player_id

