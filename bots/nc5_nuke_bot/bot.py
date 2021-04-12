
__author__ = '박현수 (hspark8312@ncsoft.com), NCSOFT Game AI Lab'


# python -m bots.nc_example_v5.bot --server=172.20.41.105
# kill -9 $(ps ax | grep SC2_x64 | fgrep -v grep | awk '{ print $1 }')
# kill -9 $(ps ax | grep bots.nc_example_v5.bot | fgrep -v grep | awk '{ print $1 }')
# ps aux

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
    """
    example v1과 유사하지만, 빌드 오더 대신, 유닛 비율을 맞추도록 유닛을 생산함
    """
    def __init__(self):
        super().__init__()

    def on_start(self):
        self.cc = self.units(UnitTypeId.COMMANDCENTER).first
        if self.start_location.distance_to(Point2((32.5, 31.5))) < 5.0:
            self.enemy_cc = Point2(Point2((95.5, 31.5)))
        else:
            self.enemy_cc = Point2(Point2((32.5, 31.5)))

    async def on_step(self, iteration: int):
        """

        """
        actions = list() # 이번 step에 실행할 액션 목록

        cc = self.units(UnitTypeId.COMMANDCENTER).first
        cc_abilities = await self.get_available_abilities(cc)
        ghosts = self.units(UnitTypeId.GHOST)
        
        if ghosts.amount == 0:
            if AbilityId.BARRACKSTRAIN_GHOST in cc_abilities:
                # 고스트가 하나도 없으면 고스트 훈련
                actions.append(cc.train(UnitTypeId.GHOST))

        elif ghosts.amount > 0:
            if AbilityId.BUILD_NUKE in cc_abilities:
                # 전술핵 생산 가능(자원이 충분)하면 전술핵 생산
                actions.append(cc(AbilityId.BUILD_NUKE))

            ghost_abilities = await self.get_available_abilities(ghosts.first)
            print(ghost_abilities)
            if AbilityId.TACNUKESTRIKE_NUKECALLDOWN in ghost_abilities and ghosts.first.is_idle:
                # 전술핵 발사 가능(생산완료)하고 고스트가 idle 상태이면, 적 본진에 전술핵 발사
                actions.append(ghosts.first(AbilityId.BEHAVIOR_CLOAKON_GHOST))
                actions.append(ghosts.first(AbilityId.TACNUKESTRIKE_NUKECALLDOWN, target=self.enemy_cc))
            
            if AbilityId.EMP_EMP in ghost_abilities and ghosts.first.is_idle:
                actions.append(ghosts.first(AbilityId.EMP_EMP, target=self.enemy_cc))

        await self.do_actions(actions)
