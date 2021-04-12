
sc2minigame 튜토리얼
====================

.. note::

   - 현재 이 문서는 2020년 NCFellowship을 위해 준비된 플랫폼과 경진대회에 대한 
     내용을 포함하고 있음
   - 경진대회 플랫폼은 Blizzard™의 StarCraft 2 [#sc2]_, s2client-api [#sc2api]_ 
     그리고 Hannes Karppila의 python-sc2 [#python-sc2]_ 를 기반으로 하고 있음


환경설정 및 기본 예제
-----------------------

여기서는 이 플랫폼과 경진대회 환경에 대한 소개를 하고, 기본적인 AI 구현 예제를 소개한다.
마지막에는 구현한 AI를 제출하는 방법에 대해 설명한다.

* :doc:`시작하기 </README>`
* :doc:`시스템 구조 및 게임 규칙 </docs/system_and_rules>`
* :doc:`예제 0. Dummy </bots/nc0_dummy/README>`
* :doc:`예제 1. Simple: 간단한 build-order </bots/nc1_simple/README>`
* :doc:`예제 2. Simple 2: 적응형 build-order </bots/nc2_simple2/README>`
* :doc:`예제 3. Simple 3: 집결지 </bots/nc3_simple3/README>`
* :doc:`예제 4. Simple PPO: 강화학습 예 </bots/nc4_simple_ppo/README>`
* :doc:`예제 5. Nuke Bot: 스킬 사용 예 </bots/nc5_nuke_bot/README>`
* :doc:`평가 시스템 및 제출 방식 </eval/README>`

.. toctree::
   :caption: 환경설정 및 기본 예제
   :maxdepth: 1
   :hidden:

   시작하기 <README.rst>
   시스템 구조 및 게임 규칙 <docs/system_and_rules.rst>
   예제 0. Dummy <bots/nc0_dummy/README.rst>
   예제 1. Simple: 간단한 build-order <bots/nc1_simple/README.rst>
   예제 2. Simple 2: 적응형 build-order <bots/nc2_simple2/README.rst>
   예제 3. Simple 3: 집결지 <bots/nc3_simple3/README.rst>
   예제 4. Simple PPO: 분산학습 예 <bots/nc4_simple_ppo/README.rst>
   예제 5. Nuke Bot: 스킬 사용 예 <bots/nc5_nuke_bot/README.rst>
   평가 시스템 및 제출 방식 <eval/README.rst>


.. 고급 예제
.. -----------------

.. .. toctree::
..    :caption: 고급 예제
..    :maxdepth: 1
..    :hidden:

..    예제 5. Map feature 처리 추가 <bots/nc4_simple_ppo/README.rst>
..    예제 6. Unit feature 처리 추가 <bots/nc4_simple_ppo/README.rst>
..    예제 7. ...



.. API
.. =====

.. .. toctree::
..    :maxdepth: 2

..    bots
..    run_sc2minigame
..    sc2_data
..    sc2_patch
..    sc2_utils


인덱스
------

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`


.. rubric:: Footnotes

.. [#sc2] StarCraft는 미국 및 다른 국가에서 Blizzard Entertainment Inc. 의 상표 또는 등록상표 입니다.
.. [#sc2api] https://github.com/Blizzard/s2client-api
.. [#python-sc2] https://github.com/Dentosal/python-sc2