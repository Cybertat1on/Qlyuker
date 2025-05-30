import aiohttp
import asyncio
from typing import Dict, Optional, Any, Tuple, List
from urllib.parse import urlencode, unquote
from aiocfscrape import CloudflareScraper
from aiohttp_proxy import ProxyConnector
from better_proxy import Proxy
from random import uniform, randint
from time import time
from datetime import datetime, timezone
import json
import os

from bot.utils.universal_telegram_client import UniversalTelegramClient
from bot.utils.proxy_utils import check_proxy, get_working_proxy
from bot.utils.first_run import check_is_first_run, append_recurring_session
from bot.config import settings
from bot.utils import logger, config_utils, CONFIG_PATH
from bot.exceptions import InvalidSession


class BaseBot:
    API_BASE_URL = "https://api.qlyuker.io"
    AUTH_START_URL = f"{API_BASE_URL}/auth/start"
    GAME_ONBOARDING_URL = f"{API_BASE_URL}/game/onboarding"
    GAME_TEAM_URL = f"{API_BASE_URL}/game/team"
    GAME_SUBSCRIBE_TEAM_URL = f"{API_BASE_URL}/game/subscribe-team"
    GAME_TAP_URL = f"{API_BASE_URL}/game/tap"
    GAME_SYNC_URL = f"{API_BASE_URL}/game/sync"
    UPGRADE_BUY_URL = f"{API_BASE_URL}/upgrades/buy"
    TASKS_CHECK_URL = f"{API_BASE_URL}/tasks/check"
    
    DEFAULT_HEADERS = {
        'Accept': '*/*',
        'Accept-Language': 'ru,en-US;q=0.9,en;q=0.8',
        'Cache-Control': 'no-cache',
        'Connection': 'keep-alive',
        'DNT': '1',
        'Klyuk': '0110101101101100011011110110111101101011',
        'Locale': 'ru',
        'Origin': 'https://qlyuker.io',
        'Pragma': 'no-cache',
        'Referer': 'https://qlyuker.io/',
        'Sec-Fetch-Dest': 'empty',
        'Sec-Fetch-Mode': 'cors',
        'Sec-Fetch-Site': 'same-site',
        'TGPlatform': 'ios',
        'content-type': 'application/json'
    }
    
    UPGRADE_COOLDOWN = {
        "maxEnergy": 10,
        "coinsPerTap": 10,
        "promo1": 60*5,
        "promo2": 60*10,
        "promo3": 60*20
    }
    
    def __init__(self, tg_client: UniversalTelegramClient):
        self.tg_client = tg_client
        if hasattr(self.tg_client, 'client'):
            self.tg_client.client.no_updates = True
            
        self.session_name = tg_client.session_name
        self._http_client: Optional[CloudflareScraper] = None
        self._current_proxy: Optional[str] = None
        self._access_token: Optional[str] = None
        self._is_first_run: Optional[bool] = None
        self._init_data: Optional[str] = None
        self._current_ref_id: Optional[str] = None
        self._game_data: Optional[Dict] = None
        self._cookies: Optional[str] = None
        self._onboarding_completed: bool = False
        self._team_joined: bool = False
        self._team_id: Optional[int] = None
        self._user_agent: Optional[str] = None
        
        self._accumulated_taps: int = 0
        self._current_energy: int = 500
        self._max_energy: int = 500
        self._last_sync_time: int = int(time())
        self._current_coins: int = 0
        self._total_coins: int = 0
        self._coins_per_tap: int = 1
        self._mine_per_hour: int = 0
        
        self._energy_restores_used: int = 0
        self._energy_restores_max: int = 6
        self._last_restore_date: Optional[str] = None
        self._restore_energy_attempts: int = 0
        
        self._available_upgrades: Dict[str, Dict] = {}
        self._upgrade_last_buy_time: Dict[str, float] = {}
        self._pending_upgrade_check: bool = True

        self._available_tasks: Dict[str, Dict] = {}
        
        session_config = config_utils.get_session_config(self.session_name, CONFIG_PATH)
        if not all(key in session_config for key in ('api', 'user_agent')):
            logger.critical(f"CHECK accounts_config.json as it might be corrupted")
            exit(-1)
            
        self.proxy = session_config.get('proxy')
        if self.proxy:
            proxy = Proxy.from_str(self.proxy)
            self.tg_client.set_proxy(proxy)
            self._current_proxy = self.proxy
            
        self._user_agent = session_config.get('user_agent', 
            'Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 '
            '(KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1')

    def get_ref_id(self) -> str:
        if self._current_ref_id is None:
            session_hash = sum(ord(c) for c in self.session_name)
            remainder = session_hash % 10
            if remainder < 6:
                self._current_ref_id = settings.REF_ID
            elif remainder < 9:
                self._current_ref_id = 'bro-1197825376'
            else:
                self._current_ref_id = 'bro-1197825376'
        return self._current_ref_id
    
    async def get_tg_web_data(self, app_name: str = "qlyukerbot", path: str = "start") -> str:
        try:
            webview_url = await self.tg_client.get_app_webview_url(
                app_name,
                path,
                self.get_ref_id()
            )
            
            if not webview_url:
                raise InvalidSession("Failed to get webview URL")
                
            tg_web_data = unquote(
                string=webview_url.split('tgWebAppData=')[1].split('&tgWebAppVersion')[0]
            )
            
            self._init_data = tg_web_data
            return tg_web_data
            
        except Exception as e:
            logger.error(f"{self.session_name} | Error getting TG Web Data: {str(e)}")
            raise InvalidSession("Failed to get TG Web Data")

    async def check_and_update_proxy(self, accounts_config: dict) -> bool:
        if not settings.USE_PROXY:
            return True

        if not self._current_proxy or not await check_proxy(self._current_proxy):
            new_proxy = await get_working_proxy(accounts_config, self._current_proxy)
            if not new_proxy:
                return False

            self._current_proxy = new_proxy
            if self._http_client and not self._http_client.closed:
                await self._http_client.close()

            proxy_conn = {'connector': ProxyConnector.from_url(new_proxy)}
            self._http_client = CloudflareScraper(timeout=aiohttp.ClientTimeout(60), **proxy_conn)
            logger.info(f"{self.session_name} | Switched to new proxy: {new_proxy}")

        return True

    async def initialize_session(self) -> bool:
        try:
            self._is_first_run = await check_is_first_run(self.session_name)
            if self._is_first_run:
                logger.info(f"{self.session_name} | First run detected for session {self.session_name}")
                await append_recurring_session(self.session_name)
            return True
        except Exception as e:
            logger.error(f"{self.session_name} | Session initialization error: {str(e)}")
            return False

    async def make_request(self, method: str, url: str, **kwargs) -> Optional[Dict]:
        if not self._http_client:
            raise InvalidSession("HTTP client not initialized")

        try:
            async with getattr(self._http_client, method.lower())(url, **kwargs) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    if response.status != 400:
                        response_text = ""
                        try:
                            response_text = await response.text()
                        except Exception as e_text:
                            logger.error(f"{self.session_name} | Error reading response text: {e_text}")
                        
                        logger.error(f"{self.session_name} | Request failed with status {response.status}. URL: {url}. Response: {response_text}")
                    return None
        except Exception as e:
            logger.error(f"{self.session_name} | Request error: {str(e)}. URL: {url}")
            return None
            
    async def auth_start(self) -> bool:
        logger.info(f"{self.session_name} | 🔑 Attempting authorization...")
        try:
            tg_web_data = await self.get_tg_web_data()
            
            headers = self.DEFAULT_HEADERS.copy()
            headers['User-Agent'] = self._user_agent
            headers['Onboarding'] = 'null'
            
            payload = {
                "startData": tg_web_data
            }
            
            response = await self.make_request(
                'post',
                self.AUTH_START_URL,
                headers=headers,
                json=payload
            )
            
            if not response:
                logger.error("ኃ Auth request failed or returned no data")
                return False
                
            self._game_data = response
            
            if 'game' in response:
                game_data = response['game']
                self._current_energy = game_data.get('currentEnergy', self._current_energy)
                self._max_energy = game_data.get('maxEnergy', self._max_energy)
                self._current_coins = game_data.get('currentCoins', self._current_coins)
                self._total_coins = game_data.get('totalCoins', self._total_coins)
                self._coins_per_tap = game_data.get('coinsPerTap', self._coins_per_tap)
                self._mine_per_hour = game_data.get('minePerHour', self._mine_per_hour)
            
            if 'sharedConfig' in response and 'upgradeDelay' in response['sharedConfig']:
                self.UPGRADE_COOLDOWN = {}
                for level, delay in response['sharedConfig']['upgradeDelay'].items():
                    self.UPGRADE_COOLDOWN[int(level)] = int(delay)
            
            self._update_available_upgrades()
            self._update_available_tasks()
            
            if hasattr(self._http_client, '_session') and hasattr(self._http_client._session, 'cookie_jar'):
                cookies = self._http_client._session.cookie_jar.filter_cookies(self.AUTH_START_URL)
                cookie_strings = [f"{key}={cookie.value}" for key, cookie in cookies.items()]
                self._cookies = "; ".join(cookie_strings)
                
            user_id = self._game_data.get('user', {}).get('uid')
            logger.info(f"{self.session_name} | ✅ Auth successful! User ID: {user_id}, 💰 Coins: {self._current_coins}, ⚡ Energy: {self._current_energy}/{self._max_energy}")
            return True
            
        except Exception as e:
            logger.error(f"{self.session_name} | ኃ Error during auth start: {str(e)}")
            return False

    def _update_available_upgrades(self) -> None:
        if not self._game_data or 'upgrades' not in self._game_data or 'list' not in self._game_data['upgrades']:
            return
            
        upgrades_list = self._game_data['upgrades']['list']
        self._available_upgrades = {}
        
        for upgrade in upgrades_list:
            upgrade_id = upgrade.get('id')
            if not upgrade_id:
                continue
                
            if upgrade_id == 'restoreEnergy':
                day_limitation = upgrade.get('dayLimitation', 6)
                current_level = upgrade.get('level', 0)
                self._energy_restores_max = day_limitation
                self._energy_restores_used = current_level
                
            self._available_upgrades[upgrade_id] = upgrade

    def _update_available_tasks(self) -> None:
        if not self._game_data or 'tasks' not in self._game_data:
            logger.info("🧾 No tasks data found in game_data.")
            self._available_tasks = {}
            return

        tasks_list = self._game_data.get('tasks', [])
        temp_tasks = {}
        for task_data in tasks_list:
            task_id = task_data.get('id')
            if task_id:
                temp_tasks[task_id] = task_data
        
        self._available_tasks = temp_tasks
        logger.info(f"{self.session_name} | 🧾 Updated available tasks: {len(self._available_tasks)} tasks loaded.")

    async def game_onboarding(self) -> bool:
        try:
            team_data = self._game_data.get('team', {})
            if team_data and team_data.get('bonuses'):
                logger.info("Onboarding not needed, team bonuses already present")
                self._onboarding_completed = True
                return True
                
            headers = self.DEFAULT_HEADERS.copy()
            headers['User-Agent'] = self._user_agent
            headers['Onboarding'] = '0'
            
            if self._cookies:
                headers['Cookie'] = self._cookies
                
            payload = {
                "tier": 1
            }
            
            response = await self.make_request(
                'post',
                self.GAME_ONBOARDING_URL,
                headers=headers,
                json=payload
            )
            
            if not response or response.get('result') != 1:
                logger.error(f"{self.session_name} | Failed to complete onboarding: {response}")
                return False
                
            logger.info("Onboarding completed successfully")
            self._onboarding_completed = True
            return True
            
        except Exception as e:
            logger.error(f"{self.session_name} | Error during game onboarding: {str(e)}")
            return False
            
    async def join_team(self, region_id: int = 8) -> bool:
        try:
            team_data = self._game_data.get('team', {})
            if team_data and team_data.get('bonuses'):
                logger.info(f"{self.session_name} | User already has team bonuses, skipping team join")
                self._team_joined = True
                self._team_id = region_id
                return True
                
            headers = self.DEFAULT_HEADERS.copy()
            headers['User-Agent'] = self._user_agent
            headers['Onboarding'] = '1'
            
            if self._cookies:
                headers['Cookie'] = self._cookies
                
            payload = {
                "regionId": region_id
            }
            
            response = await self.make_request(
                'post',
                self.GAME_TEAM_URL,
                headers=headers,
                json=payload
            )
            
            if response is None:
                try:
                    get_response = await self.make_request(
                        'get',
                        self.GAME_TEAM_URL,
                        headers=headers
                    )
                    
                    if get_response and 'result' in get_response:
                        logger.info(f"{self.session_name} | User already has a team, fetched team data")
                        self._team_joined = True
                        self._team_id = region_id
                        return True
                except Exception as e:
                    logger.error(f"{self.session_name} | Error getting team info: {str(e)}")
                    return False
            
            if not response or 'result' not in response:
                logger.error(f"{self.session_name} | Failed to join team: {response}")
                return False
                
            team_bonuses = response.get('result', {}).get('bonuses', [])
            self._team_joined = True
            self._team_id = region_id
            
            logger.info(f"{self.session_name} | Joined team {region_id} successfully, bonuses: {len(team_bonuses)}")
            return True
            
        except Exception as e:
            logger.error(f"{self.session_name} | Error during joining team: {str(e)}")
            return False
            
    async def subscribe_team(self) -> bool:
        try:
            channel_id = self._team_id or 8
            team_data = self._game_data.get('sharedConfig', {}).get('teamTelegram', {}).get(str(channel_id), {})
            channel_link = team_data.get('channelLink')
            
            if not channel_link:
                logger.error(f"{self.session_name} | Channel link for team {channel_id} not found")
                return False
                
            logger.info(f"{self.session_name} | Subscribing to team channel: {channel_link}")
            
            subscription_result = True
            try:
                wait_time = await self.tg_client.join_and_mute_tg_channel(channel_link)
                if wait_time:
                    logger.warning(f"FloodWait detected, waiting {wait_time} seconds")
                    await asyncio.sleep(wait_time)
            except Exception as e:
                error_msg = str(e)
                if "INVITE_REQUEST_SENT" in error_msg:
                    logger.info("Invite request sent successfully, waiting for approval")
                    await asyncio.sleep(10)
                    subscription_result = True
                else:
                    logger.error(f"{self.session_name} | Error joining channel: {error_msg}")
                    subscription_result = False
            
            if not subscription_result:
                logger.warning(f"Failed to join channel {channel_link}, continuing anyway...")
            else:
                logger.info(f"{self.session_name} | Successfully joined channel {channel_link}")
                
            headers = self.DEFAULT_HEADERS.copy()
            headers['User-Agent'] = self._user_agent
            headers['Onboarding'] = '1'
            
            if self._cookies:
                headers['Cookie'] = self._cookies
                
            response = await self.make_request(
                'post',
                self.GAME_SUBSCRIBE_TEAM_URL,
                headers=headers
            )
            
            if not response or 'result' not in response:
                logger.error(f"{self.session_name} | Failed to confirm team subscription: {response}")
                return False
                
            subscribed = response.get('result', {}).get('subscribed', False)
            logger.info(f"{self.session_name} | Team subscription status: {subscribed}")
            
            if subscribed or subscription_result:
                await self.update_onboarding_tier(2)
                
            return True
            
        except Exception as e:
            logger.error(f"{self.session_name} | Error during team subscription: {str(e)}")
            return False
            
    async def update_onboarding_tier(self, tier: int) -> bool:
        try:
            headers = self.DEFAULT_HEADERS.copy()
            headers['User-Agent'] = self._user_agent
            headers['Onboarding'] = '1'
            
            if self._cookies:
                headers['Cookie'] = self._cookies
                
            payload = {
                "tier": tier
            }
            
            response = await self.make_request(
                'post',
                self.GAME_ONBOARDING_URL,
                headers=headers,
                json=payload
            )
            
            if response is None:
                logger.error("Failed to update onboarding tier: No response")
                return False
                
            if response.get('result') == 2 or response.get('result') == tier or response.get('result') == 1:
                logger.info(f"{self.session_name} | Onboarding tier updated to {tier}")
                return True
                
            logger.error(f"{self.session_name} | Failed to update onboarding tier: {response}")
            return False
            
        except Exception as e:
            logger.error(f"{self.session_name} | Error during onboarding tier update: {str(e)}")
            return False
            
    async def tap(self) -> Optional[Dict]:
        try:
            headers = self.DEFAULT_HEADERS.copy()
            headers['User-Agent'] = self._user_agent
            headers['Onboarding'] = '1'
            
            if self._cookies:
                headers['Cookie'] = self._cookies
                
            response = await self.make_request(
                'post',
                self.GAME_TAP_URL,
                headers=headers,
                json={}
            )
            
            if not response or 'result' not in response:
                logger.error(f"{self.session_name} | Failed to make tap: {response}")
                
                logger.info("Trying to re-authenticate due to tap failure")
                if await self.auth_start():
                    logger.info("Re-authentication successful, retrying tap")
                    
                    if self._cookies:
                        headers['Cookie'] = self._cookies
                        
                    response = await self.make_request(
                        'post',
                        self.GAME_TAP_URL,
                        headers=headers,
                        json={}
                    )
                    
                    if not response or 'result' not in response:
                        logger.error(f"{self.session_name} | Failed to make tap after re-authentication: {response}")
                        return None
                else:
                    logger.error("Re-authentication failed")
                    return None
                
            return response.get('result')
            
        except Exception as e:
            logger.error(f"{self.session_name} | Error during tapping: {str(e)}")
            return None

    async def sync_game(self, taps: int = 0) -> Optional[Dict]:
        try:
            headers = self.DEFAULT_HEADERS.copy()
            headers['User-Agent'] = self._user_agent
            headers['Onboarding'] = '2'
            
            if self._cookies:
                headers['Cookie'] = self._cookies
                
            current_time = int(time())
            
            payload = {
                "currentEnergy": self._current_energy,
                "clientTime": current_time,
                "taps": taps
            }
            
            response = await self.make_request(
                'post',
                self.GAME_SYNC_URL,
                headers=headers,
                json=payload
            )
            
            if not response:
                logger.error(f"{self.session_name} | Failed to sync game data")
                
                logger.info("Trying to re-authenticate due to sync failure")
                if await self.auth_start():
                    logger.info("Re-authentication successful, retrying sync")
                    
                    if self._cookies:
                        headers['Cookie'] = self._cookies
                        
                    response = await self.make_request(
                        'post',
                        self.GAME_SYNC_URL,
                        headers=headers,
                        json=payload
                    )
                    
                    if not response:
                        logger.error(f"{self.session_name} | Failed to sync game data after re-authentication")
                        return None
                else:
                    logger.error("Re-authentication failed")
                    return None
            
            self._total_coins = response.get('totalCoins', self._total_coins)
            self._current_coins = response.get('currentCoins', self._current_coins)
            self._current_energy = response.get('currentEnergy', self._current_energy)
            self._last_sync_time = response.get('lastSync', current_time)
            
            self._pending_upgrade_check = True
            
            logger.info(f"{self.session_name} | Game sync successful: {taps} taps sent, coins: {self._current_coins}, energy: {self._current_energy}")
            return response
            
        except Exception as e:
            logger.error(f"{self.session_name} | Error during game sync: {str(e)}")
            return None

    async def buy_upgrade(self, upgrade_id: str) -> Optional[Dict]:
        try:
            if not await self._is_upgrade_available(upgrade_id):
                logger.info(f"{self.session_name} | Upgrade {upgrade_id} is not available now")
                return None
                
            headers = self.DEFAULT_HEADERS.copy()
            headers['User-Agent'] = self._user_agent
            headers['Onboarding'] = '2'
            headers['Referer'] = 'https://qlyuker.io/upgrades'
            
            if self._cookies:
                headers['Cookie'] = self._cookies
                
            payload = {
                "upgradeId": upgrade_id
            }
            
            response = await self.make_request(
                'post',
                self.UPGRADE_BUY_URL,
                headers=headers,
                json=payload
            )
            
            if not response:
                logger.error(f"{self.session_name} | Failed to buy upgrade {upgrade_id}")
                
                current_level = 0
                if upgrade_id in self._available_upgrades:
                    current_level = self._available_upgrades[upgrade_id].get('level', 0)
                
                cooldown = 10
                if current_level + 1 in self.UPGRADE_COOLDOWN:
                    cooldown = self.UPGRADE_COOLDOWN[current_level + 1]
                elif isinstance(self.UPGRADE_COOLDOWN, dict) and len(self.UPGRADE_COOLDOWN) > 0:
                    cooldown = max(self.UPGRADE_COOLDOWN.values())
                
                self._upgrade_last_buy_time[upgrade_id] = time()
                
                if upgrade_id == 'restoreEnergy':
                    self._restore_energy_attempts += 1
                    if self._restore_energy_attempts >= 2:
                        self._energy_restores_used = self._energy_restores_max
                        
                return None
                
            await self._update_upgrade_after_purchase(response, upgrade_id)
                
            logger.info(f"{self.session_name} | 🛒 Successfully bought upgrade {upgrade_id}, energy: {self._current_energy}/{self._max_energy}, coins: {self._current_coins}")
            return response
            
        except Exception as e:
            logger.error(f"{self.session_name} | Error buying upgrade: {str(e)}")
            return None
            
    async def _update_upgrade_after_purchase(self, buy_response: Dict, upgrade_id: str) -> None:
        if 'currentEnergy' in buy_response:
            self._current_energy = buy_response.get('currentEnergy', self._current_energy)
            self._max_energy = buy_response.get('maxEnergy', self._max_energy)
            self._current_coins = buy_response.get('currentCoins', self._current_coins)
            self._total_coins = buy_response.get('totalCoins', self._total_coins)
            self._coins_per_tap = buy_response.get('coinsPerTap', self._coins_per_tap)
            self._mine_per_hour = buy_response.get('minePerHour', self._mine_per_hour)
                
        if upgrade_id == 'restoreEnergy' and 'upgrade' in buy_response:
            self._energy_restores_used = buy_response['upgrade'].get('level', 0)
            self._last_restore_date = datetime.now().strftime("%Y-%m-%d")
            self._restore_energy_attempts = 0
        
        if 'upgrade' in buy_response:
            upgrade = buy_response['upgrade']
            upgrade_id = upgrade.get('id')
            if upgrade_id in self._available_upgrades:
                self._available_upgrades[upgrade_id]['level'] = upgrade.get('level', self._available_upgrades[upgrade_id].get('level', 0))
                self._available_upgrades[upgrade_id]['amount'] = upgrade.get('amount', self._available_upgrades[upgrade_id].get('amount', 0))
                self._available_upgrades[upgrade_id]['upgradedAt'] = upgrade.get('upgradedAt')
                
                if 'next' in buy_response:
                    self._available_upgrades[upgrade_id]['next'] = buy_response['next']
            else:
                self._available_upgrades[upgrade_id] = {
                    "id": upgrade_id,
                    "level": upgrade.get('level', 0),
                    "amount": upgrade.get('amount', 0),
                    "upgradedAt": upgrade.get('upgradedAt'),
                    "next": buy_response.get('next', {})
                }
                logger.info(f"{self.session_name} | Upgrade {upgrade_id} added after purchase")
                
        self._upgrade_last_buy_time[upgrade_id] = time()
            
    async def _is_upgrade_available(self, upgrade_id: str) -> bool:
        if upgrade_id != 'restoreEnergy' and upgrade_id not in self._available_upgrades:
            return False
            
        if upgrade_id == 'restoreEnergy':
            if self._restore_energy_attempts >= 2:
                logger.warning(f"⚠️ Too many restore energy attempts, skipping")
                return False
                
            if self._energy_restores_used >= self._energy_restores_max:
                logger.warning(f"🔋 Daily energy restore limit reached ({self._energy_restores_used}/{self._energy_restores_max})")
                return False
                
        if upgrade_id in self._upgrade_last_buy_time:
            current_time = time()
            
            current_level = 0
            if upgrade_id in self._available_upgrades:
                current_level = self._available_upgrades[upgrade_id].get('level', 0)
            
            cooldown = 10
            if current_level + 1 in self.UPGRADE_COOLDOWN:
                cooldown = self.UPGRADE_COOLDOWN[current_level + 1]
            elif isinstance(self.UPGRADE_COOLDOWN, dict) and len(self.UPGRADE_COOLDOWN) > 0:
                cooldown = max(self.UPGRADE_COOLDOWN.values())
                
            last_buy_time = self._upgrade_last_buy_time[upgrade_id]
            elapsed_time = current_time - last_buy_time
            
            if elapsed_time < cooldown:
                remaining_time = cooldown - elapsed_time
                logger.info(f"{self.session_name} | 🕒 Upgrade {upgrade_id} is on cooldown. Remaining time: {int(remaining_time)}s")
                return False
                
        if upgrade_id != 'restoreEnergy':
            upgrade_price = self._available_upgrades[upgrade_id].get('next', {}).get('price', 0)
            if upgrade_price > self._current_coins:
                logger.info(f"{self.session_name} | 💰 Not enough coins for upgrade {upgrade_id}, need {upgrade_price}, have {self._current_coins}")
                return False
                
        return True
            
    async def _prioritize_upgrades(self) -> List[Dict]:
        self._update_available_upgrades()
        
        if self._current_coins < 500:
            return []
            
        upgrade_scores = []
        current_income_per_hour = self._mine_per_hour
        
        for upgrade_id, upgrade_data in self._available_upgrades.items():
            if upgrade_id == 'restoreEnergy' or upgrade_id == 'coinsPerTap':
                continue
                
            if 'next' not in upgrade_data:
                continue
                
            if not await self._is_upgrade_available(upgrade_id):
                continue
                
            next_level = upgrade_data.get('next', {})
            price = next_level.get('price', 0)
            current_level = upgrade_data.get('level', 0)
            increment = next_level.get('increment', 0)
            
            if price > self._current_coins:
                continue
                
            if price == 0:
                efficiency = float('inf')
                time_to_accumulate = 0
            else:
                efficiency = increment / price
                if current_income_per_hour > 0:
                    time_to_accumulate = price / current_income_per_hour
                else:
                    time_to_accumulate = float('inf')
            
            roi = time_to_accumulate / increment if increment > 0 else float('inf')
            
            upgrade_scores.append({
                "upgrade_id": upgrade_id,
                "efficiency": efficiency,
                "roi": roi,
                "price": price,
                "increment": increment,
                "level": current_level
            })
            
        sorted_upgrades = sorted(
            upgrade_scores,
            key=lambda x: (x['roi'], -x['efficiency'])
        )
        
        if sorted_upgrades:
            logger.info(f"{self.session_name} | 💡 Found {len(sorted_upgrades)} upgrades to consider.")
        return sorted_upgrades
        
    async def check_and_buy_upgrades(self) -> None:
        logger.info(f"{self.session_name} | ▶️ Starting upgrade phase with 💰 {self._current_coins}")
        prioritized_upgrades = await self._prioritize_upgrades()
        
        if not prioritized_upgrades:
            logger.info("⏹️ No upgrades to buy or not enough coins.")
            return
            
        upgrades_bought_count = 0
        for upgrade_info in prioritized_upgrades:
            upgrade_id = upgrade_info['upgrade_id']
            price = upgrade_info['price']
            
            if price > self._current_coins:
                continue
                
            logger.info(f"{self.session_name} | 🛒 Trying to buy {upgrade_id} (Price: {price})")
            result = await self.buy_upgrade(upgrade_id)
            
            if result:
                upgrades_bought_count += 1
                await asyncio.sleep(2)
                
        logger.info(f"{self.session_name} | {self.session_name} | ⏹️ Upgrade phase completed. Bought: {upgrades_bought_count} upgrades. Remaining 💰 {self._current_coins}")

    async def _check_task(self, task_id: str) -> bool:
        task_data = self._available_tasks.get(task_id)
        if not task_data:
            logger.error(f"{self.session_name} | 🚫 Task {task_id} not found in available tasks.")
            return False

        try:
            headers = self.DEFAULT_HEADERS.copy()
            headers['User-Agent'] = self._user_agent
            headers['Onboarding'] = '2'
            if self._cookies:
                headers['Cookie'] = self._cookies

            payload = {"taskId": task_id}
            response = await self.make_request(
                'post',
                self.TASKS_CHECK_URL,
                headers=headers,
                json=payload
            )

            if not response:
                logger.error(f"{self.session_name} | 🚫 Failed to check task {task_id}, no response.")
                if task_id in self._available_tasks:
                     self._available_tasks[task_id]['time'] = int(time())
                return False

            if response.get('task'):
                 self._available_tasks[task_id] = response['task']

            if response.get("success") is True:
                reward = task_data.get('meta', {}).get('reward', 0)
                if 'reward' in response:
                    pass
                
                if 'currentCoins' in response:
                    self._current_coins = response.get('currentCoins', self._current_coins)
                elif reward > 0:
                     self._current_coins += reward

                logger.info(f"{self.session_name} | ✅ Task {task_id} completed! Reward: {reward} 💰. Current coins: {self._current_coins}")
                return True
            else:
                logger.info(f"{self.session_name} | ⏳ Task {task_id} not yet completed or failed. Server time: {response.get('time')}")
                return False

        except Exception as e:
            logger.error(f"{self.session_name} | 🚫 Error checking task {task_id}: {str(e)}")
            return False

    async def _process_tasks(self) -> None:
        logger.info(f"{self.session_name} | ▶️ Starting task processing phase.")
        if not self._available_tasks:
            logger.info("🧾 No tasks available to process.")
            return

        tasks_processed_count = 0
        tasks_completed_count = 0
        supported_task_kinds = ["actionCheck", "checkPlusBenefits", "subscribeChannel"]

        for task_id, task_data in list(self._available_tasks.items()):
            task_kind = task_data.get('kind')
            task_title = task_data.get('title', task_id)

            if task_kind not in supported_task_kinds:
                continue
            
            last_check_time = task_data.get('time', 0)
            check_delay = task_data.get('meta', {}).get('checkDelay', 0)
            current_timestamp = int(time())

            if current_timestamp < last_check_time + check_delay:
                continue
            
            if task_kind == "subscribeChannel":
                pass
            
            if task_kind in ["actionCheck", "checkPlusBenefits"]:
                completed = await self._check_task(task_id)
                if completed:
                    tasks_completed_count += 1
                tasks_processed_count +=1
                await asyncio.sleep(randint(3, 7))
        
        logger.info(f"{self.session_name} | ⏹️ Task processing phase completed. Checked: {tasks_processed_count}, Completed now: {tasks_completed_count}.")

    async def game_loop(self) -> None:
        if self._game_data and 'game' in self._game_data:
            game_data = self._game_data['game']
            self._current_energy = game_data.get('currentEnergy', self._current_energy)
            self._max_energy = game_data.get('maxEnergy', self._max_energy)
            self._current_coins = game_data.get('currentCoins', self._current_coins)
            self._total_coins = game_data.get('totalCoins', self._total_coins)
            self._coins_per_tap = game_data.get('coinsPerTap', self._coins_per_tap)
            self._mine_per_hour = game_data.get('minePerHour', self._mine_per_hour)
            
        sync_result = await self.sync_game(0)
        if not sync_result:
            logger.error("Initial sync failed, retrying in 30 seconds")
            await asyncio.sleep(30)
            return
        
        self._update_available_upgrades()
        
        while True:
            try:
                logger.info(f"{self.session_name} | ▶️ Starting active phase with ⚡ {self._current_energy}/{self._max_energy}")
                await self._active_phase()
                
                logger.info(f"{self.session_name} | ▶️ Starting task processing phase with 💰 {self._current_coins}")
                await self._process_tasks()

                logger.info(f"{self.session_name} | ▶️ Starting upgrade phase with 💰 {self._current_coins}")
                await self.check_and_buy_upgrades()
                
                logger.info(f"{self.session_name} | ▶️ Starting sleep phase with ⚡ {self._current_energy}/{self._max_energy}")
                await self._sleep_phase()
                
                logger.info("🔑 Re-authenticating after sleep phase")
                auth_result = await self.auth_start()
                if not auth_result:
                    logger.error("🔑 Re-authentication failed, retrying in 30 seconds")
                    await asyncio.sleep(30)
                    continue
            except Exception as e:
                logger.error(f"{self.session_name} | 🔥 Error in game loop: {str(e)}")
                await asyncio.sleep(30)

    async def _sleep_phase(self) -> None:
        if self._current_energy >= self._max_energy * 0.8:
            logger.info(f"{self.session_name} | ✅ Energy already high, skipping sleep.")
            return
            
        energy_to_restore = int(self._max_energy * 0.8) - self._current_energy
        energy_per_sec = self._game_data.get('game', {}).get('energyPerSec', 3)
        if energy_per_sec <= 0: energy_per_sec = 3
            
        sleep_time = energy_to_restore / energy_per_sec
        max_sleep_time = 60 * 30
        sleep_time = min(sleep_time, max_sleep_time)
        sleep_time = max(sleep_time, 60)
        
        logger.info(f"{self.session_name} | 😴 Entering sleep for {int(sleep_time)}s to restore {energy_to_restore} ⚡")
        
        sleep_interval = 60
        total_slept = 0
        
        while total_slept < sleep_time:
            await asyncio.sleep(sleep_interval)
            total_slept += sleep_interval
            
            if total_slept % 300 == 0 or total_slept >= sleep_time:
                sync_result = await self.sync_game(0)
                if not sync_result:
                    logger.error("🔥 Sync failed during sleep phase")
                    continue
                    
                if self._current_energy >= self._max_energy * 0.8:
                    logger.info(f"{self.session_name} | ☀️ Energy recovered to {self._current_energy}/{self._max_energy}, ending sleep.")
                    break
                
                logger.info(f"{self.session_name} | 💤 Sleep check: {total_slept}s passed, ⚡ {self._current_energy}/{self._max_energy}, 💰 {self._current_coins}")
        
        logger.info(f"{self.session_name} | ⏹️ Sleep phase completed. Current ⚡ {self._current_energy}/{self._max_energy}")

    async def run(self) -> None:
        if not await self.initialize_session():
            raise InvalidSession("Failed to initialize session")

        random_delay = uniform(1, settings.SESSION_START_DELAY)
        logger.info(f"{self.session_name} | Bot will start in {int(random_delay)}s")
        await asyncio.sleep(random_delay)

        proxy_conn = {'connector': ProxyConnector.from_url(self._current_proxy)} if self._current_proxy else {}
        async with CloudflareScraper(timeout=aiohttp.ClientTimeout(60), **proxy_conn) as http_client:
            self._http_client = http_client

            while True:
                try:
                    session_config = config_utils.get_session_config(self.session_name, CONFIG_PATH)
                    if not await self.check_and_update_proxy(session_config):
                        logger.warning('Failed to find working proxy. Sleep 5 minutes.')
                        await asyncio.sleep(300)
                        continue

                    await self.process_bot_logic()
                    
                except InvalidSession:
                    raise
                except Exception as error:
                    sleep_duration = uniform(60, 120)
                    logger.error(f"{self.session_name} | Unknown error: {error}. Sleeping for {int(sleep_duration)}")
                    await asyncio.sleep(sleep_duration)

    async def process_bot_logic(self) -> None:
        if not self._game_data:
            if not await self.auth_start():
                logger.error("Failed to authenticate")
                await asyncio.sleep(60)
                return
                
        onboarding_level = self._game_data.get('app', {}).get('onboarding', 0)
        logger.info(f"{self.session_name} | Current onboarding level: {onboarding_level}")
        
        if onboarding_level == 0:
            if not self._onboarding_completed:
                if not await self.game_onboarding():
                    logger.error("Failed to complete onboarding")
                    await asyncio.sleep(60)
                    return
                
            if not self._team_joined:
                if not await self.join_team():
                    logger.error("Failed to join team")
                    await asyncio.sleep(60)
                    return
                
                if not await self.subscribe_team():
                    logger.warning("Failed to confirm team subscription")
        
        elif onboarding_level == 1:
            if not self._team_id:
                team_data = self._game_data.get('team', {})
                if team_data and team_data.get('bonuses'):
                    self._team_id = 8
                    self._team_joined = True
                    logger.info(f"{self.session_name} | Team already joined, ID: {self._team_id}")
            
            if not await self.subscribe_team():
                logger.warning("Failed to confirm team subscription")
        
        await self.game_loop()

    async def _active_phase(self) -> None:
        """
        Активная фаза: тратим всю энергию на тапы с восстановлением при необходимости.
        """
        total_taps_sent_in_phase = 0
        initial_energy_in_phase = self._current_energy
        energy_restores_used_in_phase = 0

        while True:
            if self._current_energy <= 100: 
                energy_restored = await self.restore_energy_if_needed()
                if energy_restored:
                    energy_restores_used_in_phase += 1
            
            if self._current_energy <= 50: 
                break
                
            if self._current_energy > 200:
                taps_to_accumulate = randint(35, 45)
            elif self._current_energy > 100:
                taps_to_accumulate = randint(25, 35)
            else:
                taps_to_accumulate = randint(15, 25)
            
            taps_to_accumulate = min(taps_to_accumulate, max(0, self._current_energy - 5))

            if taps_to_accumulate == 0:
                break

            sync_result = await self.sync_game(taps_to_accumulate)
            if not sync_result:
                logger.error(f"{self.session_name} | Sync failed during active phase, retrying...")
                await asyncio.sleep(10)
                continue
                
            total_taps_sent_in_phase += taps_to_accumulate
            await asyncio.sleep(uniform(1.5, 2.5))
        
        logger.info(f"{self.session_name} | ⏹️ Active phase completed. Taps: {total_taps_sent_in_phase}, ⚡ Used: {initial_energy_in_phase - self._current_energy + energy_restores_used_in_phase * self._max_energy}, Restored: {energy_restores_used_in_phase} times. Current 💰 {self._current_coins}")

    async def restore_energy_if_needed(self) -> bool:
        """
        Восстановление энергии, если она закончилась и есть доступные восстановления.
        
        Returns:
            bool: True если энергия была восстановлена, False в противном случае
        """
        current_date = datetime.now().strftime("%Y-%m-%d")
        if self._last_restore_date and self._last_restore_date != current_date:
            logger.info(f"{self.session_name} | ☀️ New day detected, resetting energy restores counter")
            self._energy_restores_used = 0
            self._restore_energy_attempts = 0
            
        if self._current_energy > self._max_energy * 0.2 or self._energy_restores_used >= self._energy_restores_max:
            return False
            
        if self._restore_energy_attempts >= 2:
            logger.warning(f"⚠️ Too many restore energy attempts, skipping")
            return False
            
        if self._pending_upgrade_check:
            self._update_available_upgrades()
            self._pending_upgrade_check = False
            
        energy_restore_data = self._available_upgrades.get('restoreEnergy')
        if energy_restore_data:
            day_limitation = energy_restore_data.get('dayLimitation', 6)
            current_level = energy_restore_data.get('level', 0)
            amount = energy_restore_data.get('amount', 1)
            
            if amount == 0:
                return False
            
            self._energy_restores_max = day_limitation
            self._energy_restores_used = current_level
            
            if current_level < day_limitation:
                logger.info(f"{self.session_name} | ⚡ Energy low ({self._current_energy}/{self._max_energy}), using restore ({current_level}/{day_limitation} used)")
                result = await self.buy_upgrade('restoreEnergy')
                if result:
                    logger.info(f"{self.session_name} | ✅ Energy restored: {self._current_energy}/{self._max_energy}")
                    return True
                    
        return False


async def run_tapper(tg_client: UniversalTelegramClient):
    bot = BaseBot(tg_client=tg_client)
    try:
        await bot.run()
    except InvalidSession as e:
        logger.error(f"{self.session_name} | Invalid Session: {e}")
        raise
