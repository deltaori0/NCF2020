
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
        # cc_abilities = await self.get_available_abilities(cc)
        # thors = self.units(UnitTypeId.THOR)
        enemy_cc = self.enemy_start_locations[0]  # 적 시작 위치

        # 사령부 명령
        if self.can_afford(UnitTypeId.THOR) and self.time - self.evoked.get((cc.tag, 'train'), 0) > 1.0:
            # 토르 생산 가능하고, 마지막 명령을 발행한지 1초 이상 지났음
            actions.append(cc.train(UnitTypeId.THOR))
            self.evoked[(cc.tag, 'train')] = self.time

        # 유닛 명령
        for unit in self.units.not_structure:  # 건물이 아닌 유닛만 선택
            enemy_unit = self.enemy_start_locations[0]
            if self.known_enemy_units.exists:
                enemy_unit = self.known_enemy_units.closest_to(unit)  # 가장 가까운 적 유닛        

            # 적 사령부와 가장 가까운 적 유닛중 더 가까운 것을 목표로 설정
            if unit.distance_to(enemy_cc) < unit.distance_to(enemy_unit):
                target = enemy_cc
                flying_enemy = False
            else:
                target = enemy_unit
                try:
                    if target.is_flying:
                        flying_enemy = True
                    else:
                        flying_enemy = False
                except:
                    flying_enemy = False
            
            if unit.type_id is UnitTypeId.THOR:
                thor_ability = await self.get_available_abilities(unit)
                # print(thor_ability)
                # 고충격 탄두 활성화 (공중 유닛 단일 공격)
                # print('target', target, 'is_flying=', flying_enemy)
                if flying_enemy:
                    actions.append(unit(AbilityId.MORPH_THORHIGHIMPACTMODE))
                else:   # 재블린 미사일
                    actions.append(unit(AbilityId.MORPH_THOREXPLOSIVEMODE))
                    
                actions.append(unit.attack(target))

        await self.do_actions(actions)
 
