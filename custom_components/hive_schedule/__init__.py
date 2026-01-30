"""
Hive Schedule Manager Integration for Home Assistant v2.0
Depends on official Hive integration for authentication
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

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv
from homeassistant.exceptions import HomeAssistantError

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
    _LOGGER.info("Using official Hive integration for authentication")
    _LOGGER.info("=" * 80)
    
    # Find Hive config entry
    hive_entries = [
        e for e in hass.config_entries.async_entries()
        if e.domain == "hive"
    ]
    
    if not hive_entries:
        _LOGGER.error("No Hive integration found in config entries!")
        return False
    
    hive_entry = hive_entries[0]
    hive_entry_id = hive_entry.entry_id
    _LOGGER.info("✓ Found Hive config entry: %s", hive_entry_id)
    
    # Wait for Hive integration to populate hass.data["hive"][entry_id]
    # This is how the official integration stores its API object
    import asyncio
    hive_api = None
    
    for attempt in range(30):
        # Check if hass.data["hive"] exists
        if "hive" in hass.data:
            # Check if our specific entry is loaded
            if hive_entry_id in hass.data["hive"]:
                hive_data = hass.data["hive"][hive_entry_id]
                _LOGGER.debug("Found hive_data for entry, type: %s", type(hive_data))
                
                # Official integration stores as: hass.data["hive"][entry_id]["hive"]
                if isinstance(hive_data, dict) and "hive" in hive_data:
                    hive_api = hive_data["hive"]
                    _LOGGER.info("✓ Found Hive API after %d seconds", attempt + 1)
                    break
                else:
                    _LOGGER.debug("hive_data structure: %s", hive_data.keys() if isinstance(hive_data, dict) else "not a dict")
        
        _LOGGER.debug("Waiting for Hive integration... (attempt %d/30)", attempt + 1)
        await asyncio.sleep(1)
    
    if not hive_api:
        _LOGGER.error("Timeout waiting for Hive API to be available")
        _LOGGER.error("Expected: hass.data['hive']['%s']['hive']", hive_entry_id)
        _LOGGER.error("'hive' in hass.data: %s", "hive" in hass.data)
        if "hive" in hass.data:
            _LOGGER.error("Keys in hass.data['hive']: %s", list(hass.data["hive"].keys()))
        return False
    
    _LOGGER.info("✓ Successfully connected to Hive API")
    
    # Extract authentication tokens from Hive API
    # The Hive object has a session with tokens we can use
    auth_tokens = None
    
    if hasattr(hive_api, 'session'):
        session = hive_api.session
        _LOGGER.debug("Found session object: %s", type(session))
        
        # Try to get tokens from session
        if hasattr(session, 'token'):
            auth_tokens = {"token": session.token}
            _LOGGER.info("✓ Extracted auth token from Hive session")
        elif hasattr(session, 'tokenData'):
            auth_tokens = session.tokenData
            _LOGGER.info("✓ Extracted tokenData from Hive session")
        elif hasattr(session, 'auth'):
            auth_tokens = session.auth
            _LOGGER.info("✓ Extracted auth from Hive session")
        else:
            _LOGGER.debug("Session attributes: %s", [a for a in dir(session) if not a.startswith('_')])
    
    if not auth_tokens:
        _LOGGER.error("Could not extract authentication tokens from Hive API")
        return False
    
    _LOGGER.debug("Auth tokens type: %s", type(auth_tokens))
    
    # Load profiles
    profiles = await _load_profiles(hass)
    _LOGGER.info("Loaded %d schedule profiles", len(profiles))
    
    # Store data
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "hive_api": hive_api,
        "auth_tokens": auth_tokens,
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
        
        # Get authentication tokens
        auth_tokens = hass.data[DOMAIN][entry.entry_id]["auth_tokens"]
        
        # Build authorization header from tokens
        if isinstance(auth_tokens, dict) and "token" in auth_tokens:
            token = auth_tokens["token"]
        elif hasattr(auth_tokens, 'token'):
            token = auth_tokens.token
        else:
            # Try to extract token string
            token = str(auth_tokens)
        
        _LOGGER.debug("Using token for API call")
        
        # Make direct HTTP request to Hive API (like v1.x but with official tokens)
        import aiohttp
        
        url = f"https://beekeeper-uk.hivehome.com/1.0/nodes/{node_id}"
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "authorization": token,
        }
        
        _LOGGER.debug("POST %s", url)
        _LOGGER.debug("Payload: %s", schedule_data)
        
        # Use Home Assistant's aiohttp session
        from homeassistant.helpers import aiohttp_client
        session = aiohttp_client.async_get_clientsession(hass)
        
        try:
            async with session.post(url, json=schedule_data, headers=headers) as response:
                if response.status == 200:
                    _LOGGER.info("✓ Successfully updated %s schedule", day)
                else:
                    error_text = await response.text()
                    _LOGGER.error("API returned %d: %s", response.status, error_text)
                    raise HomeAssistantError(f"API error {response.status}: {error_text}")
                    
        except aiohttp.ClientError as e:
            _LOGGER.error("HTTP request failed: %s", e)
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