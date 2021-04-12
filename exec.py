#!/usr/bin/env python

import argparse
import os
import platform
from collections import namedtuple
from sc2_utils import get_ip


Host = namedtuple('Host', 'address, cpu_capacity, gpu_capacity')

Trainer = Host(get_ip('8.8.8.8'), cpu_capacity=0, gpu_capacity=0)
hosts = [    
    Host('192.168.0.102', cpu_capacity=16, gpu_capacity=0),
    # Host('192.168.0.102', cpu_capacity=1, gpu_capacity=0),
    # Host('192.168.0.102', cpu_capacity=1, gpu_capacity=0),
    # Host('ubuntu@127.0.0.1', '~/.ssh/sc_2_key.pem', 1),
]

# (클라이언트에서) 키 생성
# ssh-keygen -t rsa
# (클라이언트에서 서버에) 키 복사
# ssh-copy-id -i ${HOME}/.ssh/id_rsa.pub {server-id}@{server-ip}


def sh(args, hosts, cmd=''):
    addrs = ' '.join([h.address for h in hosts])
    os.system(f'''xpanes -c 'ssh {{}} -t "{cmd}"' {addrs} ''')


def htop(args, hosts):
    sh(args, hosts, cmd='htop')


def sync(args, hots):
    from pathlib import Path
    src_dir = Path.cwd()
    addrs = set([h.address for h in hosts])
    dst_dirs = [f'{addr}:~/' for addr in addrs]

    cmds = list()
    for dst_dir in dst_dirs:
        cmds.append(f'"rsync -rv {src_dir} {dst_dir}"')
    os.system(f"xpanes -e {' '.join(cmds)}")


def copy_sc2(args, hosts):
    src_dir = '~/SC2.4.10.zip'
    addrs = set([h.address for h in hosts])
    dst_dirs = [f'{addr}:~/' for addr in addrs]
    
    cmds = list()
    for dst_dir in dst_dirs:
        cmds.append(f'"rsync -rv {src_dir} {dst_dir}"')
    os.system(f"xpanes -e {' '.join(cmds)}")


def run_actors(args, hosts):
    addr = Trainer.address
    cmds = []
    cmds.append(f'source ~/anaconda3/bin/activate sc2')        
    cmds.append(f'cd ~/NCF2020')   
    cmds.append(f'python -m bots.{args.bot}.train --attach={addr} --n_actors=2')
    sh(args, hosts, cmd='; '.join(cmds)) 


def train(args, hosts):
    import math
    from pathlib import Path

    cmds = list()
    # tmux 세션 시작
    cmds.append('''tmux new -s sc2 -d''')
    # Trainer 시작
    cmds.append('''tmux send -t sc2 "source ~/anaconda3/bin/activate sc2" ENTER''')
    cmds.append(f'''tmux send -t sc2 "cd {Path.cwd()}" ENTER''')
    cmds.append(f'''tmux send -t sc2 "python -m bots.{args.bot}.train" ENTER''')

    max_panes = 6
    n_actor_windows = math.ceil(len(hosts) / max_panes)
    cmds.append(f'''tmux set -g pane-border-status top''')
    cmds.append('''tmux set -g pane-border-format "#{pane_title}"''')

    for i in range(n_actor_windows):
        current_hosts = hosts[i * max_panes: (i+1) * max_panes]
        # tmux, actors 윈도우 생성
        cmds.append(f'''tmux new-window -t sc2 -n actors{i}''')

        for j, host in enumerate(current_hosts):
            # actors 윈도우에서 actor 실행
            remote_cmd = '; '.join([
                'source ~/anaconda3/bin/activate sc2',
                'cd ~/NCF2020',
                f'python -m bots.{args.bot}.train '
                    f'--attach={Trainer.address} '
                    f'--n_actors={host.cpu_capacity}',
            ])
            cmd = f'''ssh {host.address} -t "{remote_cmd}"'''
            cmds.append(f'''tmux send -t sc2 '{cmd}' ENTER''')
            cmds.append(f'''tmux select-pane -T "{i*max_panes + j}: {host.address}"''')
            
            if j < len(current_hosts) - 1:
                # 필요하다면 actors 윈도우에 pane 추가
                cmds.append(f'''tmux split-window -t actors{i}''')
                cmds.append(f'''tmux select-layout -t actors{i} tiled''')
            
        # actors 윈도우 layout을 tiled로 재정렬
        # 다른 가능한 layout: even-vertical, even-horizontal
        cmds.append(f'''tmux select-layout -t actors{i} tiled''')

        # actors 윈도우의 모든 pane을 동기화
        # cmds.append(f'''tmux set-window-option -t actors{i} synchronize-panes''')

    # sc2 세션에 접속
    cmds.append('''tmux select-window -t:0''')
    cmds.append('''tmux attach -t sc2''')

    for i, cmd in enumerate(cmds):
        print(f'[{i}/{len(cmds)}] {cmd}')
        os.system(cmd)


def stop_train(args, hosts):
    os.system('''tmux kill-session -t sc2''')


def main(args):    
    # hosts = ' '.join(HOSTS)    
    tasks = args.tasks

    for task in tasks:
        func = globals().get(task)
        if func is None:
            print(f'[ERROR] {task} 함수 없음')
        elif not hasattr(func, '__call__'):
            print(f'[ERROR] {task}는 함수가 아님')
        else:
            print(f'[EXEC] {task}')
            func(args, hosts)    

 
if __name__ == '__main__':    
    parser = argparse.ArgumentParser()    
    parser.add_argument('tasks', default=[], nargs='+')    
    parser.add_argument('--bot', type=str) 
    args = parser.parse_args()    
    main(args)
