"""
Hive Schedule Manager Integration for Home Assistant v2.0
Using apyhiveapi for proper authentication with 30-day tokens
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
from apyhiveapi import Auth, Hive

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD, CONF_SCAN_INTERVAL
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.exceptions import HomeAssistantError

from .const import (
    DOMAIN,
    SERVICE_SET_DAY,
    ATTR_NODE_ID,
    ATTR_DAY,
    ATTR_SCHEDULE,
    ATTR_PROFILE,
    CONF_TOKENS,
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
DEFAULT_SCAN_INTERVAL = timedelta(hours=1)  # apyhiveapi handles token refresh
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


class HiveScheduleAPI:
    """API client for Hive heating schedules using apyhiveapi."""
    
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry):
        """Initialize the API client."""
        self.hass = hass
        self.entry = entry
        self._hive = None
        self._session = None
        
    async def async_setup(self) -> bool:
        """Set up the Hive API connection."""
        username = self.entry.data[CONF_USERNAME]
        password = self.entry.data[CONF_PASSWORD]
        
        try:
            # Initialize Hive API
            self._session = Auth(username, password)
            self._hive = Hive(self._session)
            
            # Login and get tokens
            login_result = await self._session.login()
            
            if login_result.get("ChallengeName") == "SMS_MFA":
                _LOGGER.error("MFA challenge received - this should be handled in config flow")
                return False
            
            _LOGGER.info("✓ Successfully authenticated with Hive (tokens valid for 30 days)")
            
            # Start session to initialize connection
            await self._hive.session.startSession()
            
            return True
            
        except Exception as e:
            _LOGGER.error("Failed to authenticate with Hive: %s", e)
            return False
    
    async def async_update_schedule(self, node_id: str, day: str, schedule: list) -> bool:
        """Update schedule for a specific day."""
        try:
            # Convert schedule to Hive format
            hive_schedule = []
            for entry in schedule:
                # Convert HH:MM to minutes from midnight
                hours, minutes = entry["time"].split(":")
                minutes_from_midnight = int(hours) * 60 + int(minutes)
                
                hive_schedule.append({
                    "value": {"target": entry["temp"]},
                    "start": minutes_from_midnight
                })
            
            # Update only the specified day
            schedule_data = {
                "schedule": {
                    day: hive_schedule
                }
            }
            
            _LOGGER.debug("Updating schedule for %s: %s", day, schedule_data)
            
            # Use apyhiveapi's heating module
            result = await self._hive.heating.setSchedule(node_id, schedule_data)
            
            if result:
                _LOGGER.info("✓ Successfully updated %s schedule for node %s", day, node_id)
                return True
            else:
                _LOGGER.error("Failed to update schedule - API returned False")
                return False
                
        except Exception as e:
            _LOGGER.error("Error updating schedule: %s", e)
            _LOGGER.debug("Schedule update error details", exc_info=True)
            raise HomeAssistantError(f"Failed to update schedule: {e}") from e
    
    async def async_close(self):
        """Close the API session."""
        if self._hive:
            try:
                await self._hive.session.close()
                _LOGGER.debug("Closed Hive API session")
            except Exception as e:
                _LOGGER.debug("Error closing session: %s", e)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Hive Schedule Manager from a config entry."""
    
    _LOGGER.info("=" * 80)
    _LOGGER.info("Hive Schedule Manager v%s (apyhiveapi)", VERSION)
    _LOGGER.info("30-day token lifetime with automatic refresh")
    _LOGGER.info("=" * 80)
    
    # Initialize API
    api = HiveScheduleAPI(hass, entry)
    
    # Setup and authenticate
    if not await api.async_setup():
        _LOGGER.error("Failed to set up Hive API")
        return False
    
    # Load profiles
    profiles = await _load_profiles(hass)
    _LOGGER.info("Loaded %d schedule profiles", len(profiles))
    
    # Store API instance
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "api": api,
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
        
        # Update schedule
        await api.async_update_schedule(node_id, day, day_schedule)
        
        _LOGGER.info("Successfully updated %s schedule", day)
    
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
    data = hass.data[DOMAIN].pop(entry.entry_id)
    
    # Close API session
    if "api" in data:
        await data["api"].async_close()
    
    # Unregister services if this is the last entry
    if not hass.data[DOMAIN]:
        hass.services.async_remove(DOMAIN, SERVICE_SET_DAY)
    
    return True