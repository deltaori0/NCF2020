
시작하기
=========

.. note::

   README.rst 파일을 보고 있다면, 전체 문서내용은 index.html을 참조할 것


소개
------

이 플랫폼은 2020년 NC Fellowship Game AI 경진대회 목적으로 구현되었다.
이 플랫폼은 Blizzard™ [#sc2]_ 의 StarCraft 2, s2client-api [#]_ 그리고 Hannes Karppila의
python-sc2 [#]_ 를 이용해 간단한 실시간 전략 시뮬레이션(Real-Time Strategy) 환경을 제공한다.

StarCraft 2같은 RTS 게임을 플레이하는 AI는 건물 건설, 유닛 생산, 업그레이드, 전투 등
다양한 작업을 수행해야 하기 때문에, AI를 구현하려면 매우 많은 작업이 필요하다.
2020년 경진대회에서는 자원 수집, 건물 건설을 생략하고, 
제한된 유닛 생산과 유닛 컨트롤에 집중한 경진대회 플랫폼(맵)을 구현했다.

경진대회는 StarCraft 2 (v4.10) Linux 클라이언트를 기준으로 진행한다.
Windows용 클라이언트는 자주 업데이트가 되며, python-sc2와 호환되지 않는 경우가 종종 발생하며,
이전 버전으로 다운그레이드가 어렵기 때문에, Linux 클라이언트를 사용하는 것을 기본으로 한다.

.. note::

   현재 사용하고 있는 게임 규칙이나 유닛 속성은 경진대회 운영에 심각한 문제가 될 경우 일부 변경될 수 있음


경진대회는 Linux 클라이언트를 기준으로 진행되지만, 
가능하다면 Windows용 StarCraft II도 설치하는 것이 AI 개발에 편리하다.
Linux용 클라이언트는 기본적으로 화면을 렌더링 하지 않기 때문에, 시스템 요구사항이 낮고 빠른 장점이 있지만,
실제 AI가 작동하는 모습을 확인하기 불가능하지는 않지만, 추가 노력이 필요하다.
특정 버그는 게임을 직접 플레이하거나, AI가 작동하는 모습을 관찰하면 쉽게 발견하거나 해결할 수 있으므로,
대부분의 작업을 Linux에서 하더라도, 가능하다면 Windows에서 가끔 결과물을 확인하는것이 좋다.

별도 Linux PC가 없다면, WSL (Windows Linux Subsystem) [#wsl]_ 을 이용할 수 있다.

이 플랫폼은 python-sc2를 기반으로 구현되었기 때문에, python-sc2의 설치방법,
사용법을 거의 그대로 공유한다. 이 문서에서 부족한 부분은, python-sc2 혹은
그 기반이 되는 s2client-api를 참조할 수 있다.

설치
-----

이 플랫폼은 Winodws 10과 Ubuntu 18.04 환경에서 개발 및 테스트 했다.
python-sc2가 macOS 환경도 지원하기 때문에 아마도 macOS에서도 문제가 없을 것으로 추측된다.

플랫폼을 설치하는 과정은 세 단계로 구성된다.

1. python 설치 
2. 가상환경 생성
3. StarCraft 2 설치
4. sc2minigame 설치

**python 설치**

여기서는 python anaconda 배포판을 사용하는 것을 기준으로 설명한다.
Windows나 Linux GUI 환경에서는 https://www.anaconda.com/distribution/ 에서
64bit python 3.7을 다운받아서 설치한다.

Linux 터미널에서는 아래 명령으로 anaconda 배포판을 다운받아 설치한다.

.. code-block:: bash 
  
  $ wget https://repo.anaconda.com/archive/Anaconda3-2020.02-Linux-x86_64.sh
  $ sh Anaconda3-2020.02-Linux-x86_64.sh

**가상환경 생성**

Windows와 Linux 모두 터미널(콘솔)을 열고, 아래 명령을 입력해서 
anaconda 가상환경을 만들고, 필요한 모듈을 설치한다.

.. code-block:: bash

   $ # 가상환경 생성
   $ conda create -n sc2 -y python=3.7 
   $
   $ # 환경 활성화
   $ conda activate sc2
   $
   (sc2) $ # 필수 모듈 설치
   (sc2) $ conda install -n sc2 -y ipython numpy scipy scikit-image matplotlib psutil tqdm tensorflow pyzmq portpicker async-timeout aiohttp
   (sc2) $ conda install -n sc2 -y -c conda-forge pyglet
   (sc2) $ conda install -n sc2 -y -c pytorch pytorch torchvision cpuonly   # cpu 버전
   (sc2) $ # conda install pytorch torchvision cudatoolkit=10.2 -c pytorch  # gpu 버전
   (sc2) $ pip install nest_asyncio
   (sc2) $ pip install s2clientprotocol
   (sc2) $ pip install plotille
   
**StarCraft 2 설치**

Windows 환경에서는 일반적인 방식으로 Battle.net을 통해 StarCraft 2를 설치한다.
python-sc2에서 StarCraft 2 기본 설치 경로(C:/Program Files (x86)/StarCraft II)에서
실행파일을 찾기 때문에, 가급적이면 설치 경로를 바꾸지 않는 것이 좋다. 설치 경로를 바꿔야 할 필요가 있다면,
환경변수 SC2PATH를 변경해야 한다 (python-sc2 문서를 참조).

.. warning::

  - StarCraft 2 를 처음 설치하면 C:/Program Files (x86)/StarCraft II/Maps 폴더를 만들어줘야 한다.
  - 윈도우즈 탐색기에서 폴더를 만들고, 지도를 이 폴더에 복사해 두면, 플랫폼에서 이 폴더에 있는 지도를 사용할 수 있다.

Linux환경에서는 https://github.com/Blizzard/s2client-proto#downloads 에서 
Linux용 바이너리를 다운받아서 ~/StarCraftII에 압축을 해제한다.
Linux용 바이너리는 Windows용 바이너리와 달리 화면을 렌더링하지 않아서(Headless), 
실행에 GPU가 필요하지 않고, 메모리 사용량도 적다.

Windows와 마찬가지로 ~/StarCraftII/Maps가 없다면 직접 만들어줘야 한다.

.. code-block:: bash

   $ # StarCraft 2 (v4.10) 리눅스 바이너리 다운로드
   $ cd ~
   $ wget http://blzdistsc2-a.akamaihd.net/Linux/SC2.4.10.zip  
   $
   $ # 압축해제(암호: iagreetotheeula)
   $ sudo apt install unzip
   $ unzip ~/SC2.4.10.zip -d ~/  
   $
   $ # 실행파일에 실행 권한 부여
   $ chmod +x ~/StarCraftII/Versions/Base*/SC2_x64
   $
   $ # 플랫폼에서 Maps 대신 maps에서 지도를 검색하는 경우(버그)가 있을 때
   $ ln -s $HOME/StarCraftII/Maps $HOME/StarCraftII/maps

Windows용 바이너리(게임)은 수시로 업데이트가 되고, 구버전을 사용하기 어렵지만,
Linux용 바이너리는 원하는 버전을 언제나 사용할 수 있기 때문에,
2020년 경진대회는 Linux용 바이너리 4.10을 기준으로 경진대회를 진행한다.


**sc2minigame 설치**

https://github.com/rex8312/NCF2020/releases 에서 최신 releases를 다운받아, 
설치를 원하는 경로에 압축해제한다. 여기서는 ~/sc2minigame에 압축해제했다고 가정하고 다음 과정을 진행한다.

Windows와 Linux 모두 2020년 경진대회에 사용할 맵을 StarCraft II의 Maps 폴더에 복사한다.
Maps 폴더가 없다면 생성후 복사한다.

.. code-block:: bash

   $ # 지도 복사
   $ cp ~/sc2minigame/maps/NCF-2020-v4.SC2Map $HOME/StarCraftII/Maps


게임 실행
---------

**예제 AI vs. StarCraft 기본 AI**

구현한 AI와 기본 컴퓨터 AI끼리 플레이를 할 때는 다음 명령을 입력한다.

.. code-block:: bash

   (sc2) ~/sc2minigame $ python run_sc2minigame.py \
                         --bot1=bots.nc3_simple3 \
                         --realtime=True \
                         --save_replay_as=test.SC2Replay

--bot1 옵션은 1번 플레이어 경로를 지정하는 옵션이고
--bot2에 기본 플레이어 옵션으로 기본 AI (난이도 7)가 지정되어 있다.

bots.nc3_simple3 AI는 ./bots/nc3_simple3 폴더에 있는 AI 이다.
이 문서/플랫폼에서는 bot과 AI는 동일한 의미로 사용한다.

--realtime 옵션이 True 일때는 게임이 실시간으로 실행되고
False 일때는 최대한 빠르게 가속되어 실행된다. 
경진대회에서는 AI vs. AI만을 가정하기 때문에, 
디버깅 목적이외에 realtime 옵션을 사용할 경우는 없을 것이다.

--save_replay_as 옵션은 리플레이를 저장하고 싶을때 사용한다. 
파일이름(확장자 SC2Replay)를 지정하면, 리플레이가 파일로 저장된다.
Linux 바이너리로 게임을 플레이하고 저장한 리플레이를, Windows에서 볼 수 있다.

Windows에서는 잠시 후 StarCraft II 게임이 실행될 것이고, 
Linux에서는 터미널에서 로그 메시지가 출력될 것이다. 
게임이 성공적으로 실행되면, 플랫폼 설치가 완료된 것이다.

run_sc2minigame.py는 AI를 실행하는 하나의 예일 뿐이고, python-sc2에서 
제공하는 API를 이용해 다양한 방식으로 실행가능하다(python-sc2 예제 참조).
실제 개발 도중에는 run_sc2minigame.py를 이용해 게임을 실행하는 경우보다,
직접 작성한 학습 스크립트를 이용해 실행하는 경우가 훨씬 많다.

**실행 예1) 예제 AI vs. 예제 AI**

다른 두 예제 AI끼리 게임을 하려면 다음 처럼 --bot1과 --bot2 옵션으로
게임을 하려는 AI를 지정하면 된다.

python-sc2를 이용해 구현한 AI는 게임에서는 인간 플레이어로 취급되므로,
기본 AI로 플레이 할때와 달리 게임이 두 개가 실행된다.
게임 하나는 서버가 되고, 하나는 클라이언트가 되어 멀티 플레이로 게임이 실행된다.
python-sc2에서는 서버를 host, 클라이언트를 join이라고 한다.

.. code-block:: bash

   (sc2) ~/sc2minigame $ python run_sc2minigame.py \
                         --bot1=bots.nc3_simple3 \
                         --bot2=bots.nc3_simple3 \
                         --realtime=False

**실행 예2) 인간 vs. 예제 AI**

python-sc2로 구현한 AI는 게임 중에 사람의 입력을 그대로 받을 수 있다.
따라서, run_sc2minigame.py에서는 아무 행동도 하지 않는 AI인 dummy를 실행해서
AI와 게임을 플레이 할 수 있도록 했다.

.. code-block:: bash

   (sc2) ~/sc2minigame $ python run_sc2minigame.py \
                         --bot1=bots.nc0_dummy \
                         --bot2=bots.nc3_simple3 \
                         --realtime=True

python-sc2에는 인간 플레이어를 직접 지정하는 할 수 도 있다 (python-sc2 문서 참조).


.. rubric:: Footnotes

.. [#sc2] StarCraft는 미국 및 다른 국가에서 Blizzard Entertainment Inc. 의 상표 또는 등록상표 입니다.
.. [#] https://github.com/Blizzard/s2client-api
.. [#] https://github.com/Dentosal/python-sc2
.. [#wsl] https://docs.microsoft.com/ko-kr/windows/wsl/
