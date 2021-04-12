
__author__ = '박현수 (hspark8312@ncsoft.com), NCSOFT Game AI Lab'

# python -m bots.nc_example_v5.bot --server=172.20.41.105
# kill -9 $(ps ax | grep SC2_x64 | fgrep -v grep | awk '{ print $1 }')
# kill -9 $(ps ax | grep bots.nc_example_v5.bot | fgrep -v grep | awk '{ print $1 }')
# ps aux

import argparse
import pickle
import os
os.environ['MKL_DEBUG_CPU_TYPE'] = '5'
os.environ['OMP_NUM_THREADS'] = '1'
os.environ['MKL_NUM_THREADS'] = '1'
import time
from pathlib import Path
from collections import namedtuple
from collections import deque

import nest_asyncio
nest_asyncio.apply()
import numpy as np
import psutil
import sc2
import plotille
import torch
import torch.multiprocessing as mp
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim
import tqdm
from IPython import embed
from sc2.data import Result
from sc2 import Race
from sc2.player import Bot as _Bot
from sc2.ids.ability_id import AbilityId
from sc2.ids.buff_id import BuffId
from sc2.ids.unit_typeid import UnitTypeId
from sc2.position import Point2
from torch.utils.tensorboard import SummaryWriter
from termcolor import cprint, colored

from .bot import Model
from .consts import CommandType
from .consts import ArmyStrategy, EconomyStrategy, Sample
from .consts import MessageType
from sc2_utils import keyboard, backup_dir, get_memory_usage, get_memory_usage_delta, kill_children_processes
from sc2_utils.ascii_plot import draw_sparkline


def parse_arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument('--attach', type=str)
    parser.add_argument('--frontend_port', type=int, default=5559)
    parser.add_argument('--backend_port', type=int, default=5600)
    parser.add_argument('--n_actors', type=int, default=1)
    parser.add_argument('--game_map', type=str, default='NCF-2020-v4')
    parser.add_argument('--step_interval', type=float, default=5.0)
    parser.add_argument('--n_envs', type=int, default=8)
    parser.add_argument('--horizon', type=int, default=64)
    parser.add_argument('--mini_batch_size', type=int, default=32)
    parser.add_argument('--game_timeout', type=float, default=10 * 60)
    parser.add_argument('--timeout', type=float, default=600)
    parser.add_argument('--lam', type=float, default=0.95)
    parser.add_argument('--gamma', type=float, default=0.95)
    parser.add_argument('--clip_range', type=float, default=0.2)
    parser.add_argument('--value_coef', type=float, default=0.5)
    parser.add_argument('--ent_coef', type=float, default=0.01)
    parser.add_argument('--lr', type=float, default=0.0001)
    parser.add_argument('--max_grad', type=float, default=10.0)
    parser.add_argument('--device', choices=['cpu', 'cuda'], default='cpu')
    parser.add_argument('--replay_path', type=str)
    parser.add_argument('--seed', type=int, default=0)
    parser.add_argument('--halt_at_exception', action='store_true')
    args = parser.parse_args()
    return args


class Trajectory:
    __slots__ = [
        'game_id', 'update_time', 
        'state', 'action', 'reward', 'done', 'logp_a', 'value'
    ]

    def __init__(self):
        self.game_id = None
        self.update_time = time.monotonic()
        self.state = list()
        self.action = list()
        self.reward = list()
        self.done = list()
        self.logp_a = list()
        self.value = list()

    def add(self, game_id, state, action, reward, done, logp_a, value):
        if self.game_id is None:
            self.game_id = game_id

        if self.game_id == game_id:
            self.game_id = game_id
            self.update_time = time.monotonic()
            if done:
                self.reward[-1] = reward
                self.done[-1] = done
                self.game_id = None
            else:
                self.state.append(state)
                self.action.append(action)
                self.reward.append(reward)
                self.done.append(done)
                self.logp_a.append(logp_a)
                self.value.append(value)
        else:
            raise RuntimeError

    def get(self, n_steps):
        assert n_steps < len(self.state)
        state, self.state = self.state[:n_steps+1], self.state[n_steps-1:]  # t
        action, self.action = self.action[:n_steps], self.action[n_steps-1:]  # t
        reward, self.reward = self.reward[1: n_steps+1], self.reward[n_steps-1:]  # t-1
        done, self.done = self.done[1: n_steps+1], self.done[n_steps-1:]  # t-1
        logp_a, self.logp_a = self.logp_a[:n_steps], self.logp_a[n_steps-1:]  # t
        value, self.value = self.value[:n_steps+1], self.value[n_steps-1:]  # t
        return state, action, reward, done, logp_a, value

    def __len__(self):
        return len(self.state) - 1


