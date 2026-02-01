"""Config flow for Hive Schedule Manager integration v2.1"""
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
        self._login_response = None

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
                
                # Store login response for MFA
                self._login_response = tokens
                
                # Check if MFA is required
                if tokens and tokens.get("ChallengeName") == "SMS_MFA":
                    _LOGGER.info("MFA required, proceeding to MFA step")
                    return await self.async_step_mfa()
                
                # Authentication successful without MFA
                _LOGGER.info("Authentication successful without MFA")
                return await self._create_entry(auth_result=tokens)

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
                result = await self._hive_auth.sms_2fa(mfa_code, self._login_response)
                
                _LOGGER.info("MFA verification successful")
                _LOGGER.debug("MFA result keys: %s", result.keys() if isinstance(result, dict) else "not a dict")
                
                # The result contains the final authentication tokens including RefreshToken
                return await self._create_entry(auth_result=result)

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

    async def _create_entry(self, auth_result: dict) -> FlowResult:
        """Create the config entry with auth tokens."""
        # Check if already configured
        await self.async_set_unique_id(self._username.lower())
        self._abort_if_unique_id_configured()
        
        _LOGGER.info("Creating config entry for %s", self._username)
        
        # Extract the critical tokens for 30-day re-authentication
        auth_tokens = auth_result.get('AuthenticationResult', {})
        
        entry_data = {
            CONF_USERNAME: self._username,
            CONF_PASSWORD: self._password,
            # Store all tokens for refresh capability
            "access_token": auth_tokens.get('AccessToken'),
            "id_token": auth_tokens.get('IdToken'),
            "refresh_token": auth_tokens.get('RefreshToken'),  # 30-day token!
            "token_type": auth_tokens.get('TokenType', 'Bearer'),
            "expires_in": auth_tokens.get('ExpiresIn', 3600),
        }
        
        _LOGGER.debug("Stored tokens: access_token=%s, id_token=%s, refresh_token=%s",
                     "present" if entry_data["access_token"] else "missing",
                     "present" if entry_data["id_token"] else "missing", 
                     "present" if entry_data["refresh_token"] else "missing")
        
        return self.async_create_entry(
            title=self._username,
            data=entry_data
        )