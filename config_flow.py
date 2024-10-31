import voluptuous as vol
from homeassistant import config_entries
import logging
from homeassistant.core import callback
import hashlib
import ssl
import aiohttp

_LOGGER = logging.getLogger(__name__)

class ConfigFlow(config_entries.ConfigFlow, domain="nps"):

    @staticmethod
    @callback
    def async_get_options_flow(entry: config_entries.ConfigEntry):
        return OptionsFlowHandler(entry)

    async def async_step_user(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title=user_input["name"], data=user_input)

        return self.async_show_form(step_id="user", data_schema=vol.Schema({
            vol.Required("name", description="名称"): str,
            vol.Required("url", description="API地址"): str,
            vol.Required("key", description="令牌"): str,
        }))

class OptionsFlowHandler(config_entries.OptionsFlow):
    def __init__(self, config_entry):
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        return await self.async_step_user()

    async def async_step_user(self, user_input=None):
        name = self.config_entry.data["name"]
        url = self.config_entry.data["url"]
        token = self.config_entry.data["key"]
        if self.config_entry.options:
            name = self.config_entry.options.get("name", name)
            url = self.config_entry.options.get("url", url)
            token = self.config_entry.options.get("key", token)

        if user_input is not None:
            new_title = user_input["name"]
            self.hass.config_entries.async_update_entry(
                entry=self.config_entry, title=new_title, options=user_input
            )
            dict2 = {k: v for k, v in user_input.items() if v}
            if any(value in dict2.keys() for value in {"添加TCP名称","服务端端口","目标(ip:端口)","客户端ID"}):
                if not {"添加TCP名称","服务端端口","目标(ip:端口)","客户端ID"}.issubset(dict2.keys()):
                    return self.async_show_form(
                        step_id="user",
                        data_schema=vol.Schema({
                            vol.Required("name", description="名称", default=name): str,
                            vol.Required("url", description="API地址", default=url): str,
                            vol.Required("key", description="令牌", default=token): str,
                            vol.Optional("添加TCP名称", default=get_val(user_input, "添加TCP名称")): str,
                            vol.Optional("客户端ID", default=get_val(user_input, "客户端ID")): str,
                            vol.Optional("服务端端口", default=get_val(user_input, "服务端端口")): str,
                            vol.Optional("目标(ip:端口)", default=get_val(user_input, "目标(ip:端口)")): str,
                        }),
                        errors={"添加TCP名称": "添加TCP则都为必填项"}
                    )
                data = {
                    "type": "tcp",
                    "remark": user_input["添加TCP名称"],
                    "port": user_input["服务端端口"],
                    "target": user_input["目标(ip:端口)"],
                    "client_id": user_input["客户端ID"],
                }
                await add_post(url, token, data)

            return self.async_create_entry(title=name, data=user_input)

        return self.async_show_form(step_id="user", data_schema=vol.Schema({
            vol.Required("name", description="名称", default=name): str,
            vol.Required("url", description="API地址", default=url): str,
            vol.Required("key", description="令牌", default=token):  str,
            vol.Optional("添加TCP名称"): str,
            vol.Optional("客户端ID"): str,
            vol.Optional("服务端端口"): str,
            vol.Optional("目标(ip:端口)"): str,
        }))

ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE

def get_val(data, key):
    if data.get(key):
        return data[key]
    return ""

def md5_encryption(data):
    md5 = hashlib.md5()
    md5.update(data.encode('utf-8'))
    return md5.hexdigest()

async def get_auth_key(url, key):
    _ssl = None
    if url.startswith("https"):
        _ssl = ssl_context
    async with aiohttp.ClientSession() as session:
        async with session.get(url + "/auth/gettime", ssl=_ssl) as response:
            time_data = await response.json()
            time = time_data['time']
            return { "auth_key": md5_encryption(key + str(time)), "time": time}

async def add_post(url, key, data):
    """"""
    _ssl = None
    if url.startswith("https"):
        _ssl = ssl_context

    auth_data = await get_auth_key(url, key)
    data["auth_key"] = auth_data["auth_key"]
    data["timestamp"] = auth_data["time"]

    async with aiohttp.ClientSession() as session:
        async with session.post(url+"/index/add", data=data, ssl=_ssl) as response:
            json = await response.json()
    _LOGGER.debug(f"post: {url}/index/add, data: {data} result: {json}")
    return json