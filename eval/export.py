
import csv
import os
from datetime import datetime

import matplotlib
import matplotlib.font_manager
import matplotlib.pyplot as plt
import networkx as nx
import numpy as np
import pandas as pd
import scipy.linalg as la
from IPython import embed

from . import config

matplotlib.rc('font', family="NanumMyeongjo")
# matplotlib.rc('font', family="Noto Sans Mono CJK KR")  # sudo apt install  fonts-noto-cjk
matplotlib.font_manager._rebuild()
FIG_SIZE = (13, 13)


def export_results(config):

    df = pd.read_csv(config.csv_file, names=config.csv_columns)

    # p1과 p2가 같은 봇이면 제외
    # df = df[df['p1'] != df['p2']] 

    # 현재 봇 목록에 없으면 제외
    xs = list(config.teams.keys())
    df = df[df['p1'].apply(lambda x: x in xs) | df['p2'].apply(lambda x: x in xs)]

    # 이번주 실시한 최근 게임만 선택
    df = df[df['no'] > df['no'].max() - config.rounds]
    round_start = df['no'].max() - config.rounds + 1
    round_end = df['no'].max()

    #
    # 승률
    # 
    df_score = df[['p1', 'p2', 'p1_score']]
    df_score.columns = ['p1', 'p2', 'win']
    grouped_score = df_score.groupby(['p1', 'p2'])
    win_ratio = grouped_score.mean().unstack(1).fillna(value=0.0)
    win_count = grouped_score.sum().unstack(1).fillna(value=0)
    total_count = grouped_score.count().unstack(1).fillna(value=0)

    fig, ax = plt.subplots(figsize=FIG_SIZE)
    names = win_ratio.index.to_list()
    ax.set_xticks(np.arange(len(names)))
    ax.set_yticks(np.arange(len(names)))
    [tick.set_rotation(45) for tick in ax.get_xticklabels()]
    ax.set_xticklabels(names)
    ax.set_yticklabels(names)
    values = win_ratio.to_numpy()
    ax.imshow(values, vmin=0.0, vmax=1.0, cmap='gray')
    for j, name_j in enumerate(names):
        for i, name_i in enumerate(names):
            value = values[j, i]
            brightness = 1.0 - value
            if abs(brightness - value) < 0.3:
                if value > 0.5:
                    brightness = value - 0.3
                else:
                    brightness = value + 0.3
            brightness = min(1.0, brightness)
            brightness = max(0.0, brightness)
            # if j != i:
            wc = int(win_count.values[j, i])
            tc = int(total_count.values[j, i])
            if tc > 0:
                text = ax.text(
                    i, 
                    j, 
                    f'{wc:d}/{tc:d}={wc/tc:.2f}', 
                    ha="center", 
                    va="center", 
                    color=(brightness, brightness, brightness)
                )
    # plt.show()
    plt.savefig(config.fig_dir / 'score_as_player1.png')
    plt.clf()

    #
    # 에러
    #
    df_error = df[['p1', 'p2', 'error']]
    grouped_error = df_error.groupby(['p1', 'p2'])
    error_ratio = grouped_error.mean().unstack(1).fillna(value=0.0)
    error_count = grouped_error.sum().unstack(1).fillna(value=0)

    fig, ax = plt.subplots(figsize=FIG_SIZE)
    names = win_ratio.index.to_list()
    ax.set_xticks(np.arange(len(names)))
    ax.set_yticks(np.arange(len(names)))
    [tick.set_rotation(45) for tick in ax.get_xticklabels()]
    ax.set_xticklabels(names)
    ax.set_yticklabels(names)
    values = error_ratio.to_numpy()
    ax.imshow(values, vmin=0.0, vmax=1.0, cmap='gray')
    for j, name_j in enumerate(names):
        for i, name_i in enumerate(names):
            value = values[j, i]
            brightness = 1.0 - value
            if abs(brightness - value) < 0.3:
                if value > 0.5:
                    brightness = value - 0.3
                else:
                    brightness = value + 0.3
            brightness = min(1.0, brightness)
            brightness = max(0.0, brightness)
            # if j != i:
            wc = int(error_count.values[j, i])
            tc = int(total_count.values[j, i])
            if tc > 0:
                text = ax.text(
                    i, 
                    j, 
                    f'{wc:d}/{tc:d}={wc/tc:.2f}', 
                    ha="center", 
                    va="center", 
                    color=(brightness, brightness, brightness)
                )
    # plt.show()
    plt.savefig(config.fig_dir / 'error.png')
    plt.clf()

    #
    # 게임 플레이 시간
    #
    df_play_time = df[['p1', 'p2', 'play_time']]
    grouped_play_time = df_play_time.groupby(['p1', 'p2'])
    min_play_time = df_play_time['play_time'].min()
    play_times = grouped_play_time.mean().unstack(1).fillna(value=min_play_time)

    fig, ax = plt.subplots(figsize=FIG_SIZE)
    names = win_ratio.index.to_list()
    ax.set_xticks(np.arange(len(names)))
    ax.set_yticks(np.arange(len(names)))
    [tick.set_rotation(45) for tick in ax.get_xticklabels()]
    ax.set_xticklabels(names)
    ax.set_yticklabels(names)
    values = play_times.to_numpy()
    ax.imshow(values, vmin=values.min().min(), vmax=values.max().max(), cmap='gray')
    for j, name_j in enumerate(names):
        for i, name_i in enumerate(names):
            value = values[j, i]
            bg = (values[j, i] - values.min().min()) / (values.max().max() - values.min().min())
            font = 1.0 - bg
            if abs(font - bg) < 0.3:
                if value > 0.5:
                    font = bg - 0.3
                else:
                    font = bg + 0.3
            font = min(1.0, font)
            font = max(0.0, font)
            tc = int(total_count.values[j, i])
            if tc > 0:
                text = ax.text(
                    i, 
                    j, 
                    f'{values[j, i]:.2f}', 
                    ha="center", 
                    va="center", 
                    color=(font, font, font)
                )
    # plt.show()
    plt.savefig(config.fig_dir / 'play_time.png')
    plt.clf()

    #
    # TABLE
    #
    win_count.columns = [c[1] for c in win_count.columns]
    total_count.columns = [c[1] for c in total_count.columns]
    error_count.columns = [c[1] for c in error_count.columns]

    p1_scores = win_count.sum(axis=1) / total_count.sum(axis=1)
    p2_scores = 1 - win_count.T.sum(axis=1) / total_count.T.sum(axis=1)
    total_wins = (win_count.sum(axis=1) + (total_count.T - win_count.T).sum(axis=1))
    total_n_games = (total_count.sum(axis=1) + total_count.T.sum(axis=1))
    total_scores = total_wins / total_n_games

    kv = {
        'win ratio': total_scores,
        '#wins (p1)': win_count.sum(axis=1).astype(np.int32), 
        '#games (p1)': total_count.sum(axis=1).astype(np.int32), 
        'win ratio (p1)': p1_scores,
        '#wins (p2)': (total_count.T - win_count.T).sum(axis=1).astype(np.int32), 
        '#games (p2)': total_count.T.sum(axis=1).astype(np.int32), 
        'win ratio (p2)': p2_scores,
        '#errors': error_count.sum(axis=1).astype(np.int32),
        'play_time': play_times.mean(axis=1),
    }
    summary = pd.concat(kv.values(), axis=1, sort=True)
    summary.index.name = 'bot'
    summary.columns = kv.keys()
    summary = summary.sort_values(by='win ratio', ascending=False)

    print(summary)
    # summary.to_excel(config.out_dir / 'summary.xlsx', sheet_name='Sheet1')
    summary.to_csv(config.log_dir / 'summary.csv')

    #
    # 전이 그래프
    #
    p1_win_raito = total_count / (total_count + total_count.T) * win_count / total_count
    p2_win_ratio = total_count.T / (total_count + total_count.T) * (1 - (win_count.T / total_count.T))
    total_win_raito = p1_win_raito + p2_win_ratio

    error_count.columns = [c[1] for c in error_count.columns]

    if config.args.alpha is None:
        C, pi, ranks = get_ranks(total_win_raito, use_inf_alpha=True, inf_alpha_eps=0.01)
    else:
        C, pi, ranks = get_ranks(total_win_raito, alpha=config.args.alpha)
    draw_response_graph(config, names, C, pi, ranks, total_win_raito)

    # 
    # Elo 계산
    # 
    update_elo_rating(config)

    #
    # README.rst 파일 업데이트
    #
    write_readme(config, round_start, round_end)


