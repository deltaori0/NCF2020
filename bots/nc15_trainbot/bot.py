
__author__ = '고주연 (juyon98@korea.ac.kr), 홍은수 (deltaori0@korea.ac.kr)'

import time

import sc2
from sc2.ids.ability_id import AbilityId
from sc2.ids.unit_typeid import UnitTypeId
from sc2.ids.buff_id import BuffId
from sc2.position import Point2


class Bot(sc2.BotAI):
    """
    초반 전략 : 비용이 싼 유닛(해병, 의료선) 15개로 초반부 시간 벌기
    중반부 전략 : 공성 전차를 활용한 중반부 싸움
    후반부 전략 : 밤까마귀를 활용한 방어선 생성, 전투 순양함(야마토 포, 전술 차원 도약)을 사용하여 적 사령부 공격, 유령 전술핵 사용
    """
    def __init__(self, *args, **kwargs):
        super().__init__()
        self.build_order = list() # 생산할 유닛 목록

    def on_start(self):
        """
        새로운 게임마다 초기화
        """
        self.build_order = list()
        self.evoked = dict()
        
        # 초반 빌드 오더 생성 (해병 24, 밴시 3)
        for _ in range(3):
            for _ in range(8):
                self.build_order.append(UnitTypeId.MARINE)
            self.build_order.append(UnitTypeId.BANSHEE)

        # 중반 빌드 오더 (해병: 2, 공성 전차 : 1, 화염차 : 1 - 다섯 번 반복)
        for _ in range(5):
            for _ in range(2):
                self.build_order.append(UnitTypeId.MARINE)
            self.build_order.append(UnitTypeId.SIEGETANK)
            self.build_order.append(UnitTypeId.HELLION)

    async def on_step(self, iteration: int):       
        actions = list()

        combat_units = self.units.exclude_type(
            [UnitTypeId.COMMANDCENTER, UnitTypeId.MEDIVAC, UnitTypeId.RAVEN, UnitTypeId.BATTLECRUISER, UnitTypeId.GHOST, UnitTypeId.MULE]
        )
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
        if self.can_afford(self.build_order[0]) and self.time - self.evoked.get((cc.tag, 'train'), 0) > 1.0:
            # 해당 유닛 생산 가능하고, 마지막 명령을 발행한지 1초 이상 지났음
            actions.append(cc.train(self.build_order[0]))  # 첫 번째 유닛 생산 명령 
            del self.build_order[0]  # 빌드오더에서 첫 번째 유닛 제거
            self.evoked[(cc.tag, 'train')] = self.time

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
                if combat_units.amount >= 15:   # 나중에 다른 유닛 개수랑 더하는 것으로 수정하기
                    # 전투가능한 유닛 수가 15를 넘으면 적 본진으로 공격
                    actions.append(unit.attack(target))
                    use_stimpack = True
                else:
                    # 적 사령부 방향에 유닛 집결
                    target = self.start_location + 0.25 * (enemy_cc.position - self.start_location)
                    actions.append(unit.attack(target))
                    use_stimpack = False

                if use_stimpack and unit.distance_to(target) < 15:
                    # 유닛과 목표의 거리가 15이하일 경우 스팀팩 사용
                    if not unit.has_buff(BuffId.STIMPACK) and unit.health_percentage > 0.5:
                        # 현재 스팀팩 사용중이 아니며, 체력이 50% 이상
                        if self.time - self.evoked.get((unit.tag, AbilityId.EFFECT_STIM), 0) > 1.0:
                            # 1초 이전에 스팀팩을 사용한 적이 없음
                            actions.append(unit(AbilityId.EFFECT_STIM))
                            self.evoked[(unit.tag, AbilityId.EFFECT_STIM)] = self.time
            
            # 화염차 명령
            if unit.type_id is UnitTypeId.HELLION:
                if combat_units.amount >= 15:
                    actions.append(unit.attack(target))
                else:
                    target = self.start_location + 0.25 * (enemy_cc.position - self.start_location)
                    actions.append(unit.attack(target))

            # 공성 전차 명령
            if unit.type_id is UnitTypeId.SIEGETANK: 
                if combat_units.amount >= 15:   # 나중에 다른 유닛 개수랑 더하는 것으로 수정하기
                    # 전투가능한 유닛 수가 15를 넘으면 적 본진으로 공격
                    actions.append(unit.attack(target))
                else:
                    # 적 사령부 방향에 유닛 집결
                    defense_pos = self.start_location + 0.25 * (enemy_cc.position - self.start_location)
                    actions.append(unit.attack(defense_pos))

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
                # 적 사령부로 전술 차원 도약
                if await self.can_cast(unit, AbilityId.EFFECT_TACTICALJUMP, target=enemy_cc):
                    actions.append(unit(AbilityId.EFFECT_TACTICALJUMP, target=enemy_cc))
                
                actions.append(unit.attack(target))
                
                # 야마토 포 시전 가능하면 시전
                if await self.can_cast(unit, AbilityId.YAMATO_YAMATOGUN, target=target):
                    actions.append(unit(AbilityId.YAMATO_YAMATOGUN, target=target))

            # 의료선 명령
            if unit.type_id is UnitTypeId.MEDIVAC:
                if wounded_units.exists:
                    wounded_unit = wounded_units.closest_to(unit)  # 가장 가까운 체력이 100% 이하인 유닛
                    actions.append(unit(AbilityId.MEDIVACHEAL_HEAL, wounded_unit))  # 유닛 치료 명령
                else:
                    # 회복시킬 유닛이 없으면, 전투 그룹 중앙에서 대기
                    try:
                        actions.append(unit.move(combat_units.center))
                    except:
                        actions.append(unit(AbilityId.MOVE_MOVE, target=cc))

            # 유령 명령
            if unit.type_id is UnitTypeId.GHOST:
                ghost_abilities = await self.get_available_abilities(unit)
                cc_abilities = await self.get_available_abilities(cc)
                nukes = self.units(UnitTypeId.NUKE)

                if nukes.amount == 0 and AbilityId.BUILD_NUKE in cc_abilities:
                    # 전술핵 생산 가능(자원이 충분)하면 전술핵 생산
                    actions.append(cc(AbilityId.BUILD_NUKE))

                if AbilityId.TACNUKESTRIKE_NUKECALLDOWN in ghost_abilities and unit.is_idle:
                    # 전술핵 발사 가능(생산완료)하고 고스트가 idle 상태이면, 적 본진에 전술핵 발사
                    actions.append(unit(AbilityId.BEHAVIOR_CLOAKON_GHOST))
                    actions.append(unit(AbilityId.TACNUKESTRIKE_NUKECALLDOWN, target=enemy_cc))
                    actions.append(unit.attack(cc))

                if cc.distance_to(unit) < 10 and AbilityId.EMP_EMP in ghost_abilities:
                    emp_targets = self.known_enemy_units.filter(lambda unit: unit.name in ["Battlecruiser", "SiegeTank", "SiegeTankSieged", "Banshee", "Raven", "Medivac"])
                    if emp_targets:
                        emp_target = emp_targets[0]
                        actions.append(unit(AbilityId.EMP_EMP, target=emp_target))
                    actions.append(unit.attack(target))
            
            # 밤까마귀 명령
            if unit.type_id is UnitTypeId.RAVEN:
                if combat_units.amount >= 15:
                    actions.append(unit(AbilityId.SCAN_MOVE, target=combat_units.center))
                else:
                    target = self.start_location + 0.25 * (enemy_cc.position - self.start_location)
                    actions.append(unit.attack(target))
                              
                raven_abilities = await self.get_available_abilities(unit)
                # 대장갑 미사일 이용하여 상대 사령부 쪽으로 공격시 전투순양함 대상 공격
                missile_targets = self.known_enemy_units.filter(lambda unit: unit.name == "Battlecruiser")
                if missile_targets:
                    missile_target = missile_targets[0]
                    if AbilityId.EFFECT_ANTIARMORMISSILE in raven_abilities:
                        actions.append(unit(AbilityId.EFFECT_INTERFERENCEMATRIX, target=missile_target))
                else:
                    # 전투순양함이 없는데 밤까마귀가 있는 경우 + 공격 모드일 때
                    # 밤까마귀를 은신 유닛 탐지에 이용, 다른 아군 공격 유닛들과 함께 전투 유닛 중앙에 배치
                    matrix_targets = self.known_enemy_units.filter(lambda unit: unit.name in ["SiegeTank", "SiegeTankSieged", "VikingAssault", "VikingFigher", "Battlecruiser"])
                    if matrix_targets:
                        matrix_target = matrix_targets[0]
                        if AbilityId.EFFECT_INTERFERENCEMATRIX in raven_abilities:
                            actions.append(unit(AbilityId.EFFECT_INTERFERENCEMATRIX, target=target.position))
                        else:
                            # 자동 포탑 - 방어선으로 이용: 아군 사령부보다 거리 7 앞에서 방어공격
                            # 아군 사령부 쪽에(거리 7 이하) 적 유닛 존재하면 자동 포탑 설치
                            if AbilityId.BUILDAUTOTURRET_AUTOTURRET in raven_abilities:
                                if cc.distance_to(enemy_unit) < 7:
                                    if enemy_cc==Point2(Point2((95.5, 31.5))):
                                        actions.append(unit(AbilityId.BUILDAUTOTURRET_AUTOTURRET, target=Point2(Point2((38.5, 31.5)))))
                                    else:
                                        actions.append(unit(AbilityId.BUILDAUTOTURRET_AUTOTURRET, target=Point2(Point2((89.5, 31.5)))))    

                
            # 밴시 명령
            if unit.type_id is UnitTypeId.BANSHEE:
                if combat_units.amount >= 15:
                    actions.append(unit(AbilityId.BEHAVIOR_CLOAKON_BANSHEE))
                else:
                    target = self.start_location + 0.25 * (enemy_cc.position - self.start_location)
                actions.append(unit.attack(target))
        await self.do_actions(actions)
