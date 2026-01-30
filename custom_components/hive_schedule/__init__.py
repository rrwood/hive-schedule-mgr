"""
Hive Schedule Manager Integration for Home Assistant v2.0
Standalone version using apyhiveapi (bundled with Home Assistant)
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

# apyhiveapi is bundled with Home Assistant (used by official Hive integration)
from apyhiveapi import Hive, Auth

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import aiohttp_client

from .const import (
    DOMAIN,
    SERVICE_SET_DAY,
    ATTR_NODE_ID,
    ATTR_DAY,
    ATTR_SCHEDULE,
    ATTR_PROFILE,
)

_LOGGER = logging.getLogger(__name__)

# Load version from manifest.json
def _get_version() -> str:
    """Get version from manifest.json."""
    try:
        manifest_path = os.path.join(os.path.dirname(__file__), "manifest.json")
        with open(manifest_path, 'r') as f:
            manifest = json.load(f)
            return manifest.get('version', 'unknown')
    except Exception:
        return 'unknown'

VERSION = _get_version()
PROFILES_FILE = "hive_schedule_profiles.yaml"

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
    """Load schedule profiles from YAML file asynchronously."""
    config_path = hass.config.path(PROFILES_FILE)
    
    if not os.path.exists(config_path):
        _LOGGER.info("Creating default profiles file: %s", config_path)
        await _create_default_profiles_file(config_path)
    
    try:
        async with aiofiles.open(config_path, 'r') as file:
            content = await file.read()
            profiles = yaml.safe_load(content) or {}
            _LOGGER.debug("Loaded %d profiles from %s", len(profiles), PROFILES_FILE)
            return profiles
    except Exception as e:
        _LOGGER.error("Failed to load profiles from %s: %s", PROFILES_FILE, e)
        return _get_builtin_profiles()


def _get_builtin_profiles() -> dict:
    """Get built-in default profiles as fallback."""
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
        "nonworkday": [
            {"time": "06:30", "temp": 18.5},
            {"time": "08:00", "temp": 18.0},
            {"time": "16:30", "temp": 19.5},
            {"time": "22:00", "temp": 16.0},
        ],
        "holiday": [
            {"time": "00:00", "temp": 15.0},
        ],
        "all_day_comfort": [
            {"time": "00:00", "temp": 19.0},
        ],
        "custom1": [
            {"time": "05:30", "temp": 17.0},
            {"time": "08:00", "temp": 16.5},
            {"time": "12:00", "temp": 18.0},
            {"time": "17:00", "temp": 19.0},
            {"time": "22:30", "temp": 16.0},
        ],
        "custom2": [
            {"time": "06:00", "temp": 18.0},
            {"time": "09:00", "temp": 17.5},
            {"time": "13:00", "temp": 18.5},
            {"time": "18:00", "temp": 19.5},
            {"time": "23:00", "temp": 16.5},
        ],
    }


async def _create_default_profiles_file(config_path: str):
    """Create default profiles file with examples."""
    default_content = """# Hive Schedule Profiles
# Each profile is a list of time/temp pairs for one day
# Times in 24-hour format (HH:MM), temperatures in Celsius

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

nonworkday:
  - time: "06:30"
    temp: 18.5
  - time: "08:00"
    temp: 18.0
  - time: "16:30"
    temp: 19.5
  - time: "22:00"
    temp: 16.0

holiday:
  - time: "00:00"
    temp: 15.0

all_day_comfort:
  - time: "00:00"
    temp: 19.0

custom1:
  - time: "05:30"
    temp: 17.0
  - time: "08:00"
    temp: 16.5
  - time: "12:00"
    temp: 18.0
  - time: "17:00"
    temp: 19.0
  - time: "22:30"
    temp: 16.0

custom2:
  - time: "06:00"
    temp: 18.0
  - time: "09:00"
    temp: 17.5
  - time: "13:00"
    temp: 18.5
  - time: "18:00"
    temp: 19.5
  - time: "23:00"
    temp: 16.5