def get_ranks(win_ratio, alpha=10, use_inf_alpha=False, inf_alpha_eps=0.01):
    # win_ratio.columns = [c[1] for c in win_ratio.columns]
    M = win_ratio.values
    names = win_ratio.columns

    # single population, alpha = /inf 경우
 
    #
    #  M --> C: compute transition matrix
    # 
 
    # transition matrix
    C = np.zeros_like(M, dtype=np.float32)
 
    n_strategies = M.shape[0]
    eta = 1 / (n_strategies - 1)
 
    for s in range(n_strategies):  # 현재 전략
        for r in range(n_strategies):  # 다음 전략
            if s != r:  # Compute off-diagonal fixation probabilities
                payoff_rs = M[r, s]
                payoff_sr = M[s, r]
                if use_inf_alpha:
                    if np.isclose(payoff_rs, payoff_sr, atol=1e-14):
                        C[s, r] = eta * 0.5
                    elif payoff_rs > payoff_sr:
                        # r이 s보다 payoff가 높으므로, s -> r 확률 높음
                        C[s, r] = eta * (1 - inf_alpha_eps)
                    else:
                        # s -> r 확률 낮음
                        C[s, r] = eta * inf_alpha_eps
                else:
                    u = alpha * (payoff_rs - payoff_sr)
                    C[s, r] = (1-np.exp(-u)) / (1-np.exp(-n_strategies * u))
        C[s, s] = 1 - sum(C[s, :])  # Diagonals
 
    #
    #  c --> pi
    #
    eigenvals, eigenvecs, _ = la.eig(C, left=True, right=True)
    mask = abs(eigenvals - 1.) < 1e-6
    eigenvecs = eigenvecs[:, mask]
    num_stationary_eigenvecs = np.shape(eigenvecs)[1]
    if num_stationary_eigenvecs != 1:
        raise ValueError(
            f'Expected 1 stationary distribution, but found {num_stationary_eigenvecs}'
        )
    eigenvecs *= 1. / sum(eigenvecs)
    pi = eigenvecs.real.flatten()
 
    # ranks
    ranks = dict()
    for s in range(n_strategies):
        k = f'{pi[s]:.5f}'
        ranks.setdefault(k, list())
        ranks[k].append(names[s])

    ranks = sorted([(float(score), ranks[score]) for score in ranks], reverse=True)
    return C, pi, ranks
 

