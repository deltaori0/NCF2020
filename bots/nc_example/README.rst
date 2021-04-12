예제 4. Simple PPO
===================

다양한 관점에서 보다 구체적으로 생각하면, 다른 형태로 문제를 정의할 수 있지만, 
현재 Simple 예제에서 중요한 의사결정 사항 두 가지는 다음에 어떤 유닛을 생산해야하는지, 언제 공격해야 하는지 두 가지이다.
Simple, Simple2, 그리고 Simple3는 이 두 가지 문제를 해결할 수 있는 간단한 AI를 구현한 예이다.
Simple3는 Simple이나 Simple2에 비해 성능이 향상되었지만, 의사결정 방법(규칙)을 수정해서 성능을 향상시킬 수 있는 여지가 충분히 있다.
유닛의 생산 비율을 조정하거나, 공격시점을 결정하는 규칙을 수정하는 것만으로도 승률을 높일 수 있다.

그러나, 규칙을 수정하고 평가하는 과정을 반복하는 것은 매우 번거로운 작업이고 
일정 수준이상의 성능에 도달하기 위해서는 보다 체계적이고 자동화된 방법이 필요한데, 
요즘에는 기계학습(Machine Learning)을 많이 사용된다.
만약 사전에 준비된 데이터가 있다면, 이를 이용해 감독학습(Supervised Learning)으로 AI를 빠르게 학습할 수 있지만, 
게임 플레이 데이터는 없기 때문에 AI가 게임을 직접 플레이하며 게임플레이하는 방법(정책, policy)을
학습하는 강화학습(RL, Reinforcement Learning)이 적절하다.

.. _build_order_comparison:
.. figure:: ../../docs/_static/build_order_comparision.png
   :figwidth: 600

   빌드오더 비교

유닛 마이크로 컨트롤을 크게 신경쓰고 있지 않은 지금 시점에서 
빌드오더와 공격시점을 결정하는 게임 승률에 가장 결정적인 영향을 준다. 
예를들어 두 개의 독특한 빌드오더가 있다고 가정하면 :ref:`build_order_comparison` 처럼 그림을 그릴 수 있다.
빌드오더에 따라, 전체 유닛들의 전투력이 증가하는 속도가 다른데, 보통 해병, 화염차 같은 싼 유닛을 먼저 생산하면,
빠르게 전투력이 증가하지만, 고급 유닛을 상대하기 어렵고, 
토르나 전투순양함 같은 고급 유닛을 생산하면 후반에는 전투력이 크게 증가하지만, 초반에는 전투력 증가속도가 느리다.
따라서, 빌드오더에 따라 게임 시간-전투력 곡선이 결정되는데 이상적으로는 내 전투력이 상대방보다 높은 시점에 
공격을 하는 것이 가장 유리하다. 
:ref:`build_order_comparison` 에서는 빌드오더1은 t시점 이후에 공격을 하는 것이 유리하고,
빌드오더 2는 t 시점 이전에 공격하는 것이 유리하다.

실제로는 상대방의 빌드오더나 현재 유닛구성을 알기 어렵고, 유닛간의 상성도 고려해야하기 때문에 어려운 문제지만,
상대방의 빌드오더가 고정된 상태라면 자신의 유닛정보만 가지고도 자신이 유리한 시점을 추론할 수 있다.
Simple PPO는 Simple3를 상대로 했을 때, 공격시점을 결정하는 규칙을 강화학습 알고리즘 중 하나인 
PPO (Proximal Policy Optimization)를 사용해 개선하는 예를 보여준다.

강화학습 실행
-------------

.. _simple_ppo_dist:
.. figure:: ../../docs/_static/simple_ppo_dist.png
   :figwidth: 600

   Simple PPO 학습환경

전체 시스템 구조는 :ref:`simple_ppo_dist` 처럼 구헝되어 있다. Trainer 하나와 여러 Actor들로 구성되어 있는데, 
Trainer를 먼저 실행한 뒤 원하는 만큼 Actor를 추가로 실행해서 추가할 수 있다.
Trainer와 Actor들을 모두 PC 한대에서 실행할 수도 있고, 서로 다른 PC에서 실행할 수도 있다.

StarCraft II를 실행하는데 많은 시스템 자원이 필요하기 때문에 
실제로 게임을 실행하는 Actor 프로세스를 분산환경에서 실행할 수 있도록 구성했다.

인공신경망을 포함한 학습 알고리즘의 거의 대부분은 Trainer 프로세스에서 담당하고, 
Actor는 게임을 실행하는 역할만 담당한다. 따라서, Actor에서는 게임 상태를 Trainer에게 전달하고,
신경망을 가지고 있는 Trainer가 액션을 결정해서 전달해주면 Actor는 액션을 실행한다.

.. code-block:: bash

   # Trainer 실행
   (sc2) ~/sc2minigame $ python -m bots.nc4_simple_ppo.train

학습 코드를 실행하려면 우선 Traniner process를 실행시킨다.
Trainer가 성공적으로 실행되면 "READY" 메시지가 출력된 채로 대기 한다.
Traniner는 학습 알고리즘을 실행하기만 하고, 게임을 플레이해서 데이터를 생성하지 않는다.
게임을 플레이해서 데이터를 생성하는 역할을하는 Actor process를 추가로 실행해야 한다.

.. code-block:: bash

   # Actor 실행
   (sc2) ~/sc2minigame $ python -m bots.nc4_simple_ppo.train --attach={trainer-ip} --n_actors=2

Actor는 Trainer와 비슷하게 실행하지만, Actor가 접속할 Trainer의 IP 주소를 --attach로 같이 입력하면,
Actor모드로 실행된다.
여러 Actor가 한 Trainer에 접속해서 학습을 수행할 수 있고, 많은 Actor가 접속할 수록 학습 속도를 향상시킬 수 있다.
실질적으로는 학습에 참가한 PC 사양에 따라 네트워크(LAN), CPU, GPU등에서 심각한 병목이 발생하여 
무한히 학습 속도를 향상시키는 것은 어렵지만, 일반적인 데스크톱 PC에서는 PC 10대 정도 까지는 문제없이 성능이 향상된다.

--n_actors 인자는 한번에 실행할 Actor의 개수를 뜻한다. 
여러 Actor를 실행하기 위해 여러번 명령어를 입력하는 대신, 한번에 여러 Actor를 실행할 수 있다.

학습이 성공적으로 진행되고 있다면, 다음과 같은 출력 결과를 얻을 수 있다.

.. figure:: ../../docs/_static/train_example.png
   :figwidth: 600

   Simple PPO 학습예(왼쪽: Trainer, 오른쪽: Actor)

tensorboard 출력결과는 runs 폴더에 저장되고, 학습한 인공신경망 모델은 bots/nc4_simple_ppo/model.pt 파일로 저장된다.

.. note::

   Ctrl + C를 눌러도 Trainer는 종료되지 않고, IPython 콘솔이 뜬다. Trainer를 완전히 종료시키려면,
   IPython 콘솔에서 self.stop()을 입력한 뒤 콘솔을 종료(exit 입력)해야한다.

PC 사양에 따라 차이는 있지만, Actor를 네 개 이상 사용한다면 GPU를 사용하지 않아도, 약 10시간 안에
Simle PPO는 Simple3를 상대로 90%가 넘는 승률을 달성할 수 있다.

.. code-block:: bash

   (sc2) ~/sc2minigame $ python run_sc2minigame.py --bot1=bots.nc4_simple_ppo  --bot2=bots.nc3_simple3
