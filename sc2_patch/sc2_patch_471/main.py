import asyncio
import async_timeout
import time
import logging
logger = logging.getLogger(__name__)

from sc2.main import _play_game_human
from sc2.main import _host_game

from sc2.sc2process import SC2Process
from sc2.portconfig import Portconfig
from sc2.player import Human, Bot
from sc2.data import Race, Difficulty, Result, ActionResult, CreateGameError
from sc2.game_state import GameState
from sc2.protocol import ConnectionAlreadyClosed, ProtocolError
from sc2.client import Client

# rgb render config 설정
async def _join_game(players, realtime, portconfig, save_replay_as=None, step_time_limit=None, game_time_limit=None, rgb_render_config=None):
    async with SC2Process() as server:
        await server.ping()

        client = Client(server._ws)

        try:
            result = await _play_game(players[1], client, realtime, portconfig, step_time_limit, game_time_limit, rgb_render_config=rgb_render_config)
            if save_replay_as is not None:
                await client.save_replay(save_replay_as)
            await client.leave()
            await client.quit()
        except ConnectionAlreadyClosed:
            logging.error(f"Connection was closed before the game ended")
            return None

        return result

# host_only_args 에서 rgb_render_config 제외
def run_game(map_settings, players, **kwargs):
    if sum(isinstance(p, (Human, Bot)) for p in players) > 1:
        host_only_args = ["save_replay_as", "random_seed"]
        join_kwargs = {k: v for k, v in kwargs.items() if k not in host_only_args}

        portconfig = Portconfig()
        result = asyncio.get_event_loop().run_until_complete(asyncio.gather(
            _host_game(map_settings, players, **kwargs, portconfig=portconfig),
            _join_game(players, **join_kwargs, portconfig=portconfig)
        ))
    else:
        result = asyncio.get_event_loop().run_until_complete(
            _host_game(map_settings, players, **kwargs)
        )
    return result


# sc2.main._play_game 함수에 log_queue 추가
async def _play_game(player, client, realtime, portconfig, step_time_limit=None, game_time_limit=None, rgb_render_config=None, log_queue=None):
    assert isinstance(realtime, bool), repr(realtime)

    player_id = await client.join_game(player.name, player.race, portconfig=portconfig, rgb_render_config=rgb_render_config)
    logger.info(f"Player id: {player_id} ({player.name})")

    if isinstance(player, Human):
        result = await _play_game_human(client, player_id, realtime, game_time_limit)
    else:
        result = await _play_game_ai(client, player_id, player.ai, realtime, step_time_limit, game_time_limit, log_queue)

    logger.info(f"Result for player id: {player_id}: {result}")
    return result


# haprk8312: log_queue 추가
async def _play_game_ai(client, player_id, ai, realtime, step_time_limit, game_time_limit, log_queue=None):
    if realtime:
        assert step_time_limit is None

    # step_time_limit works like this:
    # * If None, then step time is not limited
    # * If given integer or float, the bot will simpy resign if any step takes longer than that
    # * Otherwise step_time_limit must be an object, with following settings:
    #
    # Key         | Value      | Description
    # ------------|------------|-------------
    # penalty     | None       | No penalty, the bot can continue on next step
    # penalty     | N: int     | Cooldown penalty, BotAI.on_step will not be called for N steps
    # penalty     | "resign"   | Bot resigns when going over time limit
    # time_limit  | int/float  | Time limit for a single step
    # window_size | N: int     | The time limit will be used for last N steps, instad of 1
    #
    # Cooldown is a harsh penalty. The both loses the ability to act, but even worse,
    # the observation data from skipped steps is also lost. It's like falling asleep in
    # a middle of the game.
    time_penalty_cooldown = 0
    if step_time_limit is None:
        time_limit = None
        time_window = None
        time_penalty = None
    elif isinstance(step_time_limit, (int, float)):
        time_limit = float(step_time_limit)
        time_window = SlidingTimeWindow(1)
        time_penalty = "resign"
    else:
        assert isinstance(step_time_limit, dict)
        time_penalty = step_time_limit.get("penalty", None)
        time_window = SlidingTimeWindow(int(step_time_limit.get("window_size", 1)))
        time_limit = float(step_time_limit.get("time_limit", None))


    game_data = await client.get_game_data()
    game_info = await client.get_game_info()

    ai._prepare_start(client, player_id, game_info, game_data)
    try:
        ai.on_start()
    except Exception as e:
        logger.exception(f"AI on_start threw an error")
        logger.error(f"resigning due to previous error")
        ai.on_end(Result.Defeat)
        return Result.Defeat

    iteration = 0
    while True:
        state = await client.observation()
        logger.debug(f"Score: {state.observation.observation.score.score}")

        if client._game_result:
            ai.on_end(client._game_result[player_id])
            return client._game_result[player_id]

        gs = GameState(state.observation, game_data)

        if game_time_limit and (gs.game_loop * 0.725 * (1 / 16)) > game_time_limit:
            ai.on_end(Result.Tie)
            return Result.Tie

        ai._prepare_step(gs)

        if iteration == 0:
            ai._prepare_first_step()

        logger.debug(f"Running AI step, it={iteration} {gs.game_loop * 0.725 * (1 / 16):.2f}s")

        try:
            await ai.issue_events()
            if realtime:
                await ai.on_step(iteration)
            else:
                if time_penalty_cooldown > 0:
                    time_penalty_cooldown -= 1
                    logger.warning(f"Running AI step: penalty cooldown: {time_penalty_cooldown}")
                    iteration -= 1 # Do not increment the iteration on this round
                elif time_limit is None:
                    await ai.on_step(iteration)
                else:
                    out_of_budget = False
                    budget = time_limit - time_window.available

                    # Tell the bot how much time it has left attribute
                    ai.time_budget_available = budget

                    if budget < 0:
                        logger.warning(f"Running AI step: out of budget before step")
                        step_time = 0.0
                        out_of_budget = True
                    else:
                        step_start = time.monotonic()
                        try:
                            async with async_timeout.timeout(budget):
                                await ai.on_step(iteration)
                        except asyncio.TimeoutError:
                            step_time = time.monotonic() - step_start
                            logger.warning(
                                f"Running AI step: out of budget; " +
                                f"budget={budget:.2f}, steptime={step_time:.2f}, " +
                                f"window={time_window.available_fmt}"
                            )
                            out_of_budget = True
                        step_time = time.monotonic() - step_start

                    time_window.push(step_time)

                    if out_of_budget and time_penalty != None:
                        if time_penalty == "resign":
                            raise RuntimeError("Out of time")
                        else:
                            time_penalty_cooldown = int(time_penalty)
                            time_window.clear()
        except Exception as e:
            if isinstance(e, ProtocolError) and e.is_game_over_error:
                if realtime:
                    return None
                result = client._game_result[player_id]
                if result is None:
                    log.error("Game over, but no results gathered")
                    raise
                return result

            # NOTE: this message is caught by pytest suite
            logger.exception(f"AI step threw an error") # DO NOT EDIT!
            logger.error(f"resigning due to previous error")
            # hspark8312: begin
            if log_queue is not None:
                from time import gmtime, strftime
                import traceback
                tb = traceback.format_exc()
                log_queue.put(f"AI step threw an error")
                log_queue.put(f'{e} -> {tb}')
            # hspark8312: end
            ai.on_end(Result.Defeat)
            return Result.Defeat

        logger.debug(f"Running AI step: done")

        if not realtime:
            if not client.in_game:  # Client left (resigned) the game
                ai.on_end(client._game_result[player_id])
                return client._game_result[player_id]

            await client.step()

        iteration += 1