def draw_response_graph(config, names, C, pi, ranks, win_ratio): 

    # print ranks
    for rank, (score, strategy) in enumerate(sorted(ranks, reverse=True)):
        print(f'rank: {rank+1}, {", ".join(strategy)}, score: {score}')

    df_ranks = pd.DataFrame([(', '.join(ns), score) for score, ns in ranks])
    df_ranks.columns = ['names', 'score']
    df_ranks.index.name = 'rank'
    df_ranks.index = range(1, df_ranks.index.stop + 1)
    print(df_ranks)
    # df_ranks.to_excel(config.out_dir / 'rank.xlsx', sheet_name='Sheet1')
    df_ranks.to_csv(config.log_dir / 'rank.csv')
 
    edges = list()
    edge_ws = list()
    for s, name_s in enumerate(names):
        cnt = 0
        for r, name_r in enumerate(names):
            if s != r:  # s == r 인 경우 생략
                if C[s, r] >= 1 / len(names):  # 전이확률이 평균보다 작으면 생략
                    name_s_ = f'{name_s}\n{pi[s]:.3f}'
                    name_r_ = f'{name_r}\n{pi[r]:.3f}'
                    edges.append((name_s_, name_r_, C[s, r]))
                    edge_ws.append(C[s, r])
                    cnt += 1

    DG = nx.DiGraph()
    DG.add_weighted_edges_from(edges)
 
    edge_ws = np.array(edge_ws)
    edge_ws = (edge_ws - edge_ws.min() + 1e-6) / (edge_ws.max() - edge_ws.min() + 1e-6)

    options = dict(
        node_color=pi[[names.index(node.split('\n')[0]) for node in DG.nodes]],
        cmap='summer',
        # vmax=1.0,
        # vmin=0.0,
        node_size=12000,
        arrowsize=25,
        edge_color=edge_ws,
        # edge_cmap=plt.cm.Greys,
        with_labels=True, 
        font_family='NanumMyeongjo',
    )
    pos = nx.shell_layout(DG)

    fig, ax = plt.subplots(figsize=(13, 13))
    nx.draw(DG, pos=pos, **options)
    plt.savefig(config.fig_dir / 'C.png')
    plt.clf()


def update_elo_rating(config):

    def k_factor(elo_rating):
        """
        player의 k factor 계산
        """
        if elo_rating < 1100:
            return 25
        elif elo_rating < 2400:
            return 15
        else:
            return 10
    
    df = pd.read_csv(config.csv_file, names=config.csv_columns)

    # 현재 봇 목록에 없으면 제외
    xs = list(config.teams.keys())
    df = df[df['p1'].apply(lambda x: x in xs) | df['p2'].apply(lambda x: x in xs)]

    names = list(sorted(config.teams.keys()))
    elo_ratings = {name: [config.init_elo_rating] for name in names}

    for i in df.index:
        row = df.loc[i]
        if row['p1'] != row['p2']:
            old_p1_elo = elo_ratings[row['p1']][-1]
            old_p2_elo = elo_ratings[row['p2']][-1]

            p1_exp_score = 1 / (1 + 10 ** ((old_p2_elo - old_p1_elo) / 400))
            new_p1_elo = old_p1_elo + k_factor(old_p1_elo) * (row['p1_score'] - p1_exp_score)
            elo_ratings[row['p1']].append(new_p1_elo)

            p2_exp_score = 1 / (1 + 10 ** ((old_p1_elo - old_p2_elo) / 400))
            new_p2_elo = old_p2_elo + k_factor(old_p2_elo) * (row['p2_score'] - p2_exp_score)
            elo_ratings[row['p2']].append(new_p2_elo)
            
    max_x = max(len(vs) for vs in elo_ratings.values())
    fig, ax = plt.subplots(figsize=FIG_SIZE)
    
    for name in names:
        xs = np.arange(max_x - len(elo_ratings[name]), max_x)
        ax.plot(xs, elo_ratings[name], label=name)
        ax.text(max_x + 10, elo_ratings[name][-1], name)
    ax.set_xlim(0, max_x + 20)
    ax.legend(loc=2)
    # plt.subplots_adjust(right=0.75)
    plt.savefig(config.fig_dir / 'elo.png')
    plt.clf()


