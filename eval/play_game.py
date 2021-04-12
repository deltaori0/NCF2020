#!/usr/bin/env python

__author__ = '박현수(hspark8312@ncsoft.com), NSSOFT Game AI Lab'

import argparse
import datetime
import importlib
import logging
import multiprocessing as mp
import os
import platform
import shlex
import shutil
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import sc2
from IPython import embed
from sc2 import Difficulty, Race, maps
from sc2.data import Result
from sc2.player import Bot, Computer
from termcolor import cprint
from tqdm import tqdm, trange

logger = logging.getLogger(__file__)
logger.setLevel(logging.DEBUG)


def run_play_game(config, bot1, bot2, map_name, realtime, timeout, replay_path, log_path, verbose):
    # TODO: 시간초과 검사
    # TODO: 예외처리
    # TODO: 시간측정
    cmd = f'python -m eval.play_game --bot_dir={config.bot_dir} --bot1={bot1} --bot2={bot2} --map_name={map_name} --realtime={realtime}'
    if replay_path is not None:
         cmd += f' --replay_path={replay_path}'

    result = [0.5, 0.5, 0.0]
    try:
        if verbose:
            tqdm.write(f'[{datetime.datetime.today().isoformat()}] {cmd}')
        pout = subprocess.run(
            shlex.split(cmd), 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE, 
            timeout=timeout
        )
        lines = pout.stdout.split(b'\n')
        for line in lines:
            line = line.strip()
            if b'INFO:root:Result for player 1 - ' in line:
                if line.endswith(b' Victory'):
                    result[0] = 1.0
                    result[1] = 0.0
                elif line.endswith(b' Defeat'):
                    result[0] = 0.0
                    result[1] = 1.0
            elif b'INFO:root:Result for player 2 - ' in line:
                if line.endswith(b' Victory'):
                    result[0] = 0.0
                    result[1] = 1.0
                elif line.endswith(b' Defeat'):
                    result[0] = 1.0
                    result[1] = 0.0
            elif b'ERROR:sc2_patch.sc2_patch_490.main:' in line:
                result[2] = 1.0

        stdout_lines = pout.stdout.split(b'\n') 
        stdout_lines = [line.rstrip().decode('utf-8') for line in stdout_lines]
        stderr_lines = pout.stderr.split(b'\n')
        stderr_lines = [line.rstrip().decode('utf-8') for line in stderr_lines]
        lines = ['## STDOUT ##\n'] + stdout_lines + ['\n## STDERR ##\n'] + stderr_lines
        log_path.write_text('\n'.join(lines))
        assert sum(result[0:2]) == 1.0, f'result: {result}'

    except subprocess.TimeoutExpired:
        result[2] = 1.0

    return result


def play_game(bot_dir, bot1, bot2, map_name, realtime, replay_path):

    sys.path.insert(0, str(Path(bot_dir).absolute()))

    try:
        game_map = maps.get(map_name)
    except KeyError:
        assert os.path.exists(args.map_name + '.SC2Map'), f"지도 파일을 찾을 수 없음!: {args.map_name}"
        game_map = map_name

    # bot 초기화
    bots = list()
    for player_no, bot_path in enumerate([bot1, bot2]):
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
                bot_cls = getattr(importlib.import_module(module), name)
                # debug 인자를 반드시 전달함
                # bot_ai = bot_cls(debug=args.debug)
                bot_ai = bot_cls()
                bot = Bot(Race.Terran, bot_ai)
            bots.append(bot)
        except AttributeError:
            import traceback
            logger.error(f"bot 클래스를 임포트 할 수 없음: {bot_path}")
            logger.error(f'INFO:root:Result for player {player_no + 1} - Defeat')
            traceback.print_exc()
            exit(1)
        except ImportError:
            import traceback
            logger.error(f"bot 클래스를 임포트 할 수 없음: {bot_path}")
            traceback.print_exc()
            exit(1)
    
    result = sc2.run_game(game_map, bots, realtime=realtime, save_replay_as=replay_path)
    return result


if __name__ == '__main__':

    parser = argparse.ArgumentParser('NC Fellowship 2020-play_game')
    parser.add_argument('--bot_dir', type=str)
    parser.add_argument('--bot1', type=str)
    parser.add_argument('--bot2', type=str)
    parser.add_argument('--map_name', type=str, default='NCF-2020-v4')
    parser.add_argument('--realtime', type=lambda x: x in ('True', 'true', '1'), default=True)
    parser.add_argument('--replay_path', type=str, default=None)
    args = parser.parse_args()

    play_game(args.bot_dir, args.bot1, args.bot2, args.map_name, args.realtime, args.replay_path)
