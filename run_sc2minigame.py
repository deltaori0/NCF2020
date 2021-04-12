#!/usr/bin/env python

__author__ = '박현수(hspark8312@ncsoft.com), NSSOFT Game AI Lab'

import argparse
import importlib
import logging
import multiprocessing as mp
import os
import platform

import numpy as np
import sc2
from IPython import embed
from sc2 import Difficulty, Race, maps, run_game
from sc2.data import Result
from sc2.player import Bot, Computer
from tqdm import trange

logger = logging.getLogger(__file__)
logger.setLevel(logging.DEBUG)

if __name__ == '__main__':

    parser = argparse.ArgumentParser('NC Fellowship 2020-sc2minigame-run_game')
    # player 설정
    parser.add_argument(
        '--bot1',
        type=str,
        default='bots.nc5_example',
        help='bot 1 (player 1) 설정')
    parser.add_argument(
        '--bot2',
        type=str,
        default='com7',
        help='bot 2 (player 2) 설정 (기본값: 기본 컴퓨터 난이도 7)')
    # 게임 정보
    parser.add_argument(
        '--map_name',
        type=str,
        default='NCF-2020-v4',
        help='경진대회 기본 맵')
    parser.add_argument('--n_games', type=int, default=1)
    # 옵션
    parser.add_argument(
        '--realtime',
        action='store_true',
        help='false일 때는 빠르게 게임이 실행됨')
    parser.add_argument(
        '--render',
        action='store_true',
        help='True일때는 rendering option을 사용함'
    )
    parser.add_argument(
        '--save_replay_as',
        type=str,
        help='저장할 리플레이 파일 이름, 예) test.SC2Replay'
    )
    args = parser.parse_args()

    # map 정보 읽기
    try:
        game_map = maps.get(args.map_name)
    except KeyError:
        assert os.path.exists(args.map_name +
                              '.SC2Map'), f"지도 파일을 찾을 수 없음!: {args.map_name}"
        game_map = args.map_name

    # bot 초기화
    bots = list()
    for bot_path in (args.bot1, args.bot2):
        try:
            if len(bot_path) == 4 and bot_path.lower().startswith('com'):
                # bot 경로 시작이 com으로 시작하면 기본 AI를 사용함
                level = int(bot_path[3])
                # 4번째 문자는 봇의 난이도를 뜻함
                # 예) com7 -> 기본 AI 난이도 7
                # 난이도는 1~10까지 있음
                assert 1 <= level <= 10
                bot = Computer(Race.Terran, Difficulty(level))
            else:
                # 일반 bot 임포트
                module, name = bot_path.rsplit('.', 1)
                module = bot_path + '.bot'
                name = 'Bot'
                bot_cls = getattr(importlib.import_module(module), name)
                # debug 인자를 반드시 전달함
                bot_ai = bot_cls()
                bot = Bot(Race.Terran, bot_ai)
            bots.append(bot)
        except ImportError:
            import traceback
            logger.error(f"bot 클래스를 임포트 할 수 없음: {bot_path}")
            traceback.print_exc()
            exit(1)

    if args.render:
        rgb_render_config=dict(window_size=(800, 480), minimap_size=(128, 128))
    else:
        rgb_render_config = None

    result = sc2.run_game(
        game_map, 
        bots, 
        realtime=args.realtime, 
        rgb_render_config=rgb_render_config,
        save_replay_as=args.save_replay_as)
    print(result)
