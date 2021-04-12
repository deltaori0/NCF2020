# Simple PPO 코드 응용 3

1. EconomyStrategy 학습

2. 세분화한 ArmyStrategy
   - DEFENSE_SIMPLE = 0 # 기존 DEFENSE mode
   - DEFENSE_SIEGETANK = 1 # 시즈탱크 이용한 방어선 구축
   - OFFENSE_LOW = 2 # 기존 OFFENSE mode
   - OFFENSE_MID = 3 # 중간 비용 유닛 이용한 중간 단계의 OFFENSE mode
   - OFFENSE_HIGH = 4 # high-end 유닛 이용한 높은 단계의 OFFENSE mode