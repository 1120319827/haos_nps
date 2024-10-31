from homeassistant.components.switch import SwitchEntity
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, CoordinatorEntity
from datetime import timedelta
import logging
import aiohttp
import hashlib
import ssl

_LOGGER = logging.getLogger(__name__)

ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE
url = ""
key = ""

def md5_encryption(data):
    md5 = hashlib.md5()
    md5.update(data.encode('utf-8'))
    return md5.hexdigest()

async def async_setup_entry(hass, entry, async_add_entities):
    try:
        global url
        global key
        url = entry.data["url"]
        key = entry.data["key"]
        if entry.options:
            url = entry.options.get("url", url)
            key = entry.options.get("key", key)

        coordinator = MySwitchCoordinator(hass, entry)
        await coordinator.async_config_entry_first_refresh()

        entry_id = md5_encryption(entry.entry_id)[:10]

        entities = []
        for k, data in coordinator.data.items():
            entities.append(MySwitch(coordinator, data, entry_id, entry))

        async_add_entities(entities)
    except Exception as e:
        _LOGGER.error("错误: %s", str(e))

async def get_auth_key():
    _ssl = None
    if url.startswith("https"):
        _ssl = ssl_context
    async with aiohttp.ClientSession() as session:
        async with session.get(url + "/auth/gettime", ssl=_ssl) as response:
            time_data = await response.json()
            _LOGGER.debug(f"time_data: {time_data}")
            time = time_data['time']
            return { "auth_key": md5_encryption(key + str(time)), "time": time}

async def post(uri, data):
    """"""
    _ssl = None
    if url.startswith("https"):
        _ssl = ssl_context

    auth_data = await get_auth_key()
    data["auth_key"] = auth_data["auth_key"]
    data["timestamp"] = auth_data["time"]

    async with aiohttp.ClientSession() as session:
        async with session.post(url + uri, data=data, ssl=_ssl) as response:
            json = await response.json()
    _LOGGER.debug(f"post: {uri}, data: {json}")
    return json

class MySwitchCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, entry):
        super().__init__(
            hass,
            _LOGGER,
            name="NPS Switch Coordinator",
            update_interval=timedelta(seconds=15),
        )

    async def _async_update_data(self):
        params={
            "start": 0,
            "limit": 100,
            "type": "tcp"
        }
        data = await post("/index/gettunnel", params)
        result = {}
        for data in data['rows']:
            result[data['Id']] = data
        return result


class MySwitch(CoordinatorEntity, SwitchEntity):

    def __init__(self, coordinator, data, entry_id, entry):
        super().__init__(coordinator)
        name = data["Remark"]
        self._data = data
        self._coordinator = coordinator
        self._id = data["Id"]

        self._attr_unique_id = '{}.nps_{}_{}'.format('switch', entry_id, self._id).lower()
        self.entity_id = self._attr_unique_id
        self._name = name if name and name != '' else self._id

    @property
    def device_info(self):
        _client = self._data["Client"]
        _id = _client["Id"]
        _name = _client["Remark"]
        if _name == "":
            _name = _id
        _manufacturer = _client["Addr"]
        _sw_version = _client["Version"]
        _last_time = _client["LastOnlineTime"]
        _model = "离线"
        if _client["Status"]:
            _model = "在线"
        return DeviceInfo(
            identifiers={("nps", _id)},
            name=_name,
            manufacturer=str(_id) +":"+ _manufacturer,
            model=_model + ": " + _last_time,
            sw_version=_sw_version,
        )

    @property
    def name(self):
        return f"{self._name}"

    @property
    def unique_id(self):
        return self._attr_unique_id

    # @property
    # def available(self):
    #     return self._data["Client"]["Status"]

    @property
    def extra_state_attributes(self):
        _attr = {
            "状态": "开放" if self._data["Status"] else "关闭",
            "运行状态": "开放" if self._data["RunStatus"] else "关闭",
            "客户端状态": "在线" if self._data["Client"]["Status"] else "离线",
            "目标": self._data["Target"]["TargetStr"],
            "端口": str(self._data["Port"]),
            "客户端名称":str(self._data["Client"]["Remark"])
        }
        return _attr

    @property
    def is_on(self):
        self._data = self._coordinator.data[self._id]
        return self._data["Status"]

    async def async_turn_on(self, **kwargs):
        """开"""
        data = {
            "id": self._id
        }
        await post("/index/start", data)
        await self._coordinator.async_request_refresh()
        self._data = self._coordinator.data[self._id]
        await self.async_update_ha_state(True)

    async def async_turn_off(self, **kwargs):
        """关"""
        data = {
            "id": self._id
        }
        await post("/index/stop", data)
        await self._coordinator.async_request_refresh()
        self._data = self._coordinator.data[self._id]
        await self.async_update_ha_state(True)

    async def async_toggle(self, **kwargs):
        """切换"""
        data = {
            "id": self._id
        }
        if self._data["Status"]:
            await post("/index/stop", data)
        else:
            await post("/index/start", data)
        await self._coordinator.async_request_refresh()
        await self.async_update_ha_state(True)

    # async def async_remove(self):
    #     """删除"""
    #     data = {
    #         "id": self._id
    #     }
    #     await post("/index/del", data)
    #
    #     # 其他清理操作
    #     await super().async_remove()