class Trainer:
    def __init__(self, args):
        self.tasks = [self.train_step]
        
        self.args = args
        self.device = args.device
        self.model = Model().to(self.device)
        self.optimizer = optim.Adam(self.model.parameters(), lr=args.lr, amsgrad=True)
        self.writer = SummaryWriter()
        self.scores = deque(maxlen=250)
        self.saved_model_score = -1e10
        self._scores = deque(maxlen=10000)
        self.n_errors = 0

        self.env = Environment(args)
        self.batch_buffer = list()

        self.frames = 0
        self.running = True
        self.debug_mode = False

        backup_dir(
            src=str(Path(__file__).parent), 
            dst=str(Path(self.writer.log_dir) / 'backup.zip')
        )
        cprint('READY', 'green')

    @staticmethod
    def train_step(self, args, env):
        #
        # Rollouts
        #

        rollout_start_time = time.monotonic()
        rollout_frames = 0

        while True:
            self.debug_mode = self.debug_mode ^ keyboard.event('esc')

            # 인공신경망 feed-forward
            cmd, game_id, state, reward, done, info = self.env.state()

            if cmd == CommandType.REQ_TASK:
                task_dict = dict(
                    game_map=args.game_map,
                )
                self.env.set_task(task_dict)
                continue

            elif cmd == CommandType.ERROR:
                error_log_file = Path(self.writer.log_dir) / 'error.log'
                with error_log_file.open('at') as f:
                    f.write(info['error'])
                self.n_errors += 1
                self.writer.add_scalar(
                        'info/n_errors', self.n_errors, self.frames)
                self.env.finish()
                continue

            elif cmd == CommandType.SCORE:
                value, action, logp_a = None, None, None
                self.env.finish()

            else:
                with torch.no_grad():
                    value, logp = self.model(torch.FloatTensor(state).to(self.device))
                    value = value.item()
                    action = logp.exp().multinomial(num_samples=1).item()
                    logp_a = logp[:, action].item()
                self.env.act(value, action)
                self.frames += 1

            if done:
                # 승패 기록
                self.scores.append(reward)
                self._scores.append((self.frames, np.mean(self.scores)))
                if len(self.scores) >= self.scores.maxlen:
                    mean_score = np.mean(self.scores)
                    self.writer.add_scalar('perf/score', mean_score, self.frames)
                    self.writer.add_scalar('perf/win_ratio', (mean_score + 1.) / 2., self.frames)

            # 데이터 저장
            # 현재 데이터를 저장할 수 있는 trajectory 검색
            idx = -1
            for i, trajectory in enumerate(self.batch_buffer):
                # 현재 게임이 저장되고 있던 trajectory 검색
                if trajectory.game_id == game_id:  
                    idx = i
                    break

            if idx < 0:
                for i, trajectory in enumerate(self.batch_buffer):
                    # 이전 게임이 종료되었지만, 길이가 짧은 trajectory
                    if trajectory.game_id is None and len(trajectory) <= args.horizon:  
                        idx = i
                        break

            if idx < 0:
                # 현재 게임을 저장할 만한 trajectory가 없으면 새로 생성
                self.batch_buffer.append(Trajectory())  

            self.batch_buffer[idx].add(game_id, state, action, reward, done, logp_a, value)
            rollout_frames += 1

            masks = [len(troj) > args.horizon for troj in self.batch_buffer]
            # print([(len(troj), troj.done[-1]) for troj in self.batch_buffer])
            values = [min(len(troj), args.horizon) for troj in self.batch_buffer]
            values += [0] * (args.n_envs - len(values))
            sparkline = draw_sparkline(values, max_value=args.horizon, min_value=0)
            fps = rollout_frames / (time.monotonic() - rollout_start_time + 1e-6)
            text = [
                f'buffer: {sparkline}',
                f'ready {sum(masks) / args.n_envs:.2f}%',
                f'fps: {fps:.1f}',
            ]
            if self.debug_mode:
                text.append(colored('DEBUG', 'yellow'))
            text = ','.join(text)
            text += ' ' * (os.get_terminal_size().columns - 2 - len(text)) + '\r'
            print(text, end='')

            if sum(masks) >= args.n_envs:
                # 배치를 생성하기 충분한 데이터 수집 완료
                break

        #
        # Optimize
        #         
        state_buff = list()
        action_buff = list()
        reward_buff = list()
        done_buff = list()
        old_logp_buff = list()
        old_value_buff = list()
        for i, j in enumerate(np.argwhere(masks).reshape(-1)):
            s, a, r, d, lp, v = self.batch_buffer[j].get(args.horizon)
            state_buff.append(s)
            action_buff.append(a)
            reward_buff.append(r)
            done_buff.append(d)
            old_logp_buff.append(lp)
            old_value_buff.append(v)

        states = np.array(state_buff).reshape(args.n_envs, args.horizon+1, -1).transpose(1, 0, 2).astype(np.float32)
        actions = np.array(action_buff).transpose(1, 0).astype(np.int64)
        rewards = np.array(reward_buff).transpose(1, 0).astype(np.float32)
        dones = np.array(done_buff).transpose(1, 0).astype(np.float32)
        old_logps = np.array(old_logp_buff).transpose(1, 0).astype(np.float32)
        old_values = np.array(old_value_buff).transpose(1, 0).astype(np.float32)

        gamma = args.gamma * (1 - dones)
        deltas = rewards + gamma * old_values[1:] - old_values[:-1]
        adv = np.zeros((args.horizon + 1, args.n_envs), dtype=np.float32)
        returns = np.zeros((args.horizon + 1, args.n_envs), dtype=np.float32)
        returns[-1] = old_values[-1]
        for t in reversed(range(args.horizon)):
            adv[t] = adv[t + 1] * gamma[t] * args.lam + deltas[t]
            returns[t] = returns[t + 1] * gamma[t] + rewards[t] 
        adv, returns = adv[:-1], returns[:-1]
        adv = (adv - adv.mean()) / (adv.std() + 1e-8)

        state_batch = states[:-1].reshape(args.horizon * args.n_envs, -1)
        action_batch = actions.reshape(-1)
        reward_batch = rewards.reshape(-1)
        old_logp_batch = old_logps.reshape(-1)
        old_value_batch = old_values[:-1].reshape(-1)
        return_batch = returns.reshape(-1)
        adv_batch = adv.reshape(-1)

        # fit
        index = np.arange(args.horizon * args.n_envs)
        np.random.shuffle(index)
        index = index.reshape(-1, args.mini_batch_size)

        optimize_start_time = time.monotonic()
        fit_info = dict()
        for idx in tqdm.tqdm(index, 'fit'):
            states = torch.from_numpy(state_batch[idx]).to(self.device)
            actions = torch.from_numpy(action_batch[idx]).to(torch.int64).to(self.device)
            old_values = torch.from_numpy(old_value_batch[idx]).to(self.device)
            old_logps = torch.from_numpy(old_logp_batch[idx]).to(self.device)
            returns = torch.from_numpy(return_batch[idx]).to(self.device)
            adv = torch.from_numpy(adv_batch[idx]).to(self.device)

            values, logp = self.model(states)
            logp_a = logp[torch.arange(actions.shape[0]), actions]

            # value loss
            value_loss = F.smooth_l1_loss(values, returns.view(values.shape))
            # policy loss
            ratios = torch.exp(logp_a - old_logps)
            policy_loss1 = -adv * ratios
            clip_range = args.clip_range
            policy_loss2 = -adv * torch.clamp(ratios, min=1.0 - clip_range, max=1.0 + clip_range)
            policy_loss = torch.mean(torch.max(policy_loss1, policy_loss2))
            entropy = -(logp.exp() * logp).sum().item()
            loss = value_loss * args.value_coef + policy_loss - args.ent_coef * entropy

            # optimize
            self.optimizer.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(self.model.parameters(), args.max_grad)
            self.optimizer.step()

            # debug info
            approx_kl = 0.5 * torch.mean((old_logps - logp_a) ** 2)
            clipped = ratios.gt(1 + clip_range) | ratios.lt(1 - clip_range)
            clip_frac = torch.as_tensor(clipped, dtype=torch.float32).mean()
            fit_info['v_loss'] = fit_info.get('v_loss', 0.) + value_loss.item() / index.shape[0]
            fit_info['p_loss'] = fit_info.get('p_loss', 0.) + policy_loss.item() / index.shape[0]
            fit_info['entropy'] = fit_info.get('entropy', 0.) + entropy / index.shape[0]
            fit_info['approx_kl'] = fit_info.get('approx_kl', 0.) + approx_kl.item() / index.shape[0]
            fit_info['clip_frac'] = fit_info.get('clip_frac', 0.) + clip_frac.item() / index.shape[0]

        optimize_etime = time.monotonic() - optimize_start_time
        
        for tag in fit_info:
            self.writer.add_scalar(f'loss/{tag}', fit_info[tag], self.frames)
        self.writer.add_scalar('perf/reward', reward_batch.mean(), self.frames)
        self.writer.add_scalar('perf/return', return_batch.mean(), self.frames)
        self.writer.add_scalar('info/fps', fps, self.frames)
        self.writer.add_scalar('info/optimize_etime', optimize_etime, self.frames)
        memory_usage_dict = dict(psutil.virtual_memory()._asdict())
        self.writer.add_scalar(f'info/memory_used_percent', memory_usage_dict['percent'])
        self.writer.add_scalar(f'info/memory_used_gb', get_memory_usage())
        self.writer.add_scalar(f'info/memory_usage_delta', get_memory_usage_delta())
        print(plotille.scatter(*zip(*self._scores), height=30, X_label='Frames', Y_label='Score', y_min=-1.0, y_max=1.0))
        text = [
            f'step: {self.frames}',
            f'score: {np.mean(self.scores):.3f}',
            f'n_erros: {self.n_errors}',
        ]
        cprint(','.join(text))

        # 너무 오래된 trajectory batch_buffers에서 제거
        self.batch_buffer = [
            traj for traj in self.batch_buffer 
            if time.monotonic() - traj.update_time < args.timeout
        ]

        # trajectory 길이가 긴 순서대로 정렬
        self.batch_buffer = sorted(self.batch_buffer, key=lambda t: -len(t))

        # 모델 저장
        if np.mean(self.scores) > self.saved_model_score:
            model_path = Path(__file__).parent / 'model.pt'
            torch.save(self.model.state_dict(), model_path)
            self.saved_model_score = np.mean(self.scores)

    def stop(self):
        self.running = False

    def run(self):
        while self.running:
            try:
                if self.debug_mode is True:
                    self.debug_mode = False
                    raise KeyboardInterrupt

                for task in self.tasks:
                    task(self, self.args, self.env)

            except (Exception, KeyboardInterrupt) as exc:
                if isinstance(exc, KeyboardInterrupt):
                    cprint(f'[DEBUG MODE] 시작', 'yellow')
                else:
                    import traceback
                    traceback.print_exc()

                embed()

                cprint(f'[DEBUG MODE] 종료', 'yellow')
                for i, task in enumerate(self.tasks):
                    new_task = locals().get(task.__name__)
                    if new_task is not None and new_task is not task:
                        cprint(f'[FUNC. UPDATE] {new_task}', 'yellow')
                        self.tasks[i] = new_task


if __name__ == '__main__':

    mp.freeze_support()  # for Windows support

    from .envs import Actor, Environment

    args = parse_arguments()

    # TODO: numpy seed
    # TODO: torch seed

    if args.attach is None:
        # os.system("kill -9 $(ps ax | grep SC2_x64 | fgrep -v grep | awk '{ print $1 }')")
        Trainer(args).run()
    else:
        if args.n_actors <= 1:
            Actor(args).run(0)
        else:
            actors = [Actor(args) for _ in range(args.n_actors)]
            ps = [
                mp.Process(target=actor.run, args=(i,), daemon=False) 
                for i, actor in enumerate(actors)
            ]
            [p.start() for p in ps]
            [p.join() for p in ps]
        kill_children_processes(including_parent=False)