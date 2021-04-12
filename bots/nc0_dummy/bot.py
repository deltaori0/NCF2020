
__author__ = '박현수 (hspark8312@ncsoft.com), NCSOFT Game AI Lab'


import sc2


class Bot(sc2.BotAI):
    """
    아무것도 하지 않는 봇 예제
    """
    def __init__(self, *args, **kwargs):
        super().__init__()

    async def on_step(self, iteration: int):
        """
        :param int iteration: 이번이 몇 번째 스텝인지를 인자로 넘겨 줌

        매 스텝마다 호출되는 함수
        주요 AI 로직은 여기에 구현
        """

        # 유닛들이 수행할 액션은 리스트 형태로 만들어서,
        # do_actions 함수에 인자로 전달하면 게임에서 실행된다.
        # do_action 보다, do_actions로 여러 액션을 동시에 전달하는 
        # 것이 훨씬 빠르다.
        actions = list()
        await self.do_actions(actions)

