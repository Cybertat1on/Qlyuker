import random
import asyncio
from time import time
from random import randint
from urllib.parse import unquote

import aiohttp
from aiohttp_proxy import ProxyConnector
from better_proxy import Proxy
from pyrogram import Client
from pyrogram.errors import Unauthorized, UserDeactivated, AuthKeyUnregistered
from pyrogram.raw.functions.messages import RequestAppWebView
from pyrogram.raw import types

from bot.config import settings
from bot.utils import logger
from bot.exceptions import InvalidSession
from bot.core.headers import headers


class Tapper:
    def __init__(self, tg_client: Client):
        self.session_name = tg_client.name
        self.tg_client = tg_client
        self.user_id = 0
        self.username = None
        self.first_name = None
        self.last_name = None
        self.fullname = None
        self.start_param = None
        self.peer = None
        self.first_run = None
        self.user_data = {}
        self.tg_web_data = None
        self.client_lock = asyncio.Lock()

    async def get_tg_web_data(self, proxy: str | None) -> str:
        async with self.client_lock:
            if proxy:
                proxy = Proxy.from_str(proxy)
                proxy_dict = dict(
                    scheme=proxy.protocol,
                    hostname=proxy.host,
                    port=proxy.port,
                    username=proxy.login,
                    password=proxy.password
                )
            else:
                proxy_dict = None

            self.tg_client.proxy = proxy_dict

            try:
                with_tg = True

                if not self.tg_client.is_connected:
                    with_tg = False
                    try:
                        await self.tg_client.connect()
                    except (Unauthorized, UserDeactivated, AuthKeyUnregistered):
                        raise InvalidSession(self.session_name)

                self.start_param = random.choices([settings.REF_ID, "bro-1197825376"], weights=[60, 40], k=1)[0]
                peer = await self.tg_client.resolve_peer('qlyukerbot')
                InputBotApp = types.InputBotAppShortName(bot_id=peer, short_name="start")

                web_view = await self.tg_client.invoke(RequestAppWebView(
                    peer=peer,
                    app=InputBotApp,
                    platform='android',
                    write_allowed=True,
                    start_param=self.start_param
                ))

                auth_url = web_view.url
                tg_web_data = unquote(
                    string=auth_url.split('tgWebAppData=', maxsplit=1)[1].split('&tgWebAppVersion', maxsplit=1)[0])

                try:
                    if self.user_id == 0:
                        information = await self.tg_client.get_me()
                        self.user_id = information.id
                        self.first_name = information.first_name or ''
                        self.last_name = information.last_name or ''
                        self.username = information.username or ''
                except Exception as e:
                    print(e)

                if with_tg is False:
                    await self.tg_client.disconnect()

                return tg_web_data

            except InvalidSession as error:
                raise error

            except Exception as error:
                logger.error(
                    f"<cyan><cyan>{self.session_name}</cyan></cyan> | Unknown error during Authorization: {error}")
                await asyncio.sleep(delay=3)
                return None

    async def login(self, http_client: aiohttp.ClientSession, tg_web_data: str) -> dict:
        try:
            http_client.headers['Onboarding'] = '0'

            response = await http_client.post(
                url='https://qlyuker.io/api/auth/start',
                json={"startData": tg_web_data}
            )
            response.raise_for_status()
            response_json = await response.json()
            http_client.headers['Onboarding'] = '2'
            return response_json

        except Exception as error:
            logger.error(f"<cyan>{self.session_name}</cyan> | Error during login: {error}")
            await asyncio.sleep(delay=3)
            return {}

    async def get_upgrades(self, login_data: dict) -> list:
        return login_data.get('upgrades', [])

    async def send_taps(self, http_client: aiohttp.ClientSession, taps: int, current_energy: int) -> dict:
        try:
            client_time = int(time())
            json_data = {
                "currentEnergy": current_energy,
                "clientTime": client_time,
                "taps": taps
            }
            response = await http_client.post(
                url='https://qlyuker.io/api/game/sync',
                json=json_data
            )
            response.raise_for_status()

            response_json = await response.json()
            return response_json
        except Exception as error:
            logger.error(f"<cyan>{self.session_name}</cyan> | Error during send_taps: {error}")
            await asyncio.sleep(delay=3)
            return {}

    async def buy_upgrade(self, http_client: aiohttp.ClientSession, upgrade_id: str) -> dict:
        try:
            http_client.headers['Referer'] = 'https://qlyuker.io/upgrades'
            json_data = {"upgradeId": upgrade_id}
            response = await http_client.post(
                url='https://qlyuker.io/api/upgrades/buy',
                json=json_data
            )
            response.raise_for_status()

            response_json = await response.json()
            return response_json
        except aiohttp.ClientResponseError as error:
            # logger.error(
            #     f"<cyan>{self.session_name}</cyan> | Error during buy_upgrade: {error.status}, "
            #     f"message='{error.message}', url={error.request_info.url}"
            # )
            await asyncio.sleep(delay=3)
            return {}
        except Exception as error:
            #logger.error(f"<cyan>{self.session_name}</cyan> | Unexpected error during buy_upgrade: {error}")
            await asyncio.sleep(delay=3)
            return {}

    async def claim_daily_reward(self, http_client: aiohttp.ClientSession) -> dict:
        try:
            http_client.headers['Referer'] = 'https://qlyuker.io/tasks'
            response = await http_client.post(
                url='https://qlyuker.io/api/tasks/daily'
            )
            response.raise_for_status()
            response_json = await response.json()
            logger.info(f"<cyan>{self.session_name}</cyan> | ✔️ Daily reward claimed.")
            return response_json
        except Exception as error:
            logger.error(f"<cyan>{self.session_name}</cyan> | Error during claim_daily_reward: {error}")
            return {}

    async def collect_daily_bonus(self, http_client: aiohttp.ClientSession, proxy: str | None):
        while True:
            try:
                if not self.tg_web_data:
                    self.tg_web_data = await self.get_tg_web_data(proxy=proxy)
                if not self.tg_web_data:
                    logger.error(f"<cyan>{self.session_name}</cyan> | Failed to get tg_web_data in collect_daily_bonus")
                    await asyncio.sleep(60)
                    continue

                login_data = await self.login(http_client=http_client, tg_web_data=self.tg_web_data)
                if not login_data:
                    logger.error(f"<cyan>{self.session_name}</cyan> | Login failed during collect_daily_bonus")
                    await asyncio.sleep(60)
                    continue
                self.user_data = login_data.get('user', {})
                daily_reward = self.user_data.get('dailyReward', {})
                day = daily_reward.get('day', 0)
                claimed = daily_reward.get('claimed', None)

                if claimed is False or claimed is None:
                    logger.info(f"<cyan>{self.session_name}</cyan> | Daily reward not claimed yet. Attempting to claim.")
                    reward_response = await self.claim_daily_reward(http_client=http_client)
                    if reward_response:
                        self.user_data.update(reward_response.get('user', {}))
                        current_coins = self.user_data.get('currentCoins', 0)
                        logger.info(f"<cyan>{self.session_name}</cyan> | ✔️ Daily reward claimed. 💰 Current coins: <yellow>{current_coins}</yellow>")
                    else:
                        logger.error(f"<cyan>{self.session_name}</cyan> | Failed to claim daily reward.")
                else:
                    logger.info(f"<cyan>{self.session_name}</cyan> | Daily reward already received. Will try again in 8 hours.")

                await asyncio.sleep(8 * 3600)
            except Exception as error:
                logger.error(f"<cyan>{self.session_name}</cyan> | [Daily Bonus Task] Error: {error}")
                import traceback
                traceback.print_exc()
                await asyncio.sleep(60)

    async def collect_tasks(self, http_client: aiohttp.ClientSession, proxy: str | None):
        while True:
            try:
                if not self.tg_web_data:
                    self.tg_web_data = await self.get_tg_web_data(proxy=proxy)
                if not self.tg_web_data:
                    logger.error(f"<cyan>{self.session_name}</cyan> | Failed to get tg_web_data in collect_tasks")
                    await asyncio.sleep(60)
                    continue

                login_data = await self.login(http_client=http_client, tg_web_data=self.tg_web_data)
                if not login_data:
                    logger.error(f"<cyan>{self.session_name}</cyan> | Login failed during collect_tasks")
                    await asyncio.sleep(60)
                    continue

                self.user_data = login_data.get('user', {})
                tasks = login_data.get('tasks', [])
                if not tasks:
                    logger.info(f"<cyan>{self.session_name}</cyan> | No tasks available.")
                else:
                    logger.info(f"<cyan>{self.session_name}</cyan> | Attempting to complete tasks.")

                for task in tasks:
                    task_id = task.get('id')
                    if task.get('completed'):
                        logger.info(f"<cyan>{self.session_name}</cyan> | Task <green>'{task_id}'</green> already completed.")
                        continue

                    task_response = await self.check_task(http_client=http_client, task_id=task_id)
                    if task_response.get('success'):
                        reward = task_response.get('reward', 0)
                        logger.info(f"<cyan>{self.session_name}</cyan> | ✔️ Task '{task_id}' completed. Reward: {reward}")
                        self.user_data['currentCoins'] = self.user_data.get('currentCoins', 0) + reward
                    else:
                        logger.info(f"<cyan>{self.session_name}</cyan> | Task '{task_id}' not completed or already claimed.")

                    # Add random delay between tasks
                    delay = random.uniform(settings.MIN_DELAY_BETWEEN_TASKS, settings.MAX_DELAY_BETWEEN_TASKS)
                    logger.info(f"<cyan>{self.session_name}</cyan> | Waiting for {delay:.2f} seconds before next task.")
                    await asyncio.sleep(delay)

                logger.info(f"<cyan>{self.session_name}</cyan> | Finished attempting tasks. Will try again in 8 hours.")
                await asyncio.sleep(8 * 3600)
            except Exception as error:
                logger.error(f"<cyan>{self.session_name}</cyan> | [Tasks Collection] Error: {error}")
                import traceback
                traceback.print_exc()
                await asyncio.sleep(60)

    async def check_task(self, http_client: aiohttp.ClientSession, task_id: str) -> dict:
        try:
            http_client.headers['Referer'] = 'https://qlyuker.io/tasks'
            json_data = {"taskId": task_id}
            response = await http_client.post(
                url='https://qlyuker.io/api/tasks/check',
                json=json_data
            )
            response.raise_for_status()
            response_json = await response.json()
            return response_json
        except Exception as error:
            #logger.error(f"<cyan>{self.session_name}</cyan> | Error during check_task '{task_id}': {error}")
            await asyncio.sleep(delay=3)
            return {}

    async def check_proxy(self, http_client: aiohttp.ClientSession, proxy: Proxy) -> None:
        try:
            response = await http_client.get(url='https://httpbin.org/ip', timeout=aiohttp.ClientTimeout(total=5))
            ip = (await response.json()).get('origin')
            logger.info(f"<cyan>{self.session_name}</cyan> | Proxy IP: <green>{ip}</green>")
        except Exception as error:
            logger.error(f"<cyan>{self.session_name}</cyan> | Proxy: {proxy} | Error: {error}")

    async def run(self, proxy: str | None) -> None:
        proxy_conn = ProxyConnector.from_url(proxy) if proxy else None

        async with aiohttp.ClientSession(headers=headers, connector=proxy_conn) as http_client:
            if proxy:
                await self.check_proxy(http_client=http_client, proxy=proxy)

            logger.info(f"<cyan>{self.session_name}</cyan> | Starting main bot loop.")

            daily_bonus_task = asyncio.create_task(self.collect_daily_bonus(http_client=http_client, proxy=proxy))
            tasks_collection_task = asyncio.create_task(self.collect_tasks(http_client=http_client, proxy=proxy))

            while True:
                try:
                    logger.info(f"<cyan>{self.session_name}</cyan> | Main loop iteration started.")

                    if not self.tg_web_data:
                        self.tg_web_data = await self.get_tg_web_data(proxy=proxy)
                    if not self.tg_web_data:
                        logger.error(f"<cyan>{self.session_name}</cyan> | Failed to get tg_web_data in main loop")
                        await asyncio.sleep(60)
                        continue

                    login_data = await self.login(http_client=http_client, tg_web_data=self.tg_web_data)

                    if not login_data:
                        logger.error(f"<cyan>{self.session_name}</cyan> | Login failed")
                        await asyncio.sleep(delay=3)
                        continue

                    self.user_data = login_data.get('user', {})
                    current_energy = self.user_data.get('currentEnergy', 0)
                    current_coins = self.user_data.get('currentCoins', 0)
                    max_energy = self.user_data.get('maxEnergy', 0)

                    logger.info(f"<cyan>{self.session_name}</cyan> | ✔️ Logged in successfully. Current coins: <yellow>{current_coins}</yellow>, Energy: {current_energy}/{max_energy}")

                    upgrades = await self.get_upgrades(login_data)

                    while True:
                        if current_energy <= max_energy * settings.ENERGY_THRESHOLD:
                            upgrade_response = await self.buy_upgrade(http_client=http_client, upgrade_id='restoreEnergy')
                            if upgrade_response.get('currentEnergy', 0) > current_energy:
                                current_energy = upgrade_response['currentEnergy']
                                logger.info(f"<cyan>{self.session_name}</cyan> | Energy restored to {current_energy}")
                                await asyncio.sleep(settings.SLEEP_AFTER_UPGRADE)
                            else:
                                can_upgrade = False
                                for upgrade in upgrades:
                                    upgrade_id = upgrade.get('id')
                                    next_info = upgrade.get('next', {})
                                    price = next_info.get('price', 0)
                                    if current_coins >= price and price > 0:
                                        logger.info(f"<cyan>{self.session_name}</cyan> | Try buying upgrade <green>{upgrade_id}</green> for <red>{price}</red> coins")
                                        upgrade_response = await self.buy_upgrade(http_client=http_client, upgrade_id=upgrade_id)
                                        if upgrade_response:
                                            current_coins = upgrade_response.get('currentCoins', current_coins)
                                            current_energy = upgrade_response.get('currentEnergy', current_energy)
                                            max_energy = upgrade_response.get('maxEnergy', max_energy)
                                            logger.info(f"<cyan>{self.session_name}</cyan> | Upgrade <green>{upgrade_id}</green> purchased. Current coins: <yellow>{current_coins}</yellow>")
                                            await asyncio.sleep(settings.SLEEP_AFTER_UPGRADE)
                                            can_upgrade = True
                                            break
                                if not can_upgrade:
                                    logger.info(f"<cyan>{self.session_name}</cyan> | 💤 Cannot upgrade or restore energy. Going to sleep.")
                                    await asyncio.sleep(settings.SLEEP_ON_LOW_ENERGY)
                                    break

                        taps = min(current_energy, randint(settings.MIN_TAPS, settings.MAX_TAPS))
                        response = await self.send_taps(http_client=http_client, taps=taps, current_energy=current_energy)

                        if not response:
                            logger.error(f"<cyan>{self.session_name}</cyan> | Failed to send taps")
                            await asyncio.sleep(delay=3)
                            break

                        self.user_data['currentEnergy'] = response.get('currentEnergy', current_energy)
                        self.user_data['currentCoins'] = response.get('currentCoins', current_coins)
                        current_energy = self.user_data['currentEnergy']
                        current_coins = self.user_data['currentCoins']

                        logger.info(f"<cyan>{self.session_name}</cyan> | Sent <light-yellow>{taps}</light-yellow> taps. Current coins: <yellow>{current_coins}</yellow>, Energy: {current_energy}/{max_energy}")

                        await asyncio.sleep(randint(settings.MIN_SLEEP_BETWEEN_TAPS, settings.MAX_SLEEP_BETWEEN_TAPS))

                    self.tg_web_data = None

                except InvalidSession as error:
                    raise error

                except Exception as error:
                    logger.error(f"<cyan>{self.session_name}</cyan> | Unknown error: {error}")
                    import traceback
                    traceback.print_exc()
                    await asyncio.sleep(delay=3)


async def run_tapper(tg_client: Client, proxy: str | None):
    try:
        await Tapper(tg_client=tg_client).run(proxy=proxy)
    except InvalidSession:
        logger.error(f"{tg_client.name} | Invalid Session")
