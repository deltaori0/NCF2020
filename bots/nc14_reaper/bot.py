
__author__ = '홍은수 (deltaori0@korea.ac.kr)'

import os

os.environ['MKL_DEBUG_CPU_TYPE'] = '5'
os.environ['OMP_NUM_THREADS'] = '1'
os.environ['MKL_NUM_THREADS'] = '1'
import pathlib
import pickle
import time

import nest_asyncio
import numpy as np
import sc2
import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim
from IPython import embed
from sc2.data import Result
from sc2.ids.ability_id import AbilityId
from sc2.ids.buff_id import BuffId
from sc2.ids.unit_typeid import UnitTypeId
from sc2.player import Bot as _Bot
from sc2.position import Point2
from termcolor import colored, cprint

nest_asyncio.apply()


class Bot(sc2.BotAI):
    def __init__(self):
        super().__init__()

    def on_start(self):
        self.evoked = dict()


    async def on_step(self, iteration: int):
        actions = list() # 이번 step에 실행할 액션 목록

        cc = self.units(UnitTypeId.COMMANDCENTER).first
        combat_units = self.units.exclude_type([UnitTypeId.COMMANDCENTER, UnitTypeId.MEDIVAC])
        # cc_abilities = await self.get_available_abilities(cc)
        # reapers = self.units(UnitTypeId.REAPER)
        enemy_cc = self.enemy_start_locations[0]  # 적 시작 위치

        # 사령부 명령
        if self.can_afford(UnitTypeId.REAPER) and self.time - self.evoked.get((cc.tag, 'train'), 0) > 1.0:
            # 사신 생산 가능하고, 마지막 명령을 발행한지 1초 이상 지났음
            actions.append(cc.train(UnitTypeId.REAPER))
            self.evoked[(cc.tag, 'train')] = self.time

        # 유닛 명령
        for unit in self.units.not_structure:  # 건물이 아닌 유닛만 선택
            enemy_unit = self.enemy_start_locations[0]
            if self.known_enemy_units.exists:
                enemy_unit = self.known_enemy_units.closest_to(unit)  # 가장 가까운 적 유닛        

            # 적 사령부와 가장 가까운 적 유닛중 더 가까운 것을 목표로 설정
            if unit.distance_to(enemy_cc) < unit.distance_to(enemy_unit):
                target = enemy_cc
            else:
                target = enemy_unit

            if combat_units.amount > 10:
                actions.append(unit.attack(target))
            else:
                defense_position = self.start_location + 0.25 * (enemy_cc.position - self.start_location)
                actions.append(unit.attack(defense_position))         
            
            if unit.type_id is UnitTypeId.REAPER:
                reaper_abilities = await self.get_available_abilities(unit)
                # print(reaper_abilities)
                
                # KD8 지뢰 (일정 시간 후 폭발하여 5의 피해를 줌)
                actions.append(unit(AbilityId.KD8CHARGE_KD8CHARGE, target=target))

                # 체력 50퍼센트 이하가 되면 전투 피하기 - 자동 체력 회복              
                if unit.health_percentage < 0.5:
                    actions.append(unit(AbilityId.MOVE_MOVE, target=cc))


        await self.do_actions(actions)
 
