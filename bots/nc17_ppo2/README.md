# Simple PPO 코드 응용 2

1. 빌드오더는 fix -> trainbot 코드 기반 약간 수정 (의료선 삭제)

2. 학습을 통해 이용하는 것은 ArmyStrategy 부분

   -> PPO1: ArmyStrategy 파트를 기존 PPO 코드와 똑같이 유지

   -> PPO2: ArmyStrategy를 공격/방어 두가지 외에 세분화

3. 세분화한 ArmyStrategy
   - DEFENSE_SIMPLE = 0 # 기존 DEFENSE mode
   - DEFENSE_SIEGETANK = 1 # 시즈탱크 이용한 방어선 구축
   - OFFENSE_LOW = 2 # 기존 OFFENSE mode
   - OFFENSE_MID = 3 # 중간 OFFENSE mode
   - OFFENSE_HIGH = 4 # high-end 유닛 이용한 높은 단계의 OFFENSE mode