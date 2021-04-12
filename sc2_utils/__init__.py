

__author__ = '박현수 (hspark8312@ncsoft.com), NCSOFT Game AI Lab'

from concurrent.futures import ThreadPoolExecutor
from functools import wraps

import numpy as np

from .singleton import Singleton


def kill_starcraft_ii_processes():
    """
    실행되고 있는 모든 스타크래프트 게임 종료
    """
    import platform
    import os

    if platform.platform().lower().startswith('windows'):
        os.system('taskkill /f /im SC2_x64.exe')
    else:
        os.system('pkill -f SC2_x64')


def parse_race(race):
    """
    종족을 나타내는 문자열을 
    python-sc2 Race enum 타입으로 변경
    """
    from sc2 import Race

    if race.lower() == 'terran':
        return Race.Terran
    elif race.lower() == 'protoss':
        return Race.Protoss
    elif race.lower() == 'zerg':
        return Race.Zerg
    else:
        return Race.Random

        
def parse_bool(value):
    if value in ('1', 'true', 'True'):
        return True
    else:
        return False


def kill_children_processes(pid=None, including_parent=False):
    """
    부모 프로세스(pid로 지정)의 자식프로세스를 강제로 종료함

    :param pid (int): 부모 프로세스의 pid
    :param include_parent (bool): 부모도 같이 종료할 것인지 지정
    """
    import os
    import psutil

    pid = os.getpid() if pid is None else pid

    parent = psutil.Process(pid)
    for child in parent.children(recursive=True):
        print("child", child.pid, child)
        child.kill()

    if including_parent:
        parent.kill()


def get_current_time_str():
    "현재 시간을 문자열로 반환"
    import datetime
    time_str = datetime.datetime.now().isoformat()
    return time_str.split('.')[0].replace(':', '-').replace('T', '-')


def count_open_fds():
    '''
    현재 프로세스에서 열려있는 파일의 개수를 반환

    .. warning::

       리눅스에서만 작동함
    '''
    import subprocess
    import os

    pid = os.getpid()
    procs = subprocess.check_output(["lsof", '-w', '-Ff', "-p", str(pid)])
    procs = procs.decode('utf-8')
    nprocs = sum([
        1 for s in procs.split('\n') if s and s[0] == 'f' and s[1:].isdigit()
    ])
    return nprocs


def get_memory_usage():
    """
    현재 프로세스에서 사용하고 있는 메모리를 GB 단위로 반환
    """
    import os
    import psutil

    process = psutil.Process(os.getpid())
    return process.memory_info().rss / 1000000000  # GB


memory_usage_buff = None


def get_memory_usage_delta():
    """
    현재 프로세스에서 사용하고 있는 메모리의 증감을 byte 단위로 반환
    """
    global memory_usage_buff

    if memory_usage_buff is None:
        memory_usage_buff = get_memory_usage()
        return 0.
    else:
        current_memory_usage = get_memory_usage()
        delta = current_memory_usage - memory_usage_buff
        memory_usage_buff = current_memory_usage
        return delta


def cuda_available():
    import torch
    return torch.cuda.is_available()


def get_ip(ip, port=80):
    """
    현재 PC의 IP를 반환

    다른 PC에 접속해서, IP를 알아내기 때문에,
    반드시 접속할 PC의 IP를 알고 있어야 한다.
    DNS (8.8.8.8)나, Gateway 주소를 사용해도 된다.

    .. warning::

        localhost (127.0.0.1) 을 사용하면 127.0.0.1을 반환한다.
    """
    import socket

    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect((ip, port))
    ip = s.getsockname()[0]
    s.close()
    return ip


def backup_dir(src: str, dst: str):
    """
    src 폴더를 압축해서 dst경로에 저장함

    .git, __pycache__, .vscode, __backup__ 폴더 제외
    """
    import os
    import zipfile
    from pathlib import Path
    import tqdm

    # 제외할 폴더명
    excludes = {'.git', '__pycache__', '.vscode', '__backup__'}

    pathes = []
    for root, _, files in os.walk(src):
        for f in files:
            path = Path(os.path.join(root, f))
            if not excludes.intersection(path.parts):
                pathes.append(path)

    with zipfile.ZipFile(dst, 'w') as zf:
        for path in tqdm.tqdm(pathes, desc='Backup'):
            zf.write(path)


def import_component(path: str):
    """
    class 혹은 function의 경로를 문자열로 입력받아, import 함
    impot {path} 와 효과가 동일함 (상대경로 임포트 안됨)
    """
    import importlib

    module, name = path.rsplit('.', 1)
    component = getattr(importlib.import_module(module), name)
    return component


#
# Named collections
#

class NamedDict(dict):
     def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.__dict__ = self

class NamedArray(np.ndarray):
    def __new__(cls, *args, **kwargs):
        """

        a = NamedArray([[1, 2], [3, 4]], names='a,b')
        """
        names = kwargs.pop('names')
        array = np.array(*args, **kwargs)
        assert array.ndim > 1

        array = array.view(cls)
        array.columns = list()
        array.__name_dict = dict()
        for i, name in enumerate(names.split(',')):
            array.columns.append(name)
            array.__name_dict[name] = i

        array.columns = tuple(array.columns)
        assert array.shape[1] == len(array.columns)
        return array

    def __getattr__(self, name):
        try:
            data = self[:, self.__name_dict[name]]
            return data
        except KeyError:
            raise AttributeError()


class NonBlockExecutor(ThreadPoolExecutor, metaclass=Singleton):
    pass


def non_block_func(func):
    # 전달 받은 함수를 별도 쓰레드에서 실행해서, 
    # 메인 쓰레드가 멈추지 않고 계속 실행하도록 함
    # 로깅 함수처럼 결과를 반환받지 않아도 문제없고, 
    # 조금 늦게 실행되도 문제가 없는 함수에 사용

    @wraps(func)
    def wrapped_func(*args, **kwargs):
        executor = NonBlockExecutor(max_workers=4)
        executor.submit(func, *args, **kwargs)

    return wrapped_func