"""
경진대회 플랫폼 목적에 맞게 python-sc2의 기본 동작을 수정할 필요가 있음
여기에는 실행시간에 python-sc2의 행동을 수정하기 위한 코드가 있음
이 모듈은 반드시 sc2 (python-sc2) 보다 먼저 import 되어야 함

향후, 여기서 부정행위(예. API로 시야밖의 적 정보 확인, 적 유닛 파괴)에 
사용할 수 있는 API를 사용하지 못하도록 막을 예정
"""

__author__ = "박현수(hspark8312@ncsoft.com), NCSOFT Game AI Lab"

import glob
import platform
from pathlib import Path
from toolbox.logger.colorize import Color as C

VERSION_PATH = {
    "Windows": Path("C:/Program Files (x86)/StarCraft II/Versions"),
    "Linux": Path.home() / 'StarCraftII/Versions',
}

version_path = VERSION_PATH[platform.system()]
latest_version = sorted(version_path.glob('Base*'))[-1]
build_no = int(latest_version.name[4:])

# 버전정보: https://github.com/Blizzard/s2client-proto/blob/master/buildinfo/versions.json


if build_no >= 74071:
    # 4.9.0 이후 버전
    print(C.info('SC2 4.9.0 용 패치 적용'))
    import sc2_patch.sc2_patch_490

elif build_no >= 73559:
    # 4.8.5 이후 버전
    print(C.info('SC2 4.8.5 용 패치 적용'))
    import sc2_patch.sc2_patch_485
    
else:
    # 그 외
    print(C.info('SC2 4.7.1 용 패치 적용'))
    import sc2_patch.sc2_patch_471
    
