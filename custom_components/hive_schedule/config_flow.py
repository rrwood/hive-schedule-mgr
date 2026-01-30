"""Config flow for Hive Schedule Manager integration v2.0 using apyhiveapi."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from apyhiveapi import Hive
from apyhiveapi.helper.hive_exceptions import HiveReauthRequired, HiveApiError

from homeassistant import config_entries
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import aiohttp_client

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class HiveScheduleConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Hive Schedule Manager."""

    VERSION = 2

    def __init__(self):
        """Initialize the config flow."""
        self._username = None
        self._password = None
        self._hive = None
        self._reconfig_entry = None

    @staticmethod
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return HiveScheduleOptionsFlow(config_entry)

    async def async_step_reconfigure(self, user_input: dict[str, Any] | None = None):
        """Handle reconfiguration of the integration."""
        self._reconfig_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        
        # Pre-fill with existing username
        if self._reconfig_entry:
            self._username = self._reconfig_entry.data.get(CONF_USERNAME)
            self._password = self._reconfig_entry.data.get(CONF_PASSWORD)
        
        return await self.async_step_user(user_input)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step - username and password."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._username = user_input[CONF_USERNAME]
            self._password = user_input[CONF_PASSWORD]

            try:
                # Try to authenticate
                result = await self._try_authenticate()
                
                if result.get("success"):
                    # Authentication successful
                    return await self._create_or_update_entry()
                else:
                    errors["base"] = "invalid_auth"

            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception as ex:
                _LOGGER.exception("Unexpected exception: %s", ex)
                errors["base"] = "unknown"

        # Show form
        data_schema = vol.Schema({
            vol.Required(CONF_USERNAME, default=self._username or ""): str,
            vol.Required(CONF_PASSWORD, default=""): str,
        })

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
        )

    async def _create_or_update_entry(self) -> FlowResult:
        """Create a new entry or update existing one."""
        # Prepare data to store
        entry_data = {
            CONF_USERNAME: self._username,
            CONF_PASSWORD: self._password,
        }
        
        _LOGGER.info("Storing Hive credentials (apyhiveapi handles tokens)")
        
        # Check if entry already exists
        existing_entry = await self.async_set_unique_id(self._username.lower())
        
        if existing_entry:
            # Update existing entry
            _LOGGER.info("Updating existing config entry for %s", self._username)
            self.hass.config_entries.async_update_entry(
                existing_entry,
                data=entry_data
            )
            # Reload the entry to use new credentials
            await self.hass.config_entries.async_reload(existing_entry.entry_id)
            return self.async_abort(reason="reauth_successful")
        
        # Create new entry
        _LOGGER.info("Creating new config entry for %s", self._username)
        return self.async_create_entry(
            title=self._username,
            data=entry_data
        )

    async def _try_authenticate(self) -> dict[str, Any]:
        """Try to authenticate - returns status dict."""
        try:
            # Get aiohttp session
            websession = aiohttp_client.async_get_clientsession(self.hass)
            
            # Create Hive instance
            self._hive = Hive(websession=websession)
            
            # Attempt login
            login_success = await self._hive.session.login(self._username, self._password)
            
            if not login_success:
                _LOGGER.error("Login failed - check credentials")
                raise InvalidAuth
            
            # If we get here without exception, auth was successful
            _LOGGER.info("Authentication successful")
            return {"success": True}
                
        except HiveReauthRequired:
            _LOGGER.error("Re-authentication required")
            raise InvalidAuth
        except HiveApiError as err:
            _LOGGER.error("Hive API error: %s", err)
            error_str = str(err).lower()
            if "incorrect" in error_str or "invalid" in error_str or "not authorized" in error_str:
                raise InvalidAuth
            else:
                raise CannotConnect
        except Exception as err:
            _LOGGER.error("Auth error: %s", err)
            error_str = str(err).lower()
            if "incorrect" in error_str or "invalid" in error_str or "not authorized" in error_str:
                raise InvalidAuth
            else:
                raise CannotConnect


class HiveScheduleOptionsFlow(config_entries.OptionsFlow):
    """Handle options flow for reconfiguration."""

    def __init__(self, config_entry):
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Manage the options - show reconfigure button."""
        if user_input is not None:
            # Trigger reconfiguration
            return self.async_create_entry(title="", data={})

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({}),
            description_placeholders={
                "info": "Click Submit to re-authenticate with your Hive account"
            }
        )


class CannotConnect(Exception):
    """Error to indicate we cannot connect."""


class InvalidAuth(Exception):
    """Error to indicate there is invalid auth."""