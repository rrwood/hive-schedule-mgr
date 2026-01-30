"""Constants for the Hive Schedule Manager integration v2.0."""

DOMAIN = "hive_schedule"

# Configuration
CONF_MFA_CODE = "mfa_code"
CONF_TOKENS = "tokens"  # apyhiveapi manages tokens internally

# Service names
SERVICE_SET_DAY = "set_day_schedule"

# Attributes
ATTR_NODE_ID = "node_id"
ATTR_DAY = "day"
ATTR_SCHEDULE = "schedule"
ATTR_PROFILE = "profile"

# Hive API
HIVE_API_URL = "https://beekeeper-uk.hivehome.com/1.0"