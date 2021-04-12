"""
기존 known_enemy_units, known_enemy_structures는 property_cache로 정의되어 있는데,
1 vs. 1 플레이에서 자신의 유닛을 적 유닛으로 판단하는 문제가 발생할 수 있어서,
일단 일반 property로 변경함

property_cache가 속도향상 이외에 다른 기능을 가지고 있는지는 확인하지 않았음
"""

__author__ = "박현수(hspark8312@ncsoft.com), NCSOFT Game AI Lab"


from sc2.units import Units


@property
def known_enemy_units(self) -> Units:
    """List of known enemy units, including structures."""
    return self.state.enemy_units


@property
def known_enemy_structures(self) -> Units:
    """List of known enemy units, structures only."""
    return self.state.enemy_units.structure
