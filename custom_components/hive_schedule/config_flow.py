"""Config flow for Hive Schedule Manager integration v2.0 - depends on official Hive."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class HiveScheduleConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Hive Schedule Manager."""

    VERSION = 2

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        
        # Check if official Hive integration is available
        if "hive" not in self.hass.data:
            return self.async_abort(
                reason="hive_not_configured",
                description_placeholders={
                    "error": "Official Hive integration not found. Please install and configure it first."
                }
            )
        
        # Check if already configured
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()
        
        if user_input is not None:
            _LOGGER.info("Creating Hive Schedule Manager entry")
            return self.async_create_entry(
                title="Hive Schedule Manager",
                data={}
            )
        
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({}),
            description_placeholders={
                "info": "This integration uses your existing Hive integration for authentication. No credentials needed!"
            }
        )


class CannotConnect(Exception):
    """Error to indicate we cannot connect."""


class InvalidAuth(Exception):
    """Error to indicate there is invalid auth."""