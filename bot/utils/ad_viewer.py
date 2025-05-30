from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Optional, List, Any, Callable, Union, TypeVar
from abc import ABC, abstractmethod
import asyncio
import aiohttp
from random import uniform
from urllib.parse import urlencode
import json

from bot.utils.logger import logger, log_error
from bot.exceptions import AdViewError


T = TypeVar('T')


@dataclass
class AdEventConfig:
    """Конфигурация событий рекламы"""
    event_type: str
    tracking_type_id: str
    min_delay: float = 0.0
    max_delay: float = 0.0
    required: bool = True
    retry_count: int = 1


@dataclass
class AdConfig:
    """Расширенная конфигурация для просмотра рекламы"""
    # Базовые настройки
    min_view_duration: float = 15.0
    max_view_duration: float = 20.0
    min_delay_between_ads: float = 2.0
    max_delay_between_ads: float = 5.0
    max_retries: int = 3
    retry_delay: float = 5.0
    
    # Расширенные настройки
    user_agent: str = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"
    platform: str = "MacIntel"
    language: str = "ru"
    connection_type: str = "1"
    device_platform: str = "android"
    
    # Настройки событий
    events: List[AdEventConfig] = field(default_factory=lambda: [
        AdEventConfig("render", "13", 0.0, 0.5),
        AdEventConfig("show", "0", 1.0, 2.0),
        AdEventConfig("reward", "14", 0.0, 0.5, True, 3)
    ])
    
    # Дополнительные параметры запросов
    additional_params: Dict[str, str] = field(default_factory=dict)
    
    # Настройки прокси
    proxy_url: Optional[str] = None
    proxy_auth: Optional[Dict[str, str]] = None


class AdEventHandler(ABC):
    """Абстрактный обработчик событий рекламы"""
    
    @abstractmethod
    async def on_ad_start(self, ad_data: Dict[str, Any]) -> None:
        """Called before the ad viewing starts"""
        pass
    
    @abstractmethod
    async def on_ad_complete(self, ad_data: Dict[str, Any], success: bool) -> None:
        """Called after the ad viewing is completed"""
        pass
    
    @abstractmethod
    async def on_ad_error(self, error: Exception, attempt: int) -> None:
        """Called when an error occurs"""
        pass


class DefaultAdEventHandler(AdEventHandler):
    """Базовый обработчик событий рекламы"""
    
    async def on_ad_start(self, ad_data: Dict[str, Any]) -> None:
        logger.info("Ad viewing started")
    
    async def on_ad_complete(self, ad_data: Dict[str, Any], success: bool) -> None:
        status = "successfully" if success else "unsuccessfully"
        logger.info(f"Ad viewing completed {status}")
    
    async def on_ad_error(self, error: Exception, attempt: int) -> None:
        log_error(f"Error during ad viewing (attempt {attempt}): {str(error)}")


