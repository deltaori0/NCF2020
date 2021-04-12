
__author__ = '고주연 (juyon98@korea.ac.kr), 홍은수 (deltaori0@korea.ac.kr)'

import time

import numpy as np

import sc2
from sc2.ids.ability_id import AbilityId
from sc2.ids.unit_typeid import UnitTypeId
from sc2.ids.buff_id import BuffId
from sc2.position import Point2


class Bot(sc2.BotAI):
    """
    초반 전략 : 해병 + 공성 전차 + 바이킹
    최종 전략 : 전투순양함 돌격
    """
    def __init__(self, *args, **kwargs):
        super().__init__()


    def on_start(self):
        """
        새로운 게임마다 초기화
        """
        self.build_order = list() # 생산할 유닛 목록

        self.target_unit_counts = {
            UnitTypeId.COMMANDCENTER: 1, 
            UnitTypeId.MARINE: 0,
            UnitTypeId.MARAUDER: 0,
            UnitTypeId.REAPER: 0,
            UnitTypeId.GHOST: 0,
            UnitTypeId.HELLION: 0,
            UnitTypeId.SIEGETANKSIEGED: 5,
            UnitTypeId.THOR: 0,
            UnitTypeId.MEDIVAC: 0,
            UnitTypeId.VIKINGFIGHTER: 0,
            UnitTypeId.BANSHEE: 0,
            UnitTypeId.RAVEN: 1,
            UnitTypeId.BATTLECRUISER: 3,
        }
        self.evoked = dict()

    async def on_step(self, iteration: int):       
        actions = list()

        cc = self.units(UnitTypeId.COMMANDCENTER).first
        combat_units = self.units.exclude_type([UnitTypeId.COMMANDCENTER, UnitTypeId.MEDIVAC])
        wounded_units = self.units.filter(
            lambda u: u.is_biological and u.health_percentage < 1.0
        )  # 체력이 100% 이하인 유닛 검색
        battlecruiser_units = self.units.of_type(UnitTypeId.BATTLECRUISER)
        enemy_cc = self.enemy_start_locations[0]  # 적 시작 위치

        # 부족한 유닛 숫자 계산
        unit_counts = dict()
        for unit in self.units:
            unit_counts[unit.type_id] = unit_counts.get(unit.type_id, 0) + 1
        
        target_unit_counts = np.array(list(self.target_unit_counts.values()))
        # target_unit_ratio = target_unit_counts / (target_unit_counts.sum() + 1e-6)  # 목표로 하는 유닛 비율
        current_unit_counts = np.array([unit_counts.get(tid, 0) for tid in self.target_unit_counts.keys()])
        # current_unit_ratio = current_unit_counts / (current_unit_counts.sum() + 1e-6)  # 현재 유닛 비율
        # unit_ratio = (target_unit_ratio - current_unit_ratio).clip(0, 1)  # 목표 - 현재 유닛 비율
        
        # print('target unit counts=', target_unit_counts)     
        # print('current unit counts=', current_unit_counts)
        economy_strategy = np.array([i - j for i, j in zip(target_unit_counts, current_unit_counts)])
        # print(economy_strategy)

        #
        # 사령부 명령 생성
        #
        next_index = -1
        for idx, val in enumerate(economy_strategy):
            if val > 0:
                next_index = idx
                break
        
        next_unit = list(self.target_unit_counts.keys())[next_index]  # 가장 부족한 유닛을 다음에 훈련
        if next_unit is UnitTypeId.SIEGETANKSIEGED:
            next_unit = UnitTypeId.SIEGETANK
        
        cost = self._game_data.calculate_ability_cost(cc.train(next_unit))
        # print('next unit=', next_unit, 'gas cost=', cost.vespene)

        if self.vespene >= cost.vespene:
            # print('gas는 충분!')
            if self.can_afford(next_unit) and self.time - self.evoked.get((cc.tag, 'train'), 0) > 1.0:
                actions.append(cc.train(next_unit))
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
                # 적 사령부 방향에 유닛 집결
                target = self.start_location + 0.25 * (enemy_cc.position - self.start_location)
                actions.append(unit.attack(target))
                use_stimpack = False

                # if use_stimpack and unit.distance_to(target) < 15:
                #     # 유닛과 목표의 거리가 15이하일 경우 스팀팩 사용
                #     if not unit.has_buff(BuffId.STIMPACK) and unit.health_percentage > 0.5:
                #         # 현재 스팀팩 사용중이 아니며, 체력이 50% 이상
                #         if self.time - self.evoked.get((unit.tag, AbilityId.EFFECT_STIM), 0) > 1.0:
                #             # 1초 이전에 스팀팩을 사용한 적이 없음
                #             actions.append(unit(AbilityId.EFFECT_STIM))
                #             self.evoked[(unit.tag, AbilityId.EFFECT_STIM)] = self.time
            

            # 공성 전차 명령
            if unit.type_id is UnitTypeId.SIEGETANK: 
                # 적 사령부 방향에 유닛 집결
                target = self.start_location + 0.15 * (enemy_cc.position - self.start_location)
                actions.append(unit.attack(target))

                # print('현재=', unit.position, '목표=', target, '거리=', unit.distance_to(target))
                if unit.distance_to(target) < 3.0:
                    actions.append(unit(AbilityId.SIEGEMODE_SIEGEMODE))

                # actions.append(unit(AbilityId.SIEGEMODE_SIEGEMODE))
                # 공성 모드로 전환 (사거리 증가 및 범위 공격)
                # print('target=', target, 'distance=', unit.distance_to(target))

                # 사거리 안에 들어오면 바로 공성 모드로 전환
                # if 7 < unit.distance_to(target) < 13:
                #     actions.append(unit(AbilityId.SIEGEMODE_SIEGEMODE))
                # else:
                #     actions.append(unit.attack(target))


            # Siege Mode 공성 전차 명령
            if unit.type_id is UnitTypeId.SIEGETANKSIEGED:
                # if unit.distance_to(target) > 13:
                #     actions.append(unit(AbilityId.UNSIEGE_UNSIEGE))
                # else:
                actions.append(unit.attack(target))
            
            # 전투 순양함 명령
            if unit.type_id is UnitTypeId.BATTLECRUISER:       
                # 전투 순양함이 3개 이상일 때 적 사령부로 전술 차원 도약
                if battlecruiser_units.amount >= 3:
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
                ghost_abilities = await self.get_available_abilities(unit)
                if AbilityId.TACNUKESTRIKE_NUKECALLDOWN in ghost_abilities and unit.is_idle:
                # 전술핵 발사 가능(생산완료)하고 고스트가 idle 상태이면, 적 본진에 전술핵 발사
                    actions.append(unit(AbilityId.BEHAVIOR_CLOAKON_GHOST))
                    actions.append(unit(AbilityId.TACNUKESTRIKE_NUKECALLDOWN, target=enemy_cc))
            
            # 밤까마귀 명령
            if unit.type_id is UnitTypeId.RAVEN:
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
                        actions.append(unit(AbilityId.SCAN_MOVE, target=target.position))
                except:
                    pass

            # 지게로봇 명령
            if unit.type_id is UnitTypeId.MULE:
                actions.append(unit(AbilityId.EFFECT_REPAIR_MULE, target=cc))
        
        
        await self.do_actions(actions)

