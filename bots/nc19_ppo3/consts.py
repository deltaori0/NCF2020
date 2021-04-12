

from enum import Enum
from collections import namedtuple
from sc2.ids.unit_typeid import UnitTypeId


#
#  ProxyEnv와 Actor가 주고 받는 메시지 타입
#

class CommandType(bytes, Enum):
    PING = b'\x00'
    REQ_TASK = b'\x01'
    STATE = b'\x02'
    SCORE = b'\x03'
    ERROR = b'\x04'


class EconomyStrategy(Enum):
    MARINE = UnitTypeId.MARINE
    MARAUDER = UnitTypeId.MARAUDER
    REAPER = UnitTypeId.REAPER
    GHOST = UnitTypeId.GHOST
    HELLION = UnitTypeId.HELLION
    SIEGETANK = UnitTypeId.SIEGETANK
    THOR = UnitTypeId.THOR
    MEDIVAC = UnitTypeId.MEDIVAC
    VIKINGFIGHTER = UnitTypeId.VIKINGFIGHTER
    BANSHEE = UnitTypeId.BANSHEE
    RAVEN = UnitTypeId.RAVEN
    BATTLECRUISER = UnitTypeId.BATTLECRUISER


EconomyStrategy.to_index = dict()
EconomyStrategy.to_type_id = dict()

for idx, strategy in enumerate(EconomyStrategy):
    EconomyStrategy.to_index[strategy.value] = idx
    EconomyStrategy.to_type_id[idx] = strategy.value


class ArmyStrategy(Enum):
    DEFENSE_SIMPLE = 0 # 기존 DEFENSE mode
    DEFENSE_SIEGETANK = 1 # 시즈탱크 이용한 방어선 구축
    OFFENSE_LOW = 2 # 기존 OFFENSE mode
    OFFENSE_MID = 3 # 중간 비용 유닛 이용한 중간 단계의 OFFENSE mode
    OFFENSE_HIGH = 4 # high-end 유닛 이용한 높은 단계의 OFFENSE mode



Sample = namedtuple('Sample', 's, a, r, done, logp, value')


class MessageType(Enum):
    RESULT = 0
    EXCEPTION = 1


N_FEATURES = 5 + 12
N_ACTIONS = len(EconomyStrategy) * len(ArmyStrategy)