class AdViewer:
    """Универсальный класс для управления просмотром рекламы"""
    
    def __init__(
        self,
        base_url: str,
        event_url: str,
        block_id: str,
        http_client: aiohttp.ClientSession,
        access_token: str,
        user_id: Union[int, str],
        config: Optional[AdConfig] = None,
        event_handler: Optional[AdEventHandler] = None,
        custom_headers: Optional[Dict[str, str]] = None
    ) -> None:
        self._base_url = base_url
        self._event_url = event_url
        self._block_id = block_id
        self._http_client = http_client
        self._access_token = access_token
        self._user_id = str(user_id)
        self._config = config or AdConfig()
        self._event_handler = event_handler or DefaultAdEventHandler()
        self._custom_headers = custom_headers or {}
        
        # Валидация конфигурации
        self._validate_config()

    def _validate_config(self) -> None:
        """Валидация конфигурации"""
        if self._config.min_view_duration > self._config.max_view_duration:
            raise ValueError("min_view_duration cannot be greater than max_view_duration")
        if self._config.min_delay_between_ads > self._config.max_delay_between_ads:
            raise ValueError("min_delay_between_ads cannot be greater than max_delay_between_ads")

    def _get_base_params(self) -> Dict[str, str]:
        """Получение базовых параметров для запросов"""
        params = {
            "blockId": self._block_id,
            "tg_id": self._user_id,
            "tg_platform": self._config.device_platform,
            "platform": self._config.platform,
            "language": self._config.language,
            "top_domain": self._base_url.split('/')[2],
            "connectiontype": self._config.connection_type,
            **self._config.additional_params
        }
        return {k: v for k, v in params.items() if v is not None}

    def _get_headers(self, additional_headers: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        """Формирование заголовков запроса"""
        headers = {
            "Authorization": f"Bearer {self._access_token}",
            "User-Agent": self._config.user_agent,
            "Accept": "application/json",
            "Accept-Language": self._config.language,
            **self._custom_headers
        }
        if additional_headers:
            headers.update(additional_headers)
        return headers

    async def _make_request(
        self,
        url: str,
        method: str = "GET",
        params: Optional[Dict[str, str]] = None,
        data: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        timeout: Optional[float] = None
    ) -> Dict[str, Any]:
        """Универсальный метод для выполнения HTTP-запросов"""
        try:
            request_kwargs = {
                "method": method,
                "url": url,
                "headers": self._get_headers(headers),
                "timeout": aiohttp.ClientTimeout(total=timeout) if timeout else None
            }
            
            if params:
                request_kwargs["params"] = params
            if data:
                request_kwargs["json"] = data
            if self._config.proxy_url:
                request_kwargs["proxy"] = self._config.proxy_url
                if self._config.proxy_auth:
                    request_kwargs["proxy_auth"] = aiohttp.BasicAuth(**self._config.proxy_auth)

            async with self._http_client.request(**request_kwargs) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise AdViewError(
                        f"Request error {response.status}: {error_text}"
                    )
                return await response.json()
                
        except asyncio.TimeoutError:
            raise AdViewError("Request timeout exceeded")
        except Exception as e:
            raise AdViewError(f"Error during request execution: {str(e)}")

    async def _get_ad(self) -> Dict[str, Any]:
        """Получение рекламного объявления"""
        params = {
            **self._get_base_params(),
            "request_id": str(int(datetime.now(timezone.utc).timestamp() * 1000))
        }
        return await self._make_request(self._base_url, params=params)

    async def _process_ad_event(
        self,
        event_config: AdEventConfig,
        tracking_data: Dict[str, str]
    ) -> bool:
        """Обработка события рекламы с учетом конфигурации"""
        record = tracking_data.get(event_config.event_type)
        if not record:
            if event_config.required:
                raise AdViewError(f"Missing required event: {event_config.event_type}")
            return True

        for attempt in range(event_config.retry_count):
            try:
                params = {
                    "record": record,
                    "type": event_config.event_type,
                    "trackingtypeid": event_config.tracking_type_id
                }
                await self._make_request(self._event_url, params=params)
                
                if event_config.max_delay > 0:
                    await asyncio.sleep(
                        uniform(event_config.min_delay, event_config.max_delay)
                    )
                return True
                
            except AdViewError as e:
                if attempt == event_config.retry_count - 1:
                    if event_config.required:
                        raise
                    return False
                await asyncio.sleep(self._config.retry_delay)
        
        return False

    async def _simulate_ad_view(self, tracking_data: Dict[str, str]) -> bool:
        """Расширенная симуляция просмотра рекламы"""
        try:
            for event_config in self._config.events:
                if not await self._process_ad_event(event_config, tracking_data):
                    return False

            view_duration = uniform(
                self._config.min_view_duration,
                self._config.max_view_duration
            )
            logger.info(f"Ad viewed for {view_duration:.1f} seconds")
            await asyncio.sleep(view_duration)
            
            return True

        except Exception as e:
            log_error(f"Error during ad viewing: {str(e)}")
            return False

    def _extract_tracking_data(self, ad_data: Dict[str, Any]) -> Dict[str, str]:
        """Извлечение данных отслеживания из ответа API"""
        try:
            tracking_list = ad_data.get("banner", {}).get("trackings", [])
            return {
                tracking["name"]: tracking["value"]
                for tracking in tracking_list
                if "name" in tracking and "value" in tracking
            }
        except Exception as e:
            raise AdViewError(f"Invalid ad data format: {str(e)}")

    async def view_ads(
        self,
        count: int,
        success_callback: Optional[Callable[[Dict[str, Any]], Any]] = None
    ) -> int:
        """
        Просмотр указанного количества рекламных объявлений
        
        Args:
            count: Количество рекламных объявлений для просмотра
            success_callback: Функция обратного вызова после успешного просмотра
            
        Returns:
            int: Количество успешно просмотренных объявлений
        """
        successful_views = 0
        
        for i in range(count):
            logger.info(f"Starting ad viewing {i + 1}/{count}")
            
            for attempt in range(self._config.max_retries):
                try:
                    # Получение рекламы
                    ad_data = await self._get_ad()
                    await self._event_handler.on_ad_start(ad_data)
                    
                    tracking_data = self._extract_tracking_data(ad_data)
                    success = await self._simulate_ad_view(tracking_data)
                    
                    await self._event_handler.on_ad_complete(ad_data, success)
                    
                    if success:
                        successful_views += 1
                        if success_callback:
                            await success_callback(ad_data)
                        logger.info(f"Successfully viewed ad {i + 1}/{count}")
                        break
                    
                except Exception as e:
                    await self._event_handler.on_ad_error(e, attempt + 1)
                    if attempt < self._config.max_retries - 1:
                        await asyncio.sleep(self._config.retry_delay)
                    continue
            
            # Задержка между просмотрами
            if i < count - 1:
                delay = uniform(
                    self._config.min_delay_between_ads,
                    self._config.max_delay_between_ads
                )
                await asyncio.sleep(delay)
        
        return successful_views 