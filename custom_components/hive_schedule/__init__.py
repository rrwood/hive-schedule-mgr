"""
Hive Schedule Manager Integration v2.1
Uses RefreshToken for 30-day authentication without MFA
"""
from __future__ import annotations

import logging
import json
import os
from datetime import datetime, timedelta
from typing import Any

import voluptuous as vol
import yaml
import aiofiles

from apyhiveapi import Auth

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.storage import Store

from .const import (
    DOMAIN,
    SERVICE_SET_DAY,
    ATTR_NODE_ID,
    ATTR_DAY,
    ATTR_SCHEDULE,
    ATTR_PROFILE,
)

_LOGGER = logging.getLogger(__name__)
VERSION = "2.1.0"
PROFILES_FILE = "hive_schedule_profiles.yaml"
TOKEN_STORAGE_VERSION = 1
TOKEN_STORAGE_KEY = "hive_schedule_tokens"

# Service schema
SET_DAY_SCHEMA = vol.Schema({
    vol.Required(ATTR_NODE_ID): cv.string,
    vol.Required(ATTR_DAY): vol.In([
        "monday", "tuesday", "wednesday", "thursday", 
        "friday", "saturday", "sunday"
    ]),
    vol.Optional(ATTR_PROFILE): cv.string,
    vol.Optional(ATTR_SCHEDULE): vol.All(cv.ensure_list, [{
        vol.Required("time"): cv.string,
        vol.Required("temp"): vol.Coerce(float),
    }])
})


async def _load_profiles(hass: HomeAssistant) -> dict:
    """Load schedule profiles from YAML file."""
    config_path = hass.config.path(PROFILES_FILE)
    
    if not os.path.exists(config_path):
        await _create_default_profiles_file(config_path)
    
    try:
        async with aiofiles.open(config_path, 'r') as file:
            content = await file.read()
            profiles = yaml.safe_load(content) or {}
            return profiles
    except Exception as e:
        _LOGGER.error("Failed to load profiles: %s", e)
        return _get_builtin_profiles()


def _get_builtin_profiles() -> dict:
    """Get built-in default profiles."""
    return {
        "workday": [
            {"time": "05:20", "temp": 18.5},
            {"time": "07:00", "temp": 18.0},
            {"time": "16:30", "temp": 19.5},
            {"time": "21:45", "temp": 16.0},
        ],
        "weekend": [
            {"time": "07:30", "temp": 18.5},
            {"time": "09:00", "temp": 18.0},
            {"time": "16:30", "temp": 19.5},
            {"time": "22:00", "temp": 16.0},
        ],
    }


async def _create_default_profiles_file(config_path: str):
    """Create default profiles file."""
    default_content = """# Hive Schedule Profiles
workday:
  - time: "05:20"
    temp: 18.5
  - time: "07:00"
    temp: 18.0
  - time: "16:30"
    temp: 19.5
  - time: "21:45"
    temp: 16.0

weekend:
  - time: "07:30"
    temp: 18.5
  - time: "09:00"
    temp: 18.0
  - time: "16:30"
    temp: 19.5
  - time: "22:00"
    temp: 16.0
"""
    try:
        async with aiofiles.open(config_path, 'w') as file:
            await file.write(default_content)
    except Exception as e:
        _LOGGER.error("Failed to create default profiles: %s", e)


