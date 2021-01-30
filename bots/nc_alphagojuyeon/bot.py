
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

from .consts import ArmyStrategy, CommandType, EconomyStrategy, EnemyEconomy

nest_asyncio.apply()


class Model(nn.Module):
    def __init__(self):
        super().__init__()
        self.fc1 = nn.Linear(5 + 8 + 12, 64)
        self.norm1 = nn.LayerNorm(64)
        self.fc2 = nn.Linear(64, 64)
        self.norm2 = nn.LayerNorm(64)
        self.vf = nn.Linear(64, 1)
        self.economy_head = nn.Linear(64, len(EconomyStrategy))
        self.army_head = nn.Linear(64, len(ArmyStrategy))

    def forward(self, x):
        x = F.relu(self.norm1(self.fc1(x)))
        x = F.relu(self.norm2(self.fc2(x)))
        value = self.vf(x)
        economy_logp = torch.log_softmax(self.economy_head(x), -1)
        army_logp = torch.log_softmax(self.army_head(x), -1)
        bz = x.shape[0]
        logp = (economy_logp.view(bz, -1, 1) + army_logp.view(bz, 1, -1)).view(bz, -1)
        return value, logp


class Bot(sc2.BotAI):

    def __init__(self, step_interval=5.0, host_name='', sock=None):
        super().__init__()
        self.step_interval = step_interval
        self.host_name = host_name
        self.sock = sock
        if sock is None:
            try:
                self.model = Model()
                model_path = pathlib.Path(__file__).parent / 'model.pt'
                self.model.load_state_dict(
                    torch.load(model_path, map_location='cpu')
                )
            except Exception as exc:
                import traceback; traceback.print_exc()

    def on_start(self):
        """
        새로운 게임마다 초기화
        """
        self.step_interval = self.step_interval
        self.last_step_time = -self.step_interval
        self.evoked = dict()

        self.economy_strategy = EconomyStrategy.MARINE.value
        self.army_strategy = ArmyStrategy.DEFENSE

        self.cc = self.units(UnitTypeId.COMMANDCENTER).first  # 전체 유닛에서 사령부 검색
        # (32.5, 31.5) or (95.5, 31.5)
        if self.start_location.distance_to(Point2((32.5, 31.5))) < 5.0:
            # self.enemy_cc = self.enemy_start_locations[0]  # 적 시작 위치
            self.enemy_cc = Point2(Point2((95.5, 31.5)))  # 적 시작 위치
        else:
            self.enemy_cc = Point2(Point2((32.5, 31.5)))  # 적 시작 위치

        # Learner에 join
        self.game_id = f"{self.host_name}_{time.time()}"
        # data = (JOIN, game_id)
        # self.sock.send_multipart([pickle.dumps(d) for d in data])
        

    async def on_step(self, iteration: int):
        actions = list()

        if self.time - self.last_step_time >= self.step_interval:
            self.economy_strategy, self.army_strategy = self.set_strategy()
            self.last_step_time = self.time
        
        self.combat_units = self.units.exclude_type(
            [UnitTypeId.COMMANDCENTER, UnitTypeId.MEDIVAC, UnitTypeId.RAVEN, UnitTypeId.BATTLECRUISER, UnitTypeId.GHOST, UnitTypeId.MULE, UnitTypeId.NUKE]
        )
        self.wounded_units = self.units.filter(
            lambda u: u.is_biological and u.health_percentage < 1.0
        )  # 체력이 100% 이하인 유닛 검색
        
        actions += self.train_action()
        actions += self.unit_actions()
        await self.do_actions(actions)

    def set_strategy(self):
        #
        # 특징 추출
        #
        state = np.zeros(5 + len(EconomyStrategy) + len(EnemyEconomy), dtype=np.float32)
        state[0] = self.cc.health_percentage
        state[1] = min(1.0, self.minerals / 1000)
        state[2] = min(1.0, self.vespene / 1000)
        state[3] = min(1.0, self.time / 360)
        state[4] = min(1.0, self.state.score.total_damage_dealt_life / 2500)
        # 아군 유닛 종류별 개수
        for unit in self.units.not_structure:
            id = unit.type_id
            if id is UnitTypeId.SIEGETANKSIEGED:
                id = UnitTypeId.SIEGETANK
            if id is UnitTypeId.VIKINGASSAULT:
                id = UnitTypeId.VIKINGFIGHTER
            if id is UnitTypeId.THORAP:
                id = UnitTypeId.THOR
            if id is UnitTypeId.MULE:
                continue
            # if id is UnitTypeId.NUKE:
            #     continue
            state[5 + EconomyStrategy.to_index[id]] += 1
        # 적 유닛 종류별 개수
        if self.known_enemy_units.exists:
            for enemy_unit in self.known_enemy_units.not_structure:
                id = enemy_unit.type_id
                if id is UnitTypeId.SIEGETANKSIEGED:
                    id = UnitTypeId.SIEGETANK
                if id is UnitTypeId.VIKINGASSAULT:
                    id = UnitTypeId.VIKINGFIGHTER
                if id is UnitTypeId.THORAP:
                    id = UnitTypeId.THOR
                if id in EnemyEconomy:
                    state[5 + 8 + EnemyEconomy.to_index[id]] += 1
                else: 
                    continue
        state = state.reshape(1, -1)

        # NN
        data = [
            CommandType.STATE,
            pickle.dumps(self.game_id),
            pickle.dumps(state.shape),
            state,
        ]
        if self.sock is not None:
            self.sock.send_multipart(data)
            data = self.sock.recv_multipart()
            value = pickle.loads(data[0])
            action = pickle.loads(data[1])
        else:
            with torch.no_grad():
                value, logp = self.model(torch.FloatTensor(state))
                value = value.item()
                action = logp.exp().multinomial(num_samples=1).item()

        economy_strategy = EconomyStrategy.to_type_id[action // len(ArmyStrategy)]
        army_strategy = ArmyStrategy(action % len(ArmyStrategy))
        # print('next unit =', economy_strategy,'전략=', army_strategy)
        return economy_strategy, army_strategy
    
    def train_action(self):
        #
        # 사령부 명령 생성
        #
        actions = list()
        next_unit = self.economy_strategy
        if self.can_afford(next_unit):
            if self.time - self.evoked.get((self.cc.tag, 'train'), 0) > 1.0:
                actions.append(self.cc.train(next_unit))
                self.evoked[(self.cc.tag, 'train')] = self.time
        
        # 사령부 체력이 깎였을 경우 지게로봇 생성
        if self.cc.health_percentage < 1.0:
            mule_loc = self.start_location - 0.05 * (self.enemy_cc.position - self.start_location)
            actions.append(self.cc(AbilityId.CALLDOWNMULE_CALLDOWNMULE, target=mule_loc))

        # 해병 정찰 명령
        # 게임 시작시 바로 정찰병 생산
        if not self.evoked.get((self.cc.tag, 'make_patrol'), 0):
            actions.insert(0, self.cc.train(UnitTypeId.MARINE))
            self.evoked[(self.cc.tag, 'make_patrol')] = self.time
        # 15초 이전에 정찰병을 보낸 적이 없음
        elif self.time - self.evoked.get((self.cc.tag, 'make_patrol'), 0) > 15.0:
            actions.insert(0, self.cc.train(UnitTypeId.MARINE))
            self.evoked[(self.cc.tag, 'make_patrol')] = self.time
         
        return actions
        
    
    def unit_actions(self):
        #
        # 유닛 명령 생성
        #
        actions = list()
     
        for unit in self.units.not_structure:  # 건물이 아닌 유닛만 선택
            enemy_unit = self.enemy_start_locations[0]
            if self.known_enemy_units.exists:
                enemy_unit = self.known_enemy_units.closest_to(unit)  # 가장 가까운 적 유닛

            # 적 사령부와 가장 가까운 적 유닛중 더 가까운 것을 목표로 설정
            if unit.distance_to(self.enemy_cc) < unit.distance_to(enemy_unit):
                target = self.enemy_cc
            else:
                target = enemy_unit

            # 해병 명령
            if unit.type_id is UnitTypeId.MARINE:
                use_stimpack = True
                # 해병 정찰 명령
                # 15초 이전에 정찰병을 보낸 적이 없음
                if self.time - self.evoked.get((self.cc.tag, 'patrol'), 0) > 15.0 and self.time - self.evoked.get((unit.tag, 'patrol'), 0) > 15.0:
                    actions.insert(0, unit.attack(self.enemy_cc.position))
                    self.evoked[(self.cc.tag, 'patrol')] = self.time
                    self.evoked[(unit.tag, 'patrol')] = self.time
                
                elif not self.evoked.get((unit.tag, 'patrol'), 0):
                # 해병 공격 명령
                    if self.army_strategy is ArmyStrategy.OFFENSE:
                        if self.combat_units.amount >= 15:   # 나중에 다른 유닛 개수랑 더하는 것으로 수정하기
                            # 전투가능한 유닛 수가 15를 넘으면 적 본진으로 공격
                            actions.append(unit.attack(target))
                            use_stimpack = True

                    elif self.army_strategy is ArmyStrategy.DEFENSE:
                        # 적 사령부 방향에 유닛 집결
                        target = self.start_location + 0.25 * (self.enemy_cc.position - self.start_location)
                        actions.append(unit.attack(target))
                        use_stimpack = False

                    if self.army_strategy is ArmyStrategy.OFFENSE:
                        if  use_stimpack and unit.distance_to(target) < 15:
                            # 유닛과 목표의 거리가 15이하일 경우 스팀팩 사용
                            if not unit.has_buff(BuffId.STIMPACK) and unit.health_percentage > 0.5:
                                # 현재 스팀팩 사용중이 아니며, 체력이 50% 이상
                                if self.time - self.evoked.get((unit.tag, AbilityId.EFFECT_STIM), 0) > 1.0:
                                    # 1초 이전에 스팀팩을 사용한 적이 없음
                                    actions.append(unit(AbilityId.EFFECT_STIM))
                                    self.evoked[(unit.tag, AbilityId.EFFECT_STIM)] = self.time
        
            # 화염차 명령
            if unit.type_id is UnitTypeId.HELLION:
                if self.army_strategy is ArmyStrategy.OFFENSE:
                    if self.combat_units.amount >= 15:
                        actions.append(unit.attack(target))
                elif self.army_strategy is ArmyStrategy.DEFENSE:
                    target = self.start_location + 0.25 * (self.enemy_cc.position - self.start_location)
                    actions.append(unit.attack(target))

            # 공성 전차 명령
            if unit.type_id is UnitTypeId.SIEGETANK: 
                if self.army_strategy is ArmyStrategy.OFFENSE:
                    if self.combat_units.amount >= 15:   # 나중에 다른 유닛 개수랑 더하는 것으로 수정하기
                        # 전투가능한 유닛 수가 15를 넘으면 적 본진으로 공격
                        actions.append(unit.attack(target))

                elif self.army_strategy is ArmyStrategy.DEFENSE:
                    # 적 사령부 방향에 유닛 집결
                    defense_pos = self.start_location + 0.15 * (self.enemy_cc.position - self.start_location)
                    actions.append(unit.attack(defense_pos))

                    # print('현재=', unit.position, '목표=', target, '거리=', unit.distance_to(target))
                    if unit.distance_to(target) < 13:
                        actions.append(unit(AbilityId.SIEGEMODE_SIEGEMODE))
                    else:
                        actions.append(unit.attack(target))
                
            # Siege Mode 공성 전차 명령
            if unit.type_id is UnitTypeId.SIEGETANKSIEGED:
                if unit.distance_to(target) > 13:
                    actions.append(unit(AbilityId.UNSIEGE_UNSIEGE))
                else:
                    actions.append(unit.attack(target))
            
            # 전투 순양함 명령
            if unit.type_id is UnitTypeId.BATTLECRUISER:       
                # 전투순양함이 2개 이상일 때 적 사령부로 전술 차원 도약
                if self.army_strategy is ArmyStrategy.OFFENSE:
                    battlecruiser_units = self.units(UnitTypeId.BATTLECRUISER)
                    if battlecruiser_units.amount >= 2:
                        if self.can_cast(unit, AbilityId.EFFECT_TACTICALJUMP, target=self.enemy_cc):
                          actions.append(unit(AbilityId.EFFECT_TACTICALJUMP, target=self.enemy_cc))
                        # 야마토 포 시전 가능하면 시전
                        if self.can_cast(unit, AbilityId.YAMATO_YAMATOGUN, target=target):
                            actions.append(unit(AbilityId.YAMATO_YAMATOGUN, target=target))
                        actions.append(unit.attack(target))
                    else:
                        target = self.start_location + 0.05 * (self.enemy_cc.position - self.start_location)
                        actions.append(unit.attack(target))
                if self.army_strategy is ArmyStrategy.DEFENSE:
                    target = self.start_location + 0.05 * (self.enemy_cc.position - self.start_location)
                    actions.append(unit.attack(target))

            # 유령 명령
            # if unit.type_id is UnitTypeId.GHOST:
            #     nukes = self.units(UnitTypeId.NUKE)
            #     if nukes.amount == 0:
            #         if self.can_afford(UnitTypeId.NUKE):
            #             # 전술핵 생산 가능(자원이 충분)하면 전술핵 생산
            #             actions.append(self.cc.train(UnitTypeId.NUKE))
            #     if self.army_strategy is ArmyStrategy.OFFENSE:
            #         if self.can_cast(unit, AbilityId.TACNUKESTRIKE_NUKECALLDOWN, target=self.enemy_cc) and unit.is_idle:
            #             # 전술핵 발사 가능(생산완료)하고 고스트가 idle 상태이면, 적 본진에 전술핵 발사
            #             actions.append(unit(AbilityId.BEHAVIOR_CLOAKON_GHOST))
            #             actions.append(unit(AbilityId.TACNUKESTRIKE_NUKECALLDOWN, target=self.enemy_cc))
            #             actions.append(unit.attack(self.cc))
                
            #     elif self.army_strategy is ArmyStrategy.DEFENSE:
            #         if self.can_cast(unit, AbilityId.EMP_EMP) and unit.is_idle:
            #             emp_targets = self.known_enemy_units.filter(lambda unit: unit.name in ["Battlecruiser", "SiegeTank", "SiegeTankSieged", "Banshee", "Raven", "Medivac"])
            #             if emp_targets:
            #                 emp_target = emp_targets[0]
            #                 actions.append(unit(AbilityId.EMP_EMP, target=emp_target))
            #         actions.append(unit.attack(target))

            # 밤까마귀 명령
            if unit.type_id is UnitTypeId.RAVEN:
                if self.army_strategy is ArmyStrategy.OFFENSE:
                    # 대장갑 미사일 이용하여 상대 사령부 쪽으로 공격시 전투순양함 대상 공격
                    missile_targets = self.known_enemy_units.filter(lambda unit: unit.name == "Battlecruiser")
                    if missile_targets:
                        missile_target = missile_targets[0]
                        # 전투순양함이 아군 사령부쪽에 있지 않을때 대장갑 미사일 이용하기
                        if self.can_cast(unit, AbilityId.EFFECT_ANTIARMORMISSILE, target=missile_target):
                            actions.append(unit(AbilityId.EFFECT_ANTIARMORMISSILE, target=missile_target))
                    else:
                        # 전투순양함이 없는데 밤까마귀가 있는 경우 + 공격 모드일 때
                        # 밤까마귀를 은신 유닛 탐지에 이용, 다른 아군 공격 유닛들과 함께 전투 유닛 중앙에 배치
                        if self.combat_units.amount >= 15:
                            actions.append(unit(AbilityId.SCAN_MOVE, target=self.combat_units.center))
                
                elif self.army_strategy is ArmyStrategy.DEFENSE:
                    # 방해 매트릭스 이용하여 아군 사령부 쪽에서 유닛(특히 전투순양함) 방어
                    matrix_targets = self.known_enemy_units.filter(lambda unit: unit.name in ["SiegeTank", "SiegeTankSieged", "VikingAssault", "VikingFigher", "Battlecruiser"])
                    if matrix_targets:
                        matrix_target = matrix_targets[0]
                        if self.can_cast(unit, AbilityId.EFFECT_INTERFERENCEMATRIX, target=matrix_target.position):
                            actions.append(unit(AbilityId.EFFECT_INTERFERENCEMATRIX, target=matrix_target.position))
                    else:
                        # 자동 포탑 - 방어선으로 이용: 아군 사령부보다 거리 7 앞에서 방어공격
                        # 아군 사령부 쪽에(거리 7 이하) 적 유닛 존재하면 자동 포탑 설치
                        if self.enemy_cc==Point2(Point2((95.5, 31.5))):
                            turret_target = Point2(Point2((38.5, 31.5)))
                        else:
                            turret_target = Point2(Point2((89.5, 31.5)))
                        
                        if self.cc.distance_to(target) < 7:
                            if self.can_cast(unit, AbilityId.BUILDAUTOTURRET_AUTOTURRET, target=turret_target):
                                actions.append(unit(AbilityId.BUILDAUTOTURRET_AUTOTURRET, target=turret_target))

            # 밴시 명령
            if unit.type_id is UnitTypeId.BANSHEE: 
                if self.army_strategy is ArmyStrategy.OFFENSE:
                    if self.combat_units.amount >= 15:
                        actions.append(unit(AbilityId.BEHAVIOR_CLOAKON_BANSHEE))
                elif self.army_strategy is ArmyStrategy.DEFENSE:
                    target =  self.start_location + 0.25 * (self.enemy_cc.position - self.start_location)
                
                actions.append(unit.attack(target))
            
            # 토르 명령
            if unit.type_id is UnitTypeId.THOR:
                try:
                    if target.is_flying:
                        actions.append(unit(AbilityId.MORPH_THORHIGHIMPACTMODE))
                except:
                    pass

                if self.army_strategy is ArmyStrategy.OFFENSE:
                    if self.combat_units.amount >= 15:
                        actions.append(unit.attack(target))
                elif self.army_strategy is ArmyStrategy.DEFENSE:
                    target = self.start_location + 0.25 * (self.enemy_cc.position - self.start_location)
                    actions.append(unit.attack(target))
            
            if unit.type_id is UnitTypeId.THORAP:
                try:
                    if not target.is_flying:
                        actions.append(unit(AbilityId.MORPH_THOREXPLOSIVEMODE))
                except:
                    pass

                if self.army_strategy is ArmyStrategy.OFFENSE:
                    if self.combat_units.amount >= 15:
                        actions.append(unit.attack(target))
                elif self.army_strategy is ArmyStrategy.DEFENSE:
                    target = self.start_location + 0.25 * (self.enemy_cc.position - self.start_location)
                    actions.append(unit.attack(target))
            
            # 바이킹 명령
            if unit.type_id is UnitTypeId.VIKINGFIGHTER:
                try:
                    if not target.is_flying:
                        actions.append(unit(AbilityId.MORPH_VIKINGASSAULTMODE))
                except:
                    pass
                
                if self.army_strategy is ArmyStrategy.OFFENSE:
                    if self.combat_units.amount >= 15:
                        actions.append(unit.attack(target))
                elif self.army_strategy is ArmyStrategy.DEFENSE:
                    target = self.start_location + 0.25 * (self.enemy_cc.position - self.start_location)
                    actions.append(unit.attack(target))                    
            
            if unit.type_id is UnitTypeId.VIKINGASSAULT:
                try:
                    if target.is_flying:
                        actions.append(unit(AbilityId.MORPH_VIKINGFIGHTERMODE))
                except:
                    pass

                if self.army_strategy is ArmyStrategy.OFFENSE:
                    if self.combat_units.amount >= 15:
                        actions.append(unit.attack(target))
                elif self.army_strategy is ArmyStrategy.DEFENSE:
                    target = self.start_location + 0.25 * (self.enemy_cc.position - self.start_location)
                    actions.append(unit.attack(target))     

            # 지게로봇 명령
            if unit.type_id is UnitTypeId.MULE:
                actions.append(unit(AbilityId.EFFECT_REPAIR_MULE, target=self.cc))
        
        return actions
    

    def on_end(self, game_result):
        if self.sock is not None:
            score = 1. if game_result is Result.Victory else -1.
            self.sock.send_multipart((
                CommandType.SCORE, 
                pickle.dumps(self.game_id),
                pickle.dumps(score),
            ))
            self.sock.recv_multipart()
