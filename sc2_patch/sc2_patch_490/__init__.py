
"""
경진대회 플랫폼 목적에 맞게 python-sc2의 기본 동작을 수정할 필요가 있음
여기에는 실행시간에 python-sc2의 행동을 수정하기 위한 코드가 있음
이 모듈은 반드시 sc2 (python-sc2) 보다 먼저 import 되어야 함

향후, 여기서 부정행위(예. API로 시야밖의 적 정보 확인, 적 유닛 파괴)에 
사용할 수 있는 API를 사용하지 못하도록 막을 예정
"""

__author__ = "박현수(hspark8312@ncsoft.com), NCSOFT Game AI Lab"


import sys
import inspect
from importlib.machinery import (
    PathFinder, 
    ModuleSpec, 
    SourceFileLoader)


class Finder(PathFinder):
    def __init__(self, module_name):
        self.module_name = module_name

    def find_spec(self, fullname, path=None, target=None):
        if fullname == self.module_name:
            # 변경할 모듈의 로더를 교체
            spec = super().find_spec(fullname, path, target)
            loader = CustomLoader(fullname, spec.origin)
            return ModuleSpec(fullname, loader)


class CustomLoader(SourceFileLoader):
    def exec_module(self, module):
        super().exec_module(module)
        print(f'패치 {module.__name__}')
        if module.__name__ == 'sc2.main':
            module = sc2_main_patcher(module)
        elif module.__name__ == 'sc2.controller':
            module = sc2_controller_patcher(module)
        elif module.__name__ == 'sc2.client':
            module = sc2_client_patcher(module)
        elif module.__name__ == 'sc2.bot_ai':
            module = sc2_bot_ai_patcher(module)
        elif module.__name__ == 'sc2.ids.ability_id':
            module = sc2_ids_ability_id_patcher(module)
        elif module.__name__ == 'sc2.game_state':
            module = sc2_game_state_patcher(module)
        return module


def sc2_main_patcher(module):
    from . import main
    module.run_game = main.run_game
    module._play_game = main._play_game
    module._play_game_ai = main._play_game_ai
    module._join_game = main._join_game
    return module


def sc2_controller_patcher(module):
    from . import controller
    module.Controller.create_game = controller.create_game
    return module


def sc2_client_patcher(module):
    from . import client
    module.Client.join_game = client.join_game
    return module


def sc2_bot_ai_patcher(module):
    from . import bot_ai
    module.BotAI.known_enemy_units = bot_ai.known_enemy_units
    return module


def sc2_ids_ability_id_patcher(module):
    from .ids import ability_id
    module.AbilityId = ability_id.AbilityId
    return module


def sc2_game_state_patcher(module):
    from . import game_state
    module.GameState = game_state.GameState
    return module


def patch():
    sys.meta_path.insert(0, Finder('sc2.main'))
    sys.meta_path.insert(0, Finder('sc2.controller'))
    sys.meta_path.insert(0, Finder('sc2.client'))
    sys.meta_path.insert(0, Finder('sc2.bot_ai'))
    sys.meta_path.insert(0, Finder('sc2.ids.ability_id'))
    sys.meta_path.insert(0, Finder('sc2.game_state'))

patch()