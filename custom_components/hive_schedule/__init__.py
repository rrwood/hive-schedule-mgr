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
    
    # Debug: Check what's in hass.data
    _LOGGER.debug("Available domains in hass.data: %s", list(hass.data.keys()))
    
    # Check if official Hive integration is loaded
    if "hive" not in hass.data:
        _LOGGER.error("'hive' not found in hass.data!")
        _LOGGER.info("Checking config entries for Hive integration...")
        
        # Check config entries
        hive_entries = [
            entry for entry in hass.config_entries.async_entries()
            if entry.domain == "hive"
        ]
        
        if hive_entries:
            _LOGGER.warning("Hive integration is configured but not loaded in hass.data yet")
            _LOGGER.warning("This might be a race condition - try reloading the integration")
        else:
            _LOGGER.error("No Hive integration found in config entries either!")
        
        return False
    
    _LOGGER.info("✓ Found 'hive' in hass.data")
    _LOGGER.debug("hass.data['hive'] keys: %s", list(hass.data["hive"].keys()) if isinstance(hass.data["hive"], dict) else "not a dict")
    
    # Get Hive API from official integration
    hive_data = hass.data["hive"]
    
    # Try different ways to access the Hive API
    hive_api = None
    
    # Method 1: Look for 'hive' key in entries
    for hive_entry_id, data in hive_data.items():
        _LOGGER.debug("Checking entry %s: %s", hive_entry_id, type(data))
        if isinstance(data, dict) and "hive" in data:
            hive_api = data["hive"]
            _LOGGER.info("✓ Found Hive API via method 1 (dict with 'hive' key)")
            break
    
    # Method 2: Maybe it's directly the Hive object
    if not hive_api:
        for hive_entry_id, data in hive_data.items():
            if hasattr(data, "heating"):
                hive_api = data
                _LOGGER.info("✓ Found Hive API via method 2 (object with 'heating' attribute)")
                break
    
    # Method 3: Check if there's a specific structure
    if not hive_api and isinstance(hive_data, dict):
        # Try to find any entry
        for key, value in hive_data.items():
            _LOGGER.debug("Entry %s has type: %s, dir: %s", key, type(value), dir(value) if hasattr(value, '__dict__') else "N/A")
    
    if not hive_api:
        _LOGGER.error("Could not access Hive API from official integration")
        _LOGGER.error("hass.data['hive'] structure: %s", hive_data)
        return False
    
    _LOGGER.info("✓ Successfully connected to Hive API")
    
    # Load profiles
    profiles = await _load_profiles(hass)
    _LOGGER.info("Loaded %d schedule profiles", len(profiles))
    
    # Store data
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "hive_api": hive_api,
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
        
        # Update schedule using official Hive API
        try:
            result = await hive_api.heating.setSchedule(node_id, schedule_data)
            
            if result:
                _LOGGER.info("✓ Successfully updated %s schedule", day)
            else:
                raise HomeAssistantError("Hive API returned False")
                
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