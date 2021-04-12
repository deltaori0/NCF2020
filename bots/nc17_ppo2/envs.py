#
#  비동기 Environ와 Actor
#

import asyncio
import socket
import time
import platform
import pickle
import multiprocessing as mp

import sc2
import zmq
from sc2 import Race
from sc2.client import Client
from sc2.main import _play_game, _setup_host_game
from sc2.player import Bot as _Bot
from sc2.portconfig import Portconfig
from sc2.protocol import ConnectionAlreadyClosed, ProtocolError
from sc2.sc2process import SC2Process
from termcolor import cprint
import numpy as np
from IPython import embed

from ..nc3_simple3.bot import Bot as OppBot
from .bot import Bot as MyBot
from .consts import CommandType
from sc2_utils import kill_children_processes


def device_func(context, frontend_addr, backend_addr):
    # ZMQ queue device
    # https://learning-0mq-with-pyzmq.readthedocs.io/en/latest/pyzmq/devices/queue.html
    try:
        if context is None:
            context = zmq.Context(1)

        frontend = context.socket(zmq.ROUTER)
        frontend.bind(frontend_addr)
        backend = context.socket(zmq.DEALER)
        backend.bind(backend_addr)
        zmq.device(zmq.QUEUE, frontend, backend)
    except Exception as exc:
        print(exc)
        print("bringing down zmq device")
    finally:
        pass
        frontend.close()
        backend.close()
        context.term()


class Environment:
    def __init__(self, args):
        self.args = args
        self.context = zmq.Context()
        self.sock = self.context.socket(zmq.REP)

        if platform.system() == 'Windows':
            # Windows에서는 Process기반 queue device 실행
            # 다른 프로토콜 사용 불가능
            from zmq.devices import ProcessDevice
            device = ProcessDevice(zmq.QUEUE, zmq.ROUTER, zmq.DEALER)
            device.bind_in(f"tcp://*:{args.frontend_port}")
            device.bind_out(f"tcp://*:{args.backend_port}")
            device.setsockopt_in(zmq.IDENTITY, 'ROUTER'.encode())
            device.setsockopt_out(zmq.IDENTITY, 'DEALER'.encode())
            device.start()
            self.sock.connect("tcp://localhost:{}".format(args.backend_port))
        else:
            # Linux에서는 backend protocol을 tcp보다 빠른 
            # inproc (inter-process)를 사용하고,
            # thread 기반 queue device를 실행
            import threading
            _device = threading.Thread(
                target=device_func, 
                args=(
                    self.context,
                    f"tcp://*:{args.frontend_port}",
                    f"inproc://backend"
                ), 
            )
            _device.start()
            self.sock.connect(f"inproc://backend")

    def state(self):
        # actor 중 하나 --> queue 를 거쳐 데이터를 전달 받음
        # Trainer에서 처리 후 결과를 act, finish, set_task 중 하나를 통해 반환
        data = self.sock.recv_multipart()
        cmd, msg = data[0], data[1:]

        if cmd == CommandType.STATE:  # actor에서 게임 상태 전달 --> act
            game_id = pickle.loads(msg[0])
            shape = pickle.loads(msg[1])
            state = np.frombuffer(msg[2], dtype=np.float32).reshape(shape)
            return cmd, game_id, state, 0.0, False, dict()

        elif cmd == CommandType.SCORE:  # actor에서 게임 점수 전달 --> finish
            game_id = pickle.loads(msg[0])
            score = pickle.loads(msg[1])
            return cmd, game_id, None, score, True, dict()

        elif cmd == CommandType.REQ_TASK:  # actor에서 게임 세팅 요청 --> set_task
            return cmd, None, None, None, None, dict()

        elif cmd == CommandType.ERROR:   # actor에서 에러 메시지 전달 --> finish
            error_msg = pickle.loads(msg[0])
            return cmd, None, None, None, None, dict(error=error_msg)

    def act(self, value, action):
        data = [pickle.dumps(value), pickle.dumps(action)]
        self.sock.send_multipart(data)

    def finish(self):
        self.sock.send_multipart([CommandType.PING])

    def set_task(self, task_dict):
        self.sock.send_multipart([pickle.dumps(task_dict)])

