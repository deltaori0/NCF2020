#!/usr/bin/env python

__author__ = '박현수(hspark8312@ncsoft.com), NSSOFT Game AI Lab'


import csv
import itertools
import logging
import multiprocessing as mp
import os
import platform
import shlex
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from IPython import embed
from sc2_utils import kill_starcraft_ii_processes
from termcolor import colored, cprint
from tqdm import tqdm, trange

from eval.export import export_results
from eval.play_game import run_play_game

from . import config
from .config import args

logger = logging.getLogger(__file__)
logger.setLevel(logging.DEBUG)


def update_bots(config):
    result = list()
    for name in config.teams:
        team = config.teams[name]
        if Path(team.target).exists():
            # pull bots
            cmd = f'git pull'
            ret = subprocess.call(shlex.split(cmd), cwd=team.target)
        else:
            # clone bots
            cmd = f'git clone {team.repo} {team.target}'
            ret = subprocess.call(shlex.split(cmd))

        if ret == 0:
            cprint(f'> {name} 업데이트 성공', 'green')
        else:
            cprint(f'> {name} 업데이트 실패', 'red')
            cprint(f'> {cmd}')
            exit(1)

        result.append(ret)
        time.sleep(1)
    return result


def play_games(config, round_start, round_end, verbose):
    config.replay_dir.mkdir(exist_ok=True, parents=True)

    # 게임 생성
    match_list = list(itertools.product(config.teams, config.teams))

    excludes = list()
    if config.csv_file.exists():
        with open(config.csv_file, 'rt') as f:
            reader = csv.reader(f)
            for line in reader:
                n, p1, p2, *_ = line
                excludes.append(f'{n}-{p1}-{p2}')

    # 게임 실행
    n_updates = 0
    for n in trange(round_start, round_end):
        for match in tqdm(match_list, leave=False):
            p1, p2 = match

            round_key = f'{n}-{p1}-{p2}'
            if round_key in excludes:
                if verbose:
                    tqdm.write(f'SKIP: {round_key}')
                continue
            else:
                n_updates += 1

            bot1 = config.teams[p1].class_path
            bot2 = config.teams[p2].class_path

            if args.save_replay:
                replay_path = str(config.replay_dir / f'{p1}-{p2}' / f'{p1}-{p2}-{n}.SC2Replay')
            else:
                replay_path = None
            log_path = config.replay_dir / f'{p1}-{p2}' / f'{p1}-{p2}-{n}.log'
            log_path.parent.mkdir(exist_ok=True, parents=True)

            realtime = False
            map_name = config.args.map_name
            timeout = config.args.timeout

            start = time.monotonic()

            try:
                result = run_play_game(config, bot1, bot2, map_name, realtime, timeout, replay_path, log_path, verbose)
                if verbose:
                    if result[0] == 1.0 and result[1] == 0.0:
                        color = ('white', 'on_red')
                    elif result[0] == 0.0 and result[1] == 1.0:
                        color = ('white', 'on_blue')
                    else:
                        color = ('grey', 'on_yellow')
                    tqdm.write(colored(f'Round: {n}, {p1}: {result[0]}, {p2}: {result[1]}, error: {result[2]}', *color))

            except Exception as e:
                result = [0.5, 0.5, 1.0]
                with open(config.system_log_file, 'at') as f:
                    f.write(f'{bot1}, {bot2}\n')
                    f.write(f'{e}\n')

            play_time = int(time.monotonic() - start)

            # 결과 기록
            with open(config.csv_file, 'at') as f:
                writer = csv.writer(f)
                writer.writerow([n, p1, p2, map_name, result[0], result[1], result[2], play_time])

            time.sleep(15)
            kill_starcraft_ii_processes()

    return n_updates > 0


def sync_results(config, push: bool):

    # git 저장소가 없으면 clone
    if not config.out_dir.exists():
        os.system(f'rm -r {config.out_dir}')
        cmd = f'git clone {config.out_repo} {config.out_dir}'
        cprint(cmd, 'green')
        os.system(cmd)

    config.bot_dir.mkdir(parents=True, exist_ok=True)
    config.replay_dir.mkdir(parents=True, exist_ok=True)
    config.fig_dir.mkdir(parents=True, exist_ok=True)
    config.log_dir.mkdir(parents=True, exist_ok=True)

    cwd =  os.getcwd()
    os.chdir(config.out_dir)

    # git 저장소에 push
    if (cwd / config.out_dir / '.git' / 'index.lock').exists():
        (cwd / config.out_dir / '.git' / 'index.lock').unlink()
    if (cwd / config.out_dir / '.git' / 'config.lock').exists():
        (cwd / config.out_dir / '.git' / 'config.lock').unlink()

    if push:
        cmds = [
            'git pull -f',
            'git add -u',
            'git add *',
            f'git commit -m "{datetime.now().isoformat()}"',
            # f'git remote add origin {config.out_repo}',
            # 'git push -u origin master',
            'git push origin master:master',
        ]
    else:
        cmds = ['git pull -f']

    for cmd in cmds:
        cprint(cmd, 'green')
        # os.system(cmd)
        ret = subprocess.call(shlex.split(cmd))
        if ret != 0:
            cprint(f'실패 > {cmd}', 'red')
            exit(1)



    os.chdir(cwd)

if __name__ == '__main__':

    """
    # 플레이, 분석, 게시 실행
    python -m eval.run ../config.csv --verbose  --publish_results=True

    # 플레이 실행
    python -m eval.run ../config.csv --verbose --publish_results=False
    python -m eval.run ../config.csv --update_bots=True --play_games=True --export_results=False --verbose

    # 플레이 안하고, 결과 분석만 실행
    python -m eval.run ../config.csv --root_dir=../{root} --update_bots=False --play_games=False --export_results=True --publish_results=False --verbose

    # 출력문서 변환
    pandoc README.rst -f rst -t html -s -o README.html
    """

    cprint(f'* 평가: {config.root_dir}', 'green', 'on_red')

    sync_results(config, push=False)

    if args.update_bots:
        cprint(f'* 봇 업데이트', 'green', 'on_red')
        result = update_bots(config)
        if any(result):
            cprint(f'> 업데이트 실패', 'red')
            exit(1)

    df = pd.read_csv(config.csv_file, names=config.csv_columns)
    # 현재 봇 목록에 없으면 제외
    xs = list(config.teams.keys())
    df = df[df['p1'].apply(lambda x: x in xs) | df['p2'].apply(lambda x: x in xs)]
    # 게임 start/종료 번호 식별
    round_start = df['no'].max() + 1
    round_end = round_start + args.rounds

    if args.play_games:
        cprint(f'* 토너먼트 시작 {round_start} -> {round_end}', 'green', 'on_red')
        play_games(config, round_start, round_end, verbose=config.verbose)

    if args.export_results:  
        cprint(f'* 결과 분석 및 출력', 'green', 'on_red')
        export_results(config)
        
    if args.publish_results:
        cprint(f'* 토너먼트 결과 공개', 'green', 'on_red')
        sync_results(config, push=True)
    else:
        cprint(f'python -m eval.run ../config.csv --root_dir={config.root_dir} --update_bots=False --play_games=False --export_results=False --publish_results=True --verbose', 'green')
