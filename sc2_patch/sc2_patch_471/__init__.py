
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
            spec = super().find_spec(fullname, path, target)
            loader = CustomLoader(fullname, spec.origin)
            return ModuleSpec(fullname, loader)


class CustomLoader(SourceFileLoader):
    def exec_module(self, module):
        super().exec_module(module)
        if module.__name__ == 'sc2.main':
            module = sc2_main_patcher(module)
        elif module.__name__ == 'sc2.controller':
            module = sc2_controller_patcher(module)
        elif module.__name__ == 'sc2.client':
            module = sc2_client_patcher(module)
        elif module.__name__ == 'sc2.bot_ai':
            module = sc2_bot_ai_patcher(module)
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


def patch():
    sys.meta_path.insert(0, Finder('sc2.main'))
    sys.meta_path.insert(0, Finder('sc2.controller'))
    sys.meta_path.insert(0, Finder('sc2.client'))
    sys.meta_path.insert(0, Finder('sc2.bot_ai'))

patch()