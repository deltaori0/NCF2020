
예제 0. Dummy
==============

.. figure:: ../../docs/_static/base_game_ai.png
   :figwidth: 400

   게임 AI 기본구조

대부분의 Game AI는 현재 상태(state, observation)를 인식하고, 
그에 적절한 액션(action)을 결정하는 작업을 반복하는 객체이다.
상태는 현재 AI가 처해있는 주변 상태에 대한 정보를 담고 있고, 
AI는 이 정보를 처리해서, 현재 상태를 목표 상태(goal)에 가깝도록 바꿀 수 있는 
액션을 출력할 수 있어야 한다.
상태, 액션, 목표를 어떻게 정의할 지, 상태를 어떻게 처리할지에 따라서 다양한 방식으로 AI를 구현할 수 있다.

처음으로 소개하는 Dummy AI는 가장 간단한 예(아무 것도 하지 않는 AI)를 보여준다.
이 AI는 게임으로부터 상태 정보를 제공받지만, 아무런 처리도 하지 않고, 아무런 액션도 반환하지 않는다.
이 AI는 python-sc2에서 구현할 수 있는 가장 간단한 AI를 보여주기 위해 소개한다.

python-sc2에 AI를 구현할 때는, python-sc2의 sc2.BotAI 클래스를 상속한 뒤, 
__init__, on_step 등의 메소드를 오버라이딩해서 봇을 구현하면 된다.


.. literalinclude:: bot.py
   :pyobject: Bot


이번 경진대회에서는 운영 편의상 AI 객체의 이름은 Bot으로 하고, 파일 이름은 bot.py,
해당 AI와 관련된 모든 파일은 bots 폴더의 서브폴더에 저장한다.

예를 들어 내가 제출하는 봇의 이름이 My Bot 이라면, 관련된 코드 및 데이터를 bots/my_bot 
폴더에 저장하고, BoatAI 클래스를 상속한 클래스는 bots/my_bot/bot.py 파일에 Bot 으로 한다.

이 AI를 실행하려면 다음 명령을 터미널에서 입력하면 된다.

.. code-block:: bash

   (sc2) ~/sc2minigame $ python run_sc2minigame.py --bot1=bots.nc0_dummy


코드에서 쉽게 확인할 수 있듯이, 이 AI는 아무런 액션도 하지 않기 때문에, 
시간이 지나면 상대 유닛이 공격해와서 패배하는 것을 볼 수 있다.