
import argparse
import csv
from collections import namedtuple
from datetime import datetime
from pathlib import Path

from IPython import embed

from sc2_utils import parse_bool
from termcolor import cprint


def parse_bool(s):
    return s in ('True', 'true', '1')

parser = argparse.ArgumentParser('NC Fellowship 2020-eval')
# 평가 정보가 저장된 경로
parser.add_argument('config_csv', type=Path)
parser.add_argument('--root_dir', type=Path)
# 작업 목록
parser.add_argument('--update_bots', type=parse_bool, default=True)
parser.add_argument('--play_games', type=parse_bool, default=True)
parser.add_argument('--export_results', type=parse_bool, default=True)
parser.add_argument('--publish_results', type=parse_bool, default=True)
# 옵션
parser.add_argument('--rounds', type=int, default=10)
parser.add_argument('--max_rounds', type=int, default=100)
parser.add_argument('--map_name', type=str, default='NCF-2020-v4')
parser.add_argument('--timeout', type=int, default=1800)
parser.add_argument('--save_replay', type=parse_bool, default=True)
parser.add_argument('--replay_path', type=str, default=None)
parser.add_argument('--alpha', type=float, default=None)
parser.add_argument('--init_elo_rating', type=float, default=1000)
parser.add_argument('--verbose', action='store_true')
parser.add_argument('--out_repo', type=str, default='https://github.com/rex8312/NCF2020_Eval.git')
args = parser.parse_args()


# 평가시작시간
t_start = datetime.now()

# 평가용 봇과 결과가 저장되는 폴더
if args.root_dir is None:
    root_dir = Path(f"../T/{datetime.now().isoformat().replace(':', '-').split('.')[0]}")
else:
    root_dir = args.root_dir
root_dir.mkdir(parents=True, exist_ok=True)
out_dir = root_dir / 'results'
bot_dir = root_dir / 'bots'
replay_dir = out_dir / 'replays'
fig_dir = out_dir / 'fig'
log_dir = out_dir / 'log'
csv_file = log_dir / 'result.csv'
system_log_file = log_dir / 'system.log'

# 봇 저장소 목록 읽기
with args.config_csv.open() as f:
    reader = csv.reader(f)
    repos = [
        (name.strip().replace(' ', '_'), repo.strip()) 
        for name, repo, *_ in reader if repo.strip() != ''
    ]
    names_, repos_ = zip(*repos)
    assert len(names_) == len(set(names_)), "중복된 bot 이름이 있음"
    assert len(repos_) == len(set(repos_)), "중복된 저장소가 이름이 있음"
    repos = {name: repo for name, repo in repos}
    
# 봇 정보 저장
Team = namedtuple('Team', 'name, repo, target, class_path')

teams = dict()
for name in repos.keys():
    user_id, repo_name, *dirs = repos[name].split('https://github.com/')[1].split('/')
    url = f'https://github.com/{user_id}/{repo_name}'
    dirs = ''.join('.'.join(dirs).split('tree.master.')[1:])
    target = bot_dir / user_id
    # class_path = f'{root_dir}.{user_id}.bot.Bot' if dirs == '' else f'{root_dir}.{user_id}.{dirs}.bot.Bot'
    class_path = f'{user_id}.bot.Bot' if dirs == '' else f'{user_id}.{dirs}.bot.Bot'
    teams[name] = Team(name, url, target, class_path)

# 게임결과 저장/읽기에 사용
csv_columns = ['no', 'p1', 'p2', 'map', 'p1_score', 'p2_score', 'error', 'play_time']

rounds = args.rounds
max_rounds = args.max_rounds
init_elo_rating = args.init_elo_rating
verbose = args.verbose
out_repo = args.out_repo