class Actor:
    def __init__(self, args):
        self.args = args

    def run(self, _id: int, verbose: bool=False, timeout: int=60000, n_games: int=100):
        # hostname = f"{socket.gethostname()}_{time.ctime().replace(' ', '-')}"
        hostname = f"{socket.gethostname()}_{_id}_{time.time()}"
        address = f"tcp://{self.args.attach}:{self.args.frontend_port}"
        context = zmq.Context()
        error_sock = context.socket(zmq.REQ)
        error_sock.connect(address)

        while True:
            try: 
                # alive_event:
                # 게임이 인스턴스 재시작 없이 재시작 할 때마다 set
                # 게임이 정상적으로 재시작하고 있다는 의미
                alive_event = mp.Event()
                # req_kill_event:
                # 게임 프로세스 내부에서 외부에 재시작을 요청할 때 set
                # n_games 만큼 게임을 플레이 한 뒤에 set해서 
                # 게임 프로세스 내부에 문제로 인해 프로세스 종료가 안되더라도, 
                # 외부에서 강제로 종료할 수 있도록 event 전달
                req_kill_event = mp.Event()
                # 
                exc_queue = mp.Queue()

                def play_game(hostname, address, n_games, alive_event, req_kill_event, exc_queue):
                    # n_games:
                    # 게임 인스턴스를 한번 실행해서 연속으로 몇 번이나 게임을 실행할 것인가?
                    # - 너무 작으면, 게임 인스턴스를 자주 재시작해야하기 때문에 속도가 느려짐
                    # - 너무 크면, 예외 상황이 발생할 가능성이 높음               

                    # sync_event:
                    # host (게임 서버)와 join (클라이언트) 사이의 동기를 맞추기 위해 사용
                    # host가 learner에게 전달받은 대로 게임 세팅 설정한 뒤에 set을 해서,
                    # join이 다음 단계를 진행할 수 있도록 함
                    sync_event = asyncio.Event()
                    portconfig = Portconfig()

                    context = zmq.Context()
                    sock = context.socket(zmq.REQ)
                    sock.RCVTIMEO = timeout  # zmq 시간제한 설정ㄴ
                    sock.connect(address)

                    # task_dict & players:
                    # 게임 세팅 관련변수, # host와 join이 동일한 reference를 가지고 있어야 함
                    task_dict = dict(step_interval=self.args.step_interval)
                    players = [None, None]

                    asyncio.get_event_loop().run_until_complete(asyncio.gather(
                        Actor._host_game(
                            hostname,
                            sock,
                            task_dict,
                            players,
                            sync_event,
                            alive_event,
                            req_kill_event,
                            exc_queue,
                            n_games=n_games,
                            realtime=False, 
                            portconfig=portconfig
                        ),
                        Actor._join_game(
                            task_dict,
                            players,
                            sync_event,
                            alive_event,
                            req_kill_event,
                            exc_queue,
                            n_games=n_games,
                            realtime=False, 
                            portconfig=portconfig
                        )
                    ))

                if self.args.game_timeout < 0:
                    # 테스트 용:
                    # play_game 기능 테스트할 때, 최대 게임시간을 음수로 설정하면,
                    # play_game 함수 직접 실행
                    play_game(hostname, address, n_games, alive_event, req_kill_event, exc_queue)

                else:
                    # 일반적인 상황에서는 play_game을 자식 프로세스로 실행
                    # 자식 프로세스 내부에서 종료를 요청(req_kill_event)하거나,
                    # 현재 프로세스에서 제한시간마다 게임이 새로 시작하는지 검사해서,
                    # 게임이 새로 시작하지 않으면(alive_event), 자식프로세스 재시작
                    game_play_proc = mp.Process(
                        target=play_game, 
                        args=(hostname, address, n_games, alive_event, req_kill_event, exc_queue),
                        daemon=False,
                    )
                    game_play_proc.start()
                    
                    running = True
                    checkpoint = time.monotonic()
                    while running:
                        # 게임 프로세스(자식 프로세스)가 정상적으로 작동 중인지 확인
                        if req_kill_event.is_set():
                            # 게임 프로세스에서 종료 요청
                            running = False

                        if time.monotonic() - checkpoint > self.args.game_timeout:
                            if alive_event.is_set():
                                # 제한 시간 이전에 게임 프로세스 내부에서 게임 재시작 확인
                                checkpoint = time.monotonic()
                                alive_event.clear()
                            else:
                                running = False

                        while exc_queue.qsize() > 0:
                            # 자식 프로세스에서 발행한 에러 메시지를 Learner에 전달
                            self.log_exception(hostname, error_sock, exc_queue.get())

                        time.sleep(1)

                    # 게임 프로세스 종료 시도 - sig.TERM                    
                    if game_play_proc.is_alive():
                        for _ in range(3):
                            game_play_proc.terminate()
                            time.sleep(0.5)
                            if not game_play_proc.is_alive():
                                break
                    
                    # 게임 프로세스 종료 시도 - sig.KILL
                    if game_play_proc.is_alive():
                        game_play_proc.kill()
                        game_play_proc.close()    

                    # 게임 프로세스 종료 시도 - psutil
                    if game_play_proc.is_alive():  
                        kill_children_processes(game_play_proc.pid, including_parent=True)                

            except Exception as exc:
                import traceback
                traceback.print_exc()
                self.log_exception(hostname, error_sock, traceback.format_exc())
                if self.args.halt_at_exception:
                    # 테스트용: 예외가 발생했을 때 멈춰 있도록 하기 위한 용도
                    embed()

                try:
                    kill_children_processes(including_parent=False)
                except OSError:
                    # 테스트용: 예외가 발생했을 때 멈춰 있도록 하기 위한 용도
                    # 매우 드물게 OSError가 발생할 수 있는데, 원인은 불확실 함
                    traceback.print_exc()
                    embed()
                    pass

    def log_exception(self, hostname, error_sock, error_msg):
        # 예외를 learner 프로세스로 전달, 
        # learnr 프로세스에서 log 파일에 저장
        header = f"@{hostname}-{time.ctime().replace(' ', '-')}"
        error_msg = f"{header}\n{error_msg}"
        cprint(f"{error_msg}", 'red')
        error_sock.send_multipart([CommandType.ERROR, pickle.dumps(error_msg)])
        error_sock.recv_multipart()
                
    @staticmethod
    async def _host_game(
            hostname,
            sock,
            task_dict,
            players,
            aio_event,
            alive_evnet,
            req_kill_event,
            exc_queue,
            n_games,
            realtime=False, 
            portconfig=None, 
            save_replay_as=None, 
            step_time_limit=None,
            game_time_limit=None, 
            rgb_render_config=None, 
            random_seed=None,
        ):

        async with SC2Process(render=rgb_render_config is not None) as server:
            try:
                for _ in range(n_games):
                    # Learner에게 다음에 실행할 게임 세팅을 요청
                    sock.send_multipart([CommandType.REQ_TASK])
                    task_dict.update(pickle.loads(sock.recv_multipart()[0]))
                    # 게임 세팅 설정
                    # !주의!: join쪽 task_dict, players와 동일한 인스턴스를 유지해야 하기 때문에,
                    # 절대 여기서 새로 생성하지 말고 업데이트만 해야함, 
                    # 불가: players = [_Bot(), _Bot()], 가능 players[0] = _Bot(); players[1] = _Bot()
                    step_interval = task_dict['step_interval']
                    players[0] = _Bot(Race.Terran, MyBot(step_interval, hostname, sock))
                    players[1] = _Bot(Race.Terran, OppBot())

                    # 게임 세팅이 완료되면 event를 set해서 join 쪽도 다음 과정을 진행하도록 함
                    aio_event.set()
                    # 게임이 새로 시작했음을 부모 프로세스에 알림
                    alive_evnet.set()

                    # 게임 시작
                    map_settings = sc2.maps.get(task_dict['game_map'])
                    await server.ping()
                    client = await _setup_host_game(server, map_settings, players, realtime, random_seed)
                    
                    result = await _play_game(
                        players[0], client, realtime, portconfig, 
                        step_time_limit, game_time_limit, rgb_render_config
                    )
                    if save_replay_as is not None:
                        await client.save_replay(save_replay_as)
                    await client.leave()  
                    # await client.quit()  # 게임 인스턴스 재시작을 위해 프로세스 종료하지 않음
            except:
                # 예외가 발생하면 부모 프로세스에 전달
                import traceback
                exc_queue.put(traceback.format_exc())

            # n_games 만큼 게임을 반복했음을 부모 프로세스에 알림
            # join에서 host를 죽이거나, host에서 join을 죽일 경우를 대비해서,
            # host와 join 양쪽에 req_kill_evnet를 set 해야함 
            # -> 어떤 경우에도 부모는 이 프로세스를 종료해야함을 알 수 있음
            req_kill_event.set()

    @staticmethod
    async def _join_game(
            task_dict,
            players,
            aio_event,
            alive_evnet,
            req_kill_event,
            exc_queue,
            n_games,
            realtime=False, 
            portconfig=None,
            save_replay_as=None, 
            step_time_limit=None, 
            game_time_limit=None,
        ):

        async with SC2Process() as server:
            try:
                for _ in range(n_games):
                    # host에서 게임을 세팅할 때까지 기다림
                    await aio_event.wait()
                    aio_event.clear()
                    # 게임을 재시작했음을 부모 프로세스에 알림
                    alive_evnet.set()

                    # 게임 시작
                    await server.ping()
                    client = Client(server._ws)

                    result = await _play_game(
                        players[1], client, realtime, portconfig, 
                        step_time_limit, game_time_limit
                    )
                    if save_replay_as is not None:
                        await client.save_replay(save_replay_as)
                    await client.leave()
                    # await client.quit()  # 게임 인스턴스 재시작을 위해 프로세스 종료하지 않음
            except:
                # 예외가 발생하면 부모 프로세스에 전달
                import traceback
                exc_queue.put(traceback.format_exc())             

            # n_games 만큼 게임을 반복했음을 부모 프로세스에 알림
            # join에서 host를 죽이거나, host에서 join을 죽일 경우를 대비해서,
            # host와 join 양쪽에 req_kill_evnet를 set 해야함 
            # -> 어떤 경우에도 부모는 이 프로세스를 종료해야함을 알 수 있음
            req_kill_event.set()
