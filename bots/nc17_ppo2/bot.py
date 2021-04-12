
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

from .consts import ArmyStrategy, CommandType, EconomyStrategy


nest_asyncio.apply()


class Model(nn.Module):
    def __init__(self):
        super().__init__()
        self.fc1 = nn.Linear(5 + 12, 64)
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
    """
    example v1과 유사하지만, 빌드 오더 대신, 유닛 비율을 맞추도록 유닛을 생산함
    """
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
        self.build_order = list() # 생산할 유닛 목록

    def on_start(self):
        """
        새로운 게임마다 초기화
        """
        self.step_interval = self.step_interval
        self.last_step_time = -self.step_interval
        self.evoked = dict()
        self.build_order = list()

        # self.economy_strategy = EconomyStrategy.MARINE.value
        self.army_strategy = ArmyStrategy.DEFENSE_SIMPLE

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
        
        # 초반 빌드 오더 생성 (해병: 30)
        for _ in range(30):
            self.build_order.append(UnitTypeId.MARINE)

        # 중반 빌드 오더 (해병: 2, 공성 전차 : 1, 화염차 : 1 - 다섯 번 반복)
        for _ in range(5):
            for _ in range(2):
                self.build_order.append(UnitTypeId.MARINE)
            self.build_order.append(UnitTypeId.SIEGETANK)
            self.build_order.append(UnitTypeId.HELLION)

    async def on_step(self, iteration: int):
        actions = list()

        combat_units = self.units.exclude_type([UnitTypeId.COMMANDCENTER, UnitTypeId.MEDIVAC, UnitTypeId.SIEGETANK, UnitTypeId.SIEGETANKSIEGED, UnitTypeId.RAVEN, UnitTypeId.BATTLECRUISER, UnitTypeId.GHOST])
        tank_units = self.units.exclude_type([UnitTypeId.COMMANDCENTER, UnitTypeId.MEDIVAC, UnitTypeId.MARINE, UnitTypeId.RAVEN, UnitTypeId.BATTLECRUISER, UnitTypeId.GHOST])
        end_units = self.units.exclude_type([UnitTypeId.COMMANDCENTER, UnitTypeId.MEDIVAC, UnitTypeId.SIEGETANK, UnitTypeId.SIEGETANKSIEGED,  UnitTypeId.MARINE]) # 후반부 유닛
        wounded_units = self.units.filter(
            lambda u: u.is_biological and u.health_percentage < 1.0
        )  # 체력이 100% 이하인 유닛 검색
        enemy_cc = self.enemy_start_locations[0]  # 적 시작 위치

        # 후반부 빌드 오더 (밤까마귀: 1, 전투 순양함: 2, 유령: 1, 전술핵: 1)
        self.build_order.append(UnitTypeId.RAVEN)
        for _ in range(2):
            self.build_order.append(UnitTypeId.BATTLECRUISER)
        self.build_order.append(UnitTypeId.GHOST)
        self.build_order.append(AbilityId.BUILD_NUKE)

        #
        # 사령부 명령 생성
        #
        cc = self.units(UnitTypeId.COMMANDCENTER).first        
        next_unit = self.build_order[0]
        cost = self._game_data.calculate_ability_cost(cc.train(next_unit))

        if self.vespene >= cost.vespene:
            # print('gas는 충분!')
            if self.can_afford(next_unit) and self.time - self.evoked.get((cc.tag, 'train'), 0) > 1.0:
                actions.append(cc.train(next_unit))
                del self.build_order[0]
                self.evoked[(cc.tag, 'train')] = self.time
            # else:
                # print('광물 부족')
        else:
            # print('gas 부족')
            if self.can_afford(UnitTypeId.MARINE) and self.time - self.evoked.get((cc.tag, 'train'), 0) > 1.0:
                actions.append(cc.train(UnitTypeId.MARINE))
                self.evoked[(cc.tag, 'train')] = self.time

        # 사령부 체력이 깎였을 경우 지게로봇 생성
        if cc.health_percentage < 1.0:
            mule_loc = self.start_location - 0.05 * (enemy_cc.position - self.start_location)
            actions.append(cc(AbilityId.CALLDOWNMULE_CALLDOWNMULE, target=mule_loc))

        #
        # 유닛 명령 생성
        #
        for unit in self.units.not_structure:  # 건물이 아닌 유닛만 선택
            enemy_unit = self.enemy_start_locations[0]
            if self.known_enemy_units.exists:
                enemy_unit = self.known_enemy_units.closest_to(unit)  # 가장 가까운 적 유닛

            # 적 사령부와 가장 가까운 적 유닛중 더 가까운 것을 목표로 설정
            if unit.distance_to(enemy_cc) < unit.distance_to(enemy_unit):
                target = enemy_cc
            else:
                target = enemy_unit

            # 해병 명령
            if unit.type_id is UnitTypeId.MARINE:
                if self.army_strategy is ArmyStrategy.OFFENSE_LOW or self.army_strategy is ArmyStrategy.OFFENSE_MID or self.army_strategy is ArmyStrategy.OFFENSE_HIGH:
                    if combat_units.amount + tank_units.amount >= 15:   # 나중에 다른 유닛 개수랑 더하는 것으로 수정하기
                        # 전투가능한 유닛 수가 15를 넘으면 적 본진으로 공격
                        actions.append(unit.attack(target))
                        use_stimpack = True
                elif self.army_strategy is ArmyStrategy.DEFENSE_SIMPLE or self.army_strategy is ArmyStrategy.DEFENSE_SIEGETANK:
                    # 적 사령부 방향에 유닛 집결
                    target = self.start_location + 0.25 * (enemy_cc.position - self.start_location)
                    actions.append(unit.attack(target))
                    use_stimpack = False

                if self.army_strategy is ArmyStrategy.OFFENSE_LOW or self.army_strategy is ArmyStrategy.OFFENSE_MID or self.army_strategy is ArmyStrategy.OFFENSE_HIGH:
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
                if self.army_strategy is ArmyStrategy.OFFENSE_MID or self.army_strategy is ArmyStrategy.OFFENSE_HIGH:
                    if combat_units.amount > 5:
                        actions.append(unit.attack(target))
                elif self.army_strategy is ArmyStrategy.DEFENSE_SIEGETANK or self.army_strategy is ArmyStrategy.DEFENSE_SIMPLE:
                    target = self.start_location + 0.25 * (enemy_cc.position - self.start_location)
                    actions.append(unit.attack(target))

            # 공성 전차 명령
            if unit.type_id is UnitTypeId.SIEGETANK: 
                if self.army_strategy is ArmyStrategy.OFFENSE_LOW or self.army_strategy is ArmyStrategy.OFFENSE_MID or self.army_strategy is ArmyStrategy.OFFENSE_HIGH:
                    if combat_units.amount + tank_units.amount >= 15:   # 나중에 다른 유닛 개수랑 더하는 것으로 수정하기
                        # 전투가능한 유닛 수가 15를 넘으면 적 본진으로 공격
                        actions.append(unit.attack(target))

                elif self.army_strategy is ArmyStrategy.DEFENSE_SIEGETANK:
                    # 적 사령부 방향에 유닛 집결
                    target = self.start_location + 0.15 * (enemy_cc.position - self.start_location)
                    actions.append(unit.attack(target))

                    # print('현재=', unit.position, '목표=', target, '거리=', unit.distance_to(target))
                    if unit.distance_to(target) < 3.0:
                        actions.append(unit(AbilityId.SIEGEMODE_SIEGEMODE))
                else:
                    # 적 사령부 방향에 유닛 집결
                    target = self.start_location + 0.25 * (enemy_cc.position - self.start_location)
                    actions.append(unit.attack(target))
                    
                    #  적 사령부가 사거리에 들어왔을 때 공성 모드로 전환
                    if unit.distance_to(enemy_cc) < 13 and unit.health_percentage > 0.3: 
                        actions.append(unit(AbilityId.SIEGEMODE_SIEGEMODE))
                    else:
                        actions.append(unit.attack(target))
                # 공성 모드로 전환 (사거리 증가 및 범위 공격)
                # print('target=', target, 'distance=', unit.distance_to(target))

                # 사거리 안에 들어오면 바로 공성 모드로 전환
                # if 7 < unit.distance_to(target) < 13:
                #     actions.append(unit(AbilityId.SIEGEMODE_SIEGEMODE))
                # else:
                #     actions.append(unit.attack(target))
                
            # Siege Mode 공성 전차 명령
            if unit.type_id is UnitTypeId.SIEGETANKSIEGED:
                if unit.distance_to(target) > 13:
                    actions.append(unit(AbilityId.UNSIEGE_UNSIEGE))
                else:
                    actions.append(unit.attack(target))
            
            # 전투 순양함 명령
            if unit.type_id is UnitTypeId.BATTLECRUISER:       
                # 전투순양함이 2개 이상일 때 적 사령부로 전술 차원 도약
                if self.army_strategy is ArmyStrategy.OFFENSE_HIGH:
                    if battlecruiser_units.amount >= 2:
                        if await self.can_cast(unit, AbilityId.EFFECT_TACTICALJUMP, target=enemy_cc):
                          actions.append(unit(AbilityId.EFFECT_TACTICALJUMP, target=enemy_cc))
                        # 야마토 포 시전 가능하면 시전
                        if await self.can_cast(unit, AbilityId.YAMATO_YAMATOGUN, target=target):
                            actions.append(unit(AbilityId.YAMATO_YAMATOGUN, target=target))
                        actions.append(unit.attack(target))
                    else:
                        defense_pos = self.start_location + 0.05 * (enemy_cc.position - self.start_location)
                        actions.append(unit.attack(defense_pos))
                
            # 유령 명령
            if unit.type_id is UnitTypeId.GHOST:
                if self.army_strategy is ArmyStrategy.OFFENSE_HIGH:
                    ghost_abilities = await self.get_available_abilities(unit)
                    if AbilityId.TACNUKESTRIKE_NUKECALLDOWN in ghost_abilities and unit.is_idle:
                    # 전술핵 발사 가능(생산완료)하고 고스트가 idle 상태이면, 적 본진에 전술핵 발사
                        actions.append(unit(AbilityId.BEHAVIOR_CLOAKON_GHOST))
                        actions.append(unit(AbilityId.TACNUKESTRIKE_NUKECALLDOWN, target=enemy_cc))
            
            # 밤까마귀 명령
            if unit.type_id is UnitTypeId.RAVEN and self.army_strategy is ArmyStrategy.OFFENSE_HIGH:
                # 자동 포탑 - 방어선으로 이용: 아군 사령부보다 거리 3 앞에서 방어공격
                # 아군 사령부 쪽에(거리 3 이하) 적 유닛 존재하면 자동 포탑 설치
                if cc.distance_to(enemy_unit) <= 3:
                    if enemy_cc==Point2(Point2((95.5, 31.5))):
                        actions.append(unit(AbilityId.BUILDAUTOTURRET_AUTOTURRET, target=Point2(Point2((38.5, 31.5)))))
                    else:
                        actions.append(unit(AbilityId.BUILDAUTOTURRET_AUTOTURRET, target=Point2(Point2((89.5, 31.5)))))
                
                # 방해 매트릭스 (은폐 유닛 드러냄)
                try:
                    if target.is_cloaked:
                        actions.append(ravens.first(AbilityId.SCAN_MOVE, target=target.position))
                except:
                    pass

            # 지게로봇 명령
            if unit.type_id is UnitTypeId.MULE:
                actions.append(unit(AbilityId.EFFECT_REPAIR_MULE, target=cc))
        
        await self.do_actions(actions)

    def set_strategy(self):
        #
        # 특징 추출
        #
        state = np.zeros(5 + len(EconomyStrategy), dtype=np.float32)
        state[0] = self.cc.health_percentage
        state[1] = min(1.0, self.minerals / 1000)
        state[2] = min(1.0, self.vespene / 1000)
        state[3] = min(1.0, self.time / 360)
        state[4] = min(1.0, self.state.score.total_damage_dealt_life / 2500)
        for unit in self.units.not_structure:
            state[5 + EconomyStrategy.to_index[unit.type_id]] += 1
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
        return army_strategy

    

    def on_end(self, game_result):
        if self.sock is not None:
            score = 1. if game_result is Result.Victory else -1.
            self.sock.send_multipart((
                CommandType.SCORE, 
                pickle.dumps(self.game_id),
                pickle.dumps(score),
            ))
            self.sock.recv_multipart()
