from homeassistant.config_entries import ConfigEntry
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
import logging


_LOGGER = logging.getLogger(__name__)

DOMAIN = "nps"

async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    return True


async def async_setup_entry(hass: HomeAssistant, entry: config_entries.ConfigEntry) -> bool:
    if not entry.update_listeners:
        entry.add_update_listener(async_update_options)


    await hass.config_entries.async_forward_entry_setup(entry, "switch")

    return True

async def async_update_options(hass: HomeAssistant, config_entry: config_entries.ConfigEntry):
    await hass.config_entries.async_reload(config_entry.entry_id)

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    await hass.config_entries.async_forward_entry_unload(entry, "switch")
    return True