def write_readme(config, round_start, round_end):

    def csv_to_table(filename, title):
        buff = f"""
.. list-table:: {title}
   :header-rows: 1

"""
        with (config.out_dir / filename).open() as f:
            reader = csv.reader(f)
            for row in reader:
                for i, item in enumerate(row):
                    if i == 0:
                        buff += f'   * - {item}\n'
                    else:
                        if item.replace('.', '', 1).isdigit():
                            # float 확인
                            buff += f'     - {float(item):.3f}\n'
                        else:
                            buff += f'     - {item}\n'
        return buff

    t_current = datetime.now()
    summary_table = csv_to_table('log/summary.csv', 'Summary')
    rank_table = csv_to_table('log/rank.csv', 'alpha-Rank')

    # README 파일 생성
    with (config.out_dir / 'README.rst').open('wt') as f:
        content = f"""
NCF2020 결과
===============

.. list-table:: 진행현황
   :header-rows: 1
 
   * - 시작시간
     - 현재시간
     - 경과시간
     - 게임 번호
   * - {config.t_start.isoformat()}
     - {t_current.isoformat()}
     - {t_current - config.t_start}
     - {round_start}부터 {round_end}까지

**결과 요약**

{summary_table}

- 게임번호 {round_start}부터 {round_end}까지 결과(최근 게임 결과)만 사용함
- win ratio: 전체 승률
- #wins (pn): 플레이어 n으로 승리한 횟수
- #games (pn): 플레이어 n으로 플레이한 횟수
- win ratio (pn): 플레이어 n으로 플레이했을 때 승률
- #errors: 참가한 게임에서 error가 발생한 횟수 (상대 플레이어가 에러를 발생시켰을 수 있음)
- player_time: 평균 게임 플레이 시간


**Elo rating**

.. figure:: fig/elo.png
   :figwidth: 200

- 현재까지 진행한 모든 게임 결과를 사용함
- https://en.wikipedia.org/wiki/Chess_rating_system
- K: 10~25, C=400


기타 분석자료
-----------------

- 게임번호 {round_start}부터 {round_end}까지 결과(최근 게임 결과)만 사용함

**플레이어 1으로 플레이 했을 때 승률**

- 플레이어 1 (row)과 플레이어 2 (column)이 플래이 했을 때, 플레이어 1의 승률 (승리 횟수 / 게임 횟수 = 승률)
- 승률이 높을 수록 밝음

.. figure:: fig/score_as_player1.png
   :figwidth: 200

**에러율**

- 플레이어 1 (row)과 플레이어 2 (column)이 플래이 했을 때, 에러 발생 확률 (에러 발생 횟수 / 게임 횟수 = 에러율)
- 게임 도중에 에러가 발생해서, 정상적으로 게임을 플레이하지 못할 경우
- 플레이어 1과 플레이어 2 중에 누가 에러를 발생했는지는 이 그림에서 확인 불가능하므로, 자세한 원인을 알기 위해서는 로그 파일을 분석해야 함
- AI 때문에 에러가 발생한 경우 에러를 발생시킨 AI의 패배로 게임이 종료

.. figure:: fig/error.png
   :figwidth: 200

**게임 플레이 시간**

- 플레이어 1 (row)과 플레이어 2 (column)이 플래이 했을 때, 평균 플레이 시간

.. figure:: fig/play_time.png
   :figwidth: 200

**AI 상성 네트워크**

- 여러 AI 사이의 상성을 나타내는 그래프
- AI a가 b에게 승률이 높다면 a <- b로 표시함
- https://arxiv.org/abs/1903.01373

.. figure:: fig/C.png
   :figwidth: 200

{rank_table}

"""
        f.write(content)

    # RST -> HTML
    # pandoc README.rst -f rst -t html -s -o README.html
    os.system(f"pandoc {config.out_dir}/README.rst -f rst -t html -s -o {config.out_dir}/README.html")


if __name__ == '__main__':

    export_results(config)
