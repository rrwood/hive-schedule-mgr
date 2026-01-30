"""Config flow for Hive Schedule Manager integration v2.0 standalone."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from apyhiveapi import Auth

from homeassistant import config_entries
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN, CONF_MFA_CODE

_LOGGER = logging.getLogger(__name__)


class HiveScheduleConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Hive Schedule Manager."""

    VERSION = 2

    def __init__(self):
        """Initialize the config flow."""
        self._username = None
        self._password = None
        self._hive_auth = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step - username and password."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._username = user_input[CONF_USERNAME]
            self._password = user_input[CONF_PASSWORD]

            try:
                # Try to authenticate using apyhiveapi
                self._hive_auth = Auth(self._username, self._password)
                tokens = await self._hive_auth.login()
                
                # Check if MFA is required
                if tokens and tokens.get("ChallengeName") == "SMS_MFA":
                    _LOGGER.info("MFA required, proceeding to MFA step")
                    return await self.async_step_mfa()
                
                # Authentication successful without MFA
                _LOGGER.info("Authentication successful")
                return await self._create_entry()

            except Exception as ex:
                _LOGGER.error("Authentication error: %s", ex)
                errors["base"] = "invalid_auth"

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

    async def async_step_mfa(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle MFA code entry."""
        errors: dict[str, str] = {}

        if user_input is not None:
            mfa_code = user_input[CONF_MFA_CODE]

            try:
                # Complete MFA challenge
                # Try different apyhiveapi signatures
                try:
                    # Method 1: Just MFA code
                    await self._hive_auth.sms_2fa(mfa_code)
                except TypeError:
                    # Method 2: With session (might be stored differently)
                    if hasattr(self._hive_auth, 'session'):
                        await self._hive_auth.sms_2fa(mfa_code, self._hive_auth.session)
                    else:
                        # Method 3: Re-raise the original error
                        raise
                
                _LOGGER.info("MFA verification successful")
                return await self._create_entry()

            except Exception as ex:
                _LOGGER.error("MFA verification error: %s", ex)
                _LOGGER.debug("MFA error details", exc_info=True)
                errors["base"] = "invalid_mfa"

        return self.async_show_form(
            step_id="mfa",
            data_schema=vol.Schema({
                vol.Required(CONF_MFA_CODE): str,
            }),
            errors=errors,
            description_placeholders={
                "username": self._username,
            },
        )

    async def _create_entry(self) -> FlowResult:
        """Create the config entry."""
        # Check if already configured
        await self.async_set_unique_id(self._username.lower())
        self._abort_if_unique_id_configured()
        
        _LOGGER.info("Creating config entry for %s", self._username)
        
        return self.async_create_entry(
            title=self._username,
            data={
                CONF_USERNAME: self._username,
                CONF_PASSWORD: self._password,
            }
        )