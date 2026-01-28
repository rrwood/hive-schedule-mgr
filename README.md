# Hive Schedule Manager

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/custom-components/hacs)
[![Version](https://img.shields.io/badge/version-1.1.17-blue.svg)](https://github.com/yourusername/hive-schedule-manager)

**Advanced schedule management for your Hive Active Heating™ system with built-in profiles, Google Calendar integration, and UI-based configuration.**

## ✨ Features

- 🎯 **8 Pre-defined Heating Profiles** - Workday, Weekend, Holiday, WFH, and more
- 🔐 **Config Flow with 2FA Support** - Secure setup through Home Assistant UI
- 📅 **Google Calendar Integration** - Automatically adjust heating based on your calendar
- 🔄 **Automatic Token Refresh** - Never worry about authentication expiring
- ⚡ **Only Updates Selected Day** - Doesn't touch other days in your schedule
- 🎨 **Custom Schedules** - Create your own temperature profiles
- 📱 **Notification Support** - Get updates when schedules change

---

## 📋 Table of Contents

- [Installation](#-installation)
- [Initial Setup](#-initial-setup)
- [Schedule Profiles](#-schedule-profiles)
- [Google Calendar Integration](#-google-calendar-integration)
- [Usage Examples](#-usage-examples)
- [Services](#-services)
- [Troubleshooting](#-troubleshooting)

---

## 📦 Installation

### HACS Installation (Recommended)

1. **Open HACS** in Home Assistant
   - Navigate to **HACS** → **Integrations**

2. **Add Custom Repository**
   - Click the **⋮** menu (top right)
   - Select **Custom repositories**
   - Add repository URL: `https://github.com/yourusername/hive-schedule-manager`
   - Category: **Integration**
   - Click **Add**

3. **Install the Integration**
   - Click **+ Explore & Download Repositories**
   - Search for "Hive Schedule Manager"
   - Click **Download**
   - Restart Home Assistant

### Manual Installation

1. Download the latest release from GitHub
2. Copy the `hive_schedule` folder to `/config/custom_components/`
3. Restart Home Assistant

---

## 🚀 Initial Setup

### Adding the Integration

1. Go to **Settings** → **Devices & Services**
2. Click **+ Add Integration**
3. Search for "Hive Schedule Manager"
4. Click to start setup

### Configuration Steps

#### Step 1: Enter Credentials

Enter your Hive account credentials (same as Hive app):
- **Email**: Your Hive account email
- **Password**: Your Hive account password

Click **Submit**

#### Step 2: Two-Factor Authentication

If you have 2FA enabled on your Hive account:

1. An SMS code will be sent to your registered phone number
2. Enter the 6-digit verification code
3. Click **Submit**

The integration will store authentication tokens securely and handle automatic token refresh.

> **Note**: You only need to enter the 2FA code once during setup. Tokens are refreshed automatically every 30 minutes.

### Finding Your Node ID

Your heating node ID is required for service calls. You can find it in several ways:

#### Method 1: Developer Tools (Easiest)

1. Go to **Developer Tools** → **States**
2. Search for `climate.` entities from your Hive integration
3. Click on a Hive thermostat entity
4. Look for `node_id` in the attributes

Example:
```yaml
node_id: "d2708e98-f22f-483e-b590-9ddbd642a3b7"
```

#### Method 2: Using the Hive App

Your node ID corresponds to your Hive receiver/thermostat. While the Hive app doesn't display it directly, you can use the Developer Tools method above which references the same device.

---

## 🎨 Schedule Profiles

The integration includes 8 pre-defined heating profiles optimized for different scenarios:

### 1. **weekday** - Standard Work Schedule
Perfect for typical Monday-Friday work schedules.

| Time  | Temperature | Purpose |
|-------|-------------|---------|
| 06:30 | 18.0°C | Morning warmup |
| 08:00 | 16.0°C | Away during day |
| 16:30 | 19.5°C | Evening warmup |
| 21:30 | 16.0°C | Night setback |

### 2. **weekend** - Relaxed Weekend Schedule
Later start, comfortable daytime temperatures.

| Time  | Temperature | Purpose |
|-------|-------------|---------|
| 07:30 | 18.0°C | Later morning warmup |
| 09:00 | 19.0°C | Comfortable day |
| 22:00 | 16.0°C | Later night setback |

### 3. **holiday** - Holiday/Vacation Home
Relaxed schedule for when you're at home all day.

| Time  | Temperature | Purpose |
|-------|-------------|---------|
| 08:00 | 18.0°C | Relaxed morning |
| 22:30 | 16.0°C | Extended evening |

### 4. **weekday_early** - Early Morning Start
For early risers or shift workers.

| Time  | Temperature | Purpose |
|-------|-------------|---------|
| 05:30 | 18.0°C | Early morning |
| 07:00 | 16.0°C | Away during day |
| 16:30 | 19.5°C | Evening warmup |
| 21:30 | 16.0°C | Night setback |

### 5. **weekday_late** - Late Return Home
For those working late or evening activities.

| Time  | Temperature | Purpose |
|-------|-------------|---------|
| 06:30 | 18.0°C | Morning warmup |
| 08:00 | 16.0°C | Away during day |
| 18:30 | 19.5°C | Late evening warmup |
| 23:00 | 16.0°C | Late night setback |

### 6. **wfh** - Work From Home
Maintains comfort throughout the workday.

| Time  | Temperature | Purpose |
|-------|-------------|---------|
| 06:30 | 18.0°C | Morning warmup |
| 09:00 | 19.0°C | Comfortable workday |
| 17:00 | 19.5°C | Evening |
| 22:00 | 16.0°C | Night setback |

### 7. **away** - Away/Vacation Mode
Minimal heating for frost protection when away.

| Time  | Temperature | Purpose |
|-------|-------------|---------|
| 00:00 | 12.0°C | Frost protection only |

### 8. **all_day_comfort** - Constant Comfort
Maintains constant temperature all day.

| Time  | Temperature | Purpose |
|-------|-------------|---------|
| 00:00 | 19.0°C | All-day comfort |

---

## 📅 Google Calendar Integration

Automatically adjust your heating schedule based on Google Calendar events! Perfect for holidays, work-from-home days, and special occasions.

### Step 1: Set Up Google Calendar in Home Assistant

1. **Install Google Calendar Integration**
   - Go to **Settings** → **Devices & Services**
   - Click **+ Add Integration**
   - Search for "Google Calendar"
   - Follow the OAuth setup process

2. **Create a Heating Schedule Calendar**
   - In Google Calendar, create a new calendar called "Home Automation"
   - Share it with your Home Assistant Google account
   - Note the entity name (e.g., `calendar.homeautomation`)

### Step 2: Create Calendar Events

Add events to your calendar with specific keywords in the title:

- **"workday"** - Uses weekday profile
- **"nonworkday"** - Uses weekend/non-working profile  
- **"holiday"** - Uses holiday profile

**Examples:**
- "Bank Holiday" → triggers holiday profile
- "Working from Home" → triggers workday profile
- "Non-workday - School Closed" → triggers nonworkday profile

### Step 3: Create Automation

Use the provided example automation to check your calendar daily and update tomorrow's heating schedule.

See the [Example Automation](#example-google-calendar-automation) section below for the complete automation code.

### How It Works

The automation:
1. Runs at 8:00 PM every evening
2. Checks tomorrow's calendar events
3. Looks for keywords: "holiday", "nonworkday", "workday"
4. Applies the appropriate heating profile
5. Sends a notification (optional)
6. Falls back to weekday/weekend based on day of week

**Calendar Priority:**
1. Holiday events (highest priority)
2. Non-workday events
3. Workday events
4. Default schedule (Mon-Thu = workday, Fri = nonworkday, Sat-Sun = weekend)

---

## 💡 Usage Examples

### Basic Service Call

Update Saturday's schedule with a custom profile:

```yaml
service: hive_schedule.set_day_schedule
data:
  node_id: "d2708e98-f22f-483e-b590-9ddbd642a3b7"
  day: "saturday"
  profile: "weekend"
```

### Custom Schedule

Create your own temperature schedule:

```yaml
service: hive_schedule.set_day_schedule
data:
  node_id: "d2708e98-f22f-483e-b590-9ddbd642a3b7"
  day: "monday"
  schedule:
    - time: "06:00"
      temp: 19.0
    - time: "09:00"
      temp: 16.0
    - time: "17:00"
      temp: 20.0
    - time: "22:30"
      temp: 15.5
```

### Example: Google Calendar Automation

Complete automation that checks your calendar and sets tomorrow's heating:

```yaml
alias: Set Tomorrow's Heating Profile
description: Automatically set heating based on Google Calendar events
triggers:
  - at: "20:00:00"
    trigger: time
conditions: []
actions:
  # Get tomorrow's calendar events
  - target:
      entity_id: calendar.homeautomation
    data:
      start_date_time: >-
        {{ (today_at('00:00') + timedelta(days=1)).strftime('%Y-%m-%d %H:%M:%S') }}
      duration:
        hours: 24
    action: calendar.get_events
    response_variable: tomorrow_events
  
  # Set up variables
  - variables:
      tomorrow_day: "{{ (now() + timedelta(days=1)).weekday() }}"
      tomorrow_day_name: "{{ (now() + timedelta(days=1)).strftime('%A').lower() }}"
      events: "{{ tomorrow_events['calendar.homeautomation'].events }}"
      has_holiday: >-
        {{ events | selectattr('summary', 'search', 'holiday', ignorecase=True) | list | length > 0 }}
      has_nonworkday: >-
        {{ events | selectattr('summary', 'search', 'nonworkday', ignorecase=True) | list | length > 0 }}
      has_workday: >-
        {{ events | selectattr('summary', 'search', 'workday', ignorecase=True) | list | length > 0 }}
  
  # Choose appropriate profile
  - choose:
      # Holiday takes priority
      - conditions:
          - condition: template
            value_template: "{{ has_holiday }}"
        sequence:
          - data:
              node_id: d2708e98-f22f-483e-b590-9ddbd642a3b7
              day: "{{ tomorrow_day_name }}"
              profile: holiday
            action: hive_schedule.set_day_schedule
          - data:
              message: "Heating for tomorrow set to Holiday 🏖️"
              title: HEATING
            action: notify.notify
      
      # Non-workday
      - conditions:
          - condition: template
            value_template: "{{ has_nonworkday }}"
        sequence:
          - data:
              node_id: d2708e98-f22f-483e-b590-9ddbd642a3b7
              day: "{{ tomorrow_day_name }}"
              profile: weekend
            action: hive_schedule.set_day_schedule
          - data:
              message: "Heating for tomorrow set to Non-workday 🏠"
              title: HEATING
            action: notify.notify
      
      # Workday
      - conditions:
          - condition: template
            value_template: "{{ has_workday }}"
        sequence:
          - data:
              node_id: d2708e98-f22f-483e-b590-9ddbd642a3b7
              day: "{{ tomorrow_day_name }}"
              profile: weekday
            action: hive_schedule.set_day_schedule
          - data:
              message: "Heating for tomorrow set to Workday 💼"
              title: HEATING
            action: notify.notify
      
      # Monday-Thursday default to workday
      - conditions:
          - condition: template
            value_template: "{{ tomorrow_day in [0, 1, 2, 3] }}"
        sequence:
          - data:
              node_id: d2708e98-f22f-483e-b590-9ddbd642a3b7
              day: "{{ tomorrow_day_name }}"
              profile: weekday
            action: hive_schedule.set_day_schedule
          - data:
              message: "Heating for tomorrow set to Workday 💼"
              title: HEATING
            action: notify.notify
      
      # Friday defaults to non-workday
      - conditions:
          - condition: template
            value_template: "{{ tomorrow_day == 4 }}"
        sequence:
          - data:
              node_id: d2708e98-f22f-483e-b590-9ddbd642a3b7
              day: "{{ tomorrow_day_name }}"
              profile: weekend
            action: hive_schedule.set_day_schedule
          - data:
              message: "Heating for tomorrow set to Non-workday 🏠"
              title: HEATING
            action: notify.notify
    
    # Weekend default
    default:
      - data:
          node_id: d2708e98-f22f-483e-b590-9ddbd642a3b7
          day: "{{ tomorrow_day_name }}"
          profile: weekend
        action: hive_schedule.set_day_schedule
      - data:
          message: "Heating for tomorrow set to Weekend 🎉"
          title: HEATING
        action: notify.notify
mode: single
```

### Example: Manual Override Button

Create a button to quickly set today to "work from home" mode:

```yaml
# In configuration.yaml
script:
  heating_wfh_today:
    alias: "Set Heating to WFH Today"
    sequence:
      - service: hive_schedule.set_day_schedule
        data:
          node_id: "d2708e98-f22f-483e-b590-9ddbd642a3b7"
          day: "{{ now().strftime('%A').lower() }}"
          profile: "wfh"

# In Lovelace dashboard
type: button
name: WFH Today
icon: mdi:home-account
tap_action:
  action: call-service
  service: script.heating_wfh_today
```

---

## 🛠️ Services

### `hive_schedule.set_day_schedule`

Update the heating schedule for a single day.

**Parameters:**

| Parameter | Required | Type | Description |
|-----------|----------|------|-------------|
| `node_id` | Yes | string | Your Hive heating node ID |
| `day` | Yes | string | Day name: monday, tuesday, etc. |
| `profile` | No* | string | Pre-defined profile name |
| `schedule` | No* | list | Custom schedule entries |

*Either `profile` OR `schedule` must be provided

**Example with Profile:**
```yaml
service: hive_schedule.set_day_schedule
data:
  node_id: "d2708e98-f22f-483e-b590-9ddbd642a3b7"
  day: "wednesday"
  profile: "wfh"
```

**Example with Custom Schedule:**
```yaml
service: hive_schedule.set_day_schedule
data:
  node_id: "d2708e98-f22f-483e-b590-9ddbd642a3b7"
  day: "thursday"
  schedule:
    - time: "07:00"
      temp: 18.5
    - time: "23:00"
      temp: 16.0
```

### `hive_schedule.get_schedule`

Retrieve the current heating schedule from Hive (reads actual schedule from Hive cloud, not cached state).

**Parameters:**

| Parameter | Required | Type | Description |
|-----------|----------|------|-------------|
| `node_id` | Yes | string | Your Hive heating node ID |

**Example:**
```yaml
service: hive_schedule.get_schedule
data:
  node_id: "d2708e98-f22f-483e-b590-9ddbd642a3b7"
response_variable: current_schedule
```

### `hive_schedule.refresh_token`

Manually refresh the authentication token (automatic refresh happens every 30 minutes).

**Parameters:** None

**Example:**
```yaml
service: hive_schedule.refresh_token
```

---

## 🔧 Troubleshooting

### Integration Won't Load

**Check logs for errors:**
```
Settings → System → Logs
```

**Common issues:**
- Incorrect Hive credentials
- 2FA code expired (codes are valid for 3 minutes)
- Network connectivity issues

**Solution:** Remove and re-add the integration with correct credentials.

### "Invalid Node ID" Error

**Symptoms:** Error 404 when calling services

**Solution:**
1. Go to Developer Tools → States
2. Find your Hive climate entity
3. Check the `node_id` attribute
4. Use that exact value in service calls

### Schedule Doesn't Update in Hive App

**Wait a few minutes** - Changes can take 1-5 minutes to appear in the Hive app.

**Check the logs:**
```
INFO Successfully updated Hive schedule for node...
```

If you see this message, the update was successful. The Hive app may need to be refreshed.

### Google Calendar Events Not Triggering

**Check the automation:**
1. Go to Settings → Automations & Scenes
2. Find your heating automation
3. Click **⋮** → Run
4. Check if it runs successfully

**Check calendar entity:**
```yaml
service: calendar.get_events
target:
  entity_id: calendar.homeautomation
data:
  duration:
    hours: 24
```

Make sure events contain the keywords (case-insensitive):
- "holiday"
- "nonworkday" 
- "workday"

### 2FA Code Not Working

**Common causes:**
- Code expired (valid for 3 minutes)
- Wrong code entered
- SMS delay

**Solution:**
1. Remove the integration
2. Start setup again
3. Wait for new SMS
4. Enter code within 3 minutes

### Token Refresh Failures

**Symptoms:** Authentication errors after setup

**Check logs for:**
```
Failed to refresh token
```

**Solution:**
```yaml
service: hive_schedule.refresh_token
```

If manual refresh fails, remove and re-add the integration.

---

## 📊 Advanced Usage

### Multiple Thermostats

If you have multiple Hive thermostats, each has its own node_id. You can manage them separately:

```yaml
# Downstairs thermostat
service: hive_schedule.set_day_schedule
data:
  node_id: "node-id-downstairs"
  day: "monday"
  profile: "weekday"

# Upstairs thermostat  
service: hive_schedule.set_day_schedule
data:
  node_id: "node-id-upstairs"
  day: "monday"
  profile: "wfh"
```

### Creating Custom Profiles

You can create your own schedule profiles by editing `schedule_profiles.py`:

```python
# Add to PROFILES dictionary
"my_custom_profile": [
    {"time": "06:00", "temp": 19.0},
    {"time": "08:30", "temp": 16.5},
    {"time": "17:00", "temp": 20.0},
    {"time": "23:00", "temp": 15.0},
],
```

After editing, restart Home Assistant.

### Debugging Schedule Updates

Enable debug logging to see detailed information:

```yaml
# configuration.yaml
logger:
  default: info
  logs:
    custom_components.hive_schedule: debug
```

This will show detailed request/response information in the logs.

---

## 🤝 Support & Contributions

- **Issues**: [GitHub Issues](https://github.com/yourusername/hive-schedule-manager/issues)
- **Discussions**: [GitHub Discussions](https://github.com/yourusername/hive-schedule-manager/discussions)
- **Pull Requests**: Contributions welcome!

---

## 📝 License

MIT License - see LICENSE file for details

---

## 🙏 Credits

- Thanks to the Home Assistant community
- Hive API reverse engineering contributors
- HACS team for making custom integrations easy

---

## ⚠️ Disclaimer

This is an unofficial integration and is not affiliated with, endorsed by, or connected to Hive, British Gas, or Centrica plc. Use at your own risk.

---

**Enjoying this integration?** ⭐ Star the repository on GitHub!