def _validate_schedule(schedule: list) -> bool:
    """Validate schedule format."""
    if not isinstance(schedule, list) or len(schedule) == 0:
        raise ValueError("Schedule must be a non-empty list")
    
    for entry in schedule:
        if not isinstance(entry, dict) or "time" not in entry or "temp" not in entry:
            raise ValueError("Each entry must have 'time' and 'temp'")
        
        # Validate time
        try:
            hours, minutes = entry["time"].split(":")
            if not (0 <= int(hours) <= 23 and 0 <= int(minutes) <= 59):
                raise ValueError
        except:
            raise ValueError(f"Invalid time: {entry['time']}")
        
        # Validate temp
        temp = float(entry["temp"])
        if not (5.0 <= temp <= 32.0):
            raise ValueError(f"Temperature {temp}°C out of range")
    
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Hive Schedule Manager from config entry."""
    
    _LOGGER.info("=" * 80)
    _LOGGER.info("Hive Schedule Manager v%s", VERSION)
    _LOGGER.info("Using RefreshToken for 30-day authentication")
    _LOGGER.info("=" * 80)
    
    # Get credentials and tokens
    username = entry.data[CONF_USERNAME]
    password = entry.data[CONF_PASSWORD]
    
    # Initialize token storage
    store = Store(hass, TOKEN_STORAGE_VERSION, f"{TOKEN_STORAGE_KEY}_{entry.entry_id}")
    
    # Load tokens from storage or config entry
    stored_data = await store.async_load() or {}
    
    # Calculate initial expiry if not present (assume tokens are fresh from config flow)
    initial_expiry = stored_data.get("token_expiry")
    if not initial_expiry and entry.data.get("access_token"):
        # Tokens just created in config flow - set expiry to 55 minutes from now
        initial_expiry = (datetime.now() + timedelta(seconds=3300)).isoformat()
    
    token_data = {
        "access_token": stored_data.get("access_token") or entry.data.get("access_token"),
        "id_token": stored_data.get("id_token") or entry.data.get("id_token"),
        "refresh_token": stored_data.get("refresh_token") or entry.data.get("refresh_token"),
        "token_expiry": initial_expiry,
    }
    
    _LOGGER.info("Loaded tokens: access=%s, id=%s, refresh=%s",
                 "present" if token_data["access_token"] else "missing",
                 "present" if token_data["id_token"] else "missing",
                 "present" if token_data["refresh_token"] else "missing")
    
    # Load profiles
    profiles = await _load_profiles(hass)
    _LOGGER.info("Loaded %d schedule profiles", len(profiles))
    
    # Get aiohttp session
    websession = aiohttp_client.async_get_clientsession(hass)
    
    # Store integration data
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "username": username,
        "password": password,
        "token_data": token_data,
        "store": store,
        "profiles": profiles,
        "websession": websession,
    }
    
    # Register service
    async def handle_set_day(call: ServiceCall) -> None:
        """Handle set_day_schedule service call."""
        node_id = call.data[ATTR_NODE_ID]
        day = call.data[ATTR_DAY]
        profile_name = call.data.get(ATTR_PROFILE)
        custom_schedule = call.data.get(ATTR_SCHEDULE)
        
        # Get schedule
        if profile_name:
            if profile_name not in profiles:
                raise HomeAssistantError(f"Unknown profile: {profile_name}")
            day_schedule = profiles[profile_name]
        elif custom_schedule:
            day_schedule = custom_schedule
        else:
            raise HomeAssistantError("Either 'profile' or 'schedule' required")
        
        # Validate
        _validate_schedule(day_schedule)
        
        _LOGGER.info("Setting %s schedule on node %s", day, node_id)
        
        # Convert to Hive format
        hive_schedule = []
        for entry in day_schedule:
            hours, minutes = entry["time"].split(":")
            hive_schedule.append({
                "value": {"target": entry["temp"]},
                "start": int(hours) * 60 + int(minutes)
            })
        
        schedule_data = {"schedule": {day: hive_schedule}}
        
        # Get valid token (refresh if needed)
        token = await _get_valid_token(hass, entry.entry_id)
        
        # Make API request
        url = f"https://beekeeper-uk.hivehome.com/1.0/nodes/{node_id}"
        headers = {
            "Content-Type": "application/json",
            "Authorization": token,  # Use IdToken (plain, no Bearer)
        }
        
        async with websession.post(url, json=schedule_data, headers=headers) as response:
            if response.status == 200:
                _LOGGER.info("✓ Successfully updated %s schedule", day)
            elif response.status in (401, 403):
                # Token invalid - force refresh and retry
                _LOGGER.warning("Token rejected, forcing refresh...")
                token = await _get_valid_token(hass, entry.entry_id, force_refresh=True)
                headers["Authorization"] = token
                
                async with websession.post(url, json=schedule_data, headers=headers) as response2:
                    if response2.status == 200:
                        _LOGGER.info("✓ Successfully updated %s schedule (after refresh)", day)
                    else:
                        error_text = await response2.text()
                        raise HomeAssistantError(f"API error {response2.status}: {error_text}")
            else:
                error_text = await response.text()
                raise HomeAssistantError(f"API error {response.status}: {error_text}")
    
    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_DAY,
        handle_set_day,
        schema=SET_DAY_SCHEMA
    )
    
    _LOGGER.info("✓ Hive Schedule Manager setup complete")
    return True


async def _get_valid_token(hass: HomeAssistant, entry_id: str, force_refresh: bool = False) -> str:
    """Get a valid token, refreshing if necessary."""
    data = hass.data[DOMAIN][entry_id]
    token_data = data["token_data"]
    store = data["store"]
    
    # Check if token is still valid (< 55 minutes old to be safe)
    now = datetime.now()
    expiry = token_data.get("token_expiry")
    
    if expiry and not force_refresh:
        expiry_dt = datetime.fromisoformat(expiry)
        if now < expiry_dt:
            _LOGGER.debug("Using cached token (expires in %s)", expiry_dt - now)
            return token_data["id_token"]
    
    # Need to refresh token
    _LOGGER.info("Token expired or force_refresh=True, refreshing using RefreshToken...")
    
    refresh_token = token_data.get("refresh_token")
    if not refresh_token:
        raise HomeAssistantError("No RefreshToken available - please reconfigure integration")
    
    # Use Auth to refresh (this uses RefreshToken, no MFA needed!)
    auth = Auth(data["username"], data["password"])
    
    try:
        # Set the refresh token
        if hasattr(auth, 'refresh_token'):
            auth.refresh_token = refresh_token
        
        # Call refresh (method name might vary)
        new_tokens = await auth.renew_access_token(refresh_token)
        
        _LOGGER.info("✓ Successfully refreshed tokens (no MFA required!)")
        
        # Update stored tokens
        auth_result = new_tokens.get('AuthenticationResult', {})
        token_data["access_token"] = auth_result.get('AccessToken')
        token_data["id_token"] = auth_result.get('IdToken')
        token_data["token_expiry"] = (now + timedelta(seconds=3300)).isoformat()  # 55 min
        
        # Save to storage
        await store.async_save(token_data)
        
        return token_data["id_token"]
        
    except Exception as e:
        _LOGGER.error("Token refresh failed: %s", e)
        _LOGGER.error("RefreshToken may have expired (30 days) - please reconfigure integration")
        raise HomeAssistantError("Authentication failed - please reconfigure integration") from e


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    hass.data[DOMAIN].pop(entry.entry_id)
    
    if not hass.data[DOMAIN]:
        hass.services.async_remove(DOMAIN, SERVICE_SET_DAY)
    
    return True