"""
    
    try:
        async with aiofiles.open(config_path, 'w') as file:
            await file.write(default_content)
        _LOGGER.info("Created default profiles file at %s", config_path)
    except Exception as e:
        _LOGGER.error("Failed to create default profiles file: %s", e)


def _validate_schedule(schedule: list) -> bool:
    """Validate a schedule format."""
    if not isinstance(schedule, list):
        raise ValueError("Schedule must be a list")
    
    if len(schedule) == 0:
        raise ValueError("Schedule must have at least one entry")
    
    for entry in schedule:
        if not isinstance(entry, dict):
            raise ValueError("Each schedule entry must be a dictionary")
        
        if "time" not in entry or "temp" not in entry:
            raise ValueError("Each entry must have 'time' and 'temp' keys")
        
        # Validate time format (HH:MM)
        time_str = entry["time"]
        try:
            hours, minutes = time_str.split(":")
            if not (0 <= int(hours) <= 23 and 0 <= int(minutes) <= 59):
                raise ValueError
        except (ValueError, AttributeError):
            raise ValueError(f"Invalid time format: {time_str}. Must be HH:MM")
        
        # Validate temperature
        try:
            temp = float(entry["temp"])
            if not (5.0 <= temp <= 32.0):
                raise ValueError(f"Temperature {temp}°C out of range (5-32°C)")
        except (ValueError, TypeError):
            raise ValueError(f"Invalid temperature: {entry['temp']}")
    
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Hive Schedule Manager from a config entry."""
    
    _LOGGER.info("=" * 80)
    _LOGGER.info("Hive Schedule Manager v%s", VERSION)
    _LOGGER.info("Standalone with apyhiveapi authentication")
    _LOGGER.info("=" * 80)
    
    # Get credentials
    username = entry.data[CONF_USERNAME]
    password = entry.data[CONF_PASSWORD]
    
    # Get aiohttp session
    websession = aiohttp_client.async_get_clientsession(hass)
    
    try:
        # Create Hive instance - we won't authenticate here, just use it for structure
        # Authentication was already done in config_flow
        hive = Hive(websession=websession)
        
        # Store credentials for later use (API calls need fresh tokens)
        hive.session.username = username
        hive.session.password = password
        
        # If auth tokens were stored during config flow, load them
        if "auth_tokens" in entry.data:
            auth_tokens = entry.data["auth_tokens"]
            _LOGGER.info("Loading auth tokens from config entry")
            _LOGGER.debug("Auth tokens: %s", auth_tokens)
            
            # Store in session
            if isinstance(auth_tokens, dict):
                hive.session.tokens = {"tokenData": auth_tokens}
                _LOGGER.info("✓ Loaded authentication tokens")
        
        _LOGGER.info("✓ Hive instance created")
        _LOGGER.info("✓ Using apyhiveapi for token management")
        
    except Exception as e:
        _LOGGER.error("Failed to create Hive instance: %s", e)
        _LOGGER.debug("Error details", exc_info=True)
        return False
    
    # Load profiles
    profiles = await _load_profiles(hass)
    _LOGGER.info("Loaded %d schedule profiles", len(profiles))
    
    # Store Hive instance
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "hive": hive,
        "profiles": profiles,
    }
    
    # Register service
    async def handle_set_day(call: ServiceCall) -> None:
        """Handle set_day_schedule service call."""
        node_id = call.data[ATTR_NODE_ID]
        day = call.data[ATTR_DAY]
        profile_name = call.data.get(ATTR_PROFILE)
        custom_schedule = call.data.get(ATTR_SCHEDULE)
        
        # Get schedule from profile or custom
        if profile_name:
            if profile_name not in profiles:
                raise HomeAssistantError(f"Unknown profile: {profile_name}")
            day_schedule = profiles[profile_name]
            _LOGGER.info("Using profile '%s' for %s", profile_name, day)
        elif custom_schedule:
            day_schedule = custom_schedule
            _LOGGER.info("Using custom schedule for %s", day)
        else:
            raise HomeAssistantError("Either 'profile' or 'schedule' must be provided")
        
        # Validate schedule
        try:
            _validate_schedule(day_schedule)
        except ValueError as err:
            raise HomeAssistantError(f"Invalid schedule: {err}") from err
        
        _LOGGER.info("Setting schedule for %s on node %s", day, node_id)
        
        # Convert schedule to Hive format
        hive_schedule = []
        for entry in day_schedule:
            hours, minutes = entry["time"].split(":")
            minutes_from_midnight = int(hours) * 60 + int(minutes)
            
            hive_schedule.append({
                "value": {"target": entry["temp"]},
                "start": minutes_from_midnight
            })
        
        schedule_data = {
            "schedule": {
                day: hive_schedule
            }
        }
        
        # Get token for API call - authenticate if needed
        try:
            _LOGGER.debug("Checking for existing tokens...")
            
            # Check if we have valid tokens and Hive session is established
            has_valid_tokens = False
            if hasattr(hive.session, 'tokens') and hive.session.tokens:
                # Check if tokenData is populated
                token_data = hive.session.tokens.get('tokenData', {})
                if token_data and isinstance(token_data, dict) and len(token_data) > 0:
                    has_valid_tokens = True
                    _LOGGER.debug("Found populated tokenData")
            
            if not has_valid_tokens:
                _LOGGER.info("No valid tokens available, authenticating...")
                
                # Use Auth to login with credentials
                auth = Auth(hive.session.username, hive.session.password)
                tokens = await auth.login()
                
                _LOGGER.debug("Auth.login() returned: %s", tokens)
                
                if tokens and tokens.get("ChallengeName") == "SMS_MFA":
                    _LOGGER.error("MFA required but not available in service call")
                    raise HomeAssistantError("Re-authentication required with MFA - please reconfigure integration")
                
                # Store tokens properly
                if isinstance(tokens, dict):
                    hive.session.tokens = {"tokenData": tokens}
                    _LOGGER.info("Authenticated successfully, tokens stored")
                else:
                    _LOGGER.error("Unexpected token format: %s", type(tokens))
                    raise HomeAssistantError("Authentication returned unexpected format")
            
            # CRITICAL: Initialize Hive session to get actual Hive API token
            # This exchanges Cognito tokens for Hive-specific API token
            _LOGGER.info("Initializing Hive session to get API token...")
            await hive.session.updateData()
            
            # Now extract the REAL Hive API token (not Cognito token!)
            token = None
            
            # Try different possible locations for Hive API token
            if hasattr(hive.session, 'token') and hive.session.token:
                token = hive.session.token
                _LOGGER.debug("Found hive.session.token")
            elif hasattr(hive.session, 'api_token') and hive.session.api_token:
                token = hive.session.api_token
                _LOGGER.debug("Found hive.session.api_token")
            elif hasattr(hive.session, 'session') and isinstance(hive.session.session, dict):
                token = hive.session.session.get('token') or hive.session.session.get('api_token')
                _LOGGER.debug("Found token in hive.session.session dict")
            
            if not token:
                _LOGGER.error("Could not extract Hive API token after updateData()")
                _LOGGER.error("Session attributes: %s", [a for a in dir(hive.session) if not a.startswith('_')])
                raise HomeAssistantError("No Hive API token available")
            
            # Make direct HTTP request to schedule API
            url = f"https://beekeeper-uk.hivehome.com/1.0/nodes/{node_id}"
            
            # Try different header formats - Hive API might expect specific format
            headers = {
                "Content-Type": "application/json",
                "Accept": "application/json",
                "Authorization": f"Bearer {token}",  # Try Bearer format first
            }
            
            _LOGGER.debug("POST %s", url)
            _LOGGER.debug("Authorization header: Bearer %s...", token[:20])
            
            async with websession.post(url, json=schedule_data, headers=headers) as response:
                if response.status == 200:
                    _LOGGER.info("✓ Successfully updated %s schedule", day)
                elif response.status == 401 or response.status == 403:
                    # Token might be wrong type or format, try without Bearer
                    _LOGGER.warning("Got %d with Bearer, trying plain token", response.status)
                    headers["Authorization"] = token
                    
                    async with websession.post(url, json=schedule_data, headers=headers) as response2:
                        if response2.status == 200:
                            _LOGGER.info("✓ Successfully updated %s schedule (plain token)", day)
                        else:
                            error_text = await response2.text()
                            _LOGGER.error("API still returned %d: %s", response2.status, error_text)
                            
                            # Clear tokens so next call will re-authenticate
                            if response2.status == 401:
                                hive.session.tokens = None
                                raise HomeAssistantError("Authentication failed - please reconfigure integration")
                            else:
                                raise HomeAssistantError(f"API error {response2.status}")
                else:
                    error_text = await response.text()
                    _LOGGER.error("API returned %d: %s", response.status, error_text)
                    raise HomeAssistantError(f"API error {response.status}")
                    
        except Exception as e:
            _LOGGER.error("Failed to update schedule: %s", e)
            raise HomeAssistantError(f"Failed to update schedule: {e}") from e
    
    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_DAY,
        handle_set_day,
        schema=SET_DAY_SCHEMA
    )
    
    _LOGGER.info("Hive Schedule Manager setup complete")
    _LOGGER.info("Profiles file: %s", hass.config.path(PROFILES_FILE))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    hass.data[DOMAIN].pop(entry.entry_id)
    
    # Unregister services if this is the last entry
    if not hass.data[DOMAIN]:
        hass.services.async_remove(DOMAIN, SERVICE_SET_DAY)
    
    return True