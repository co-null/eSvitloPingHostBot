import os
import json
from config import SETTINGS_FILE

# Load user settings from file
def load_user_settings():
    if os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, 'r') as file:
            return json.load(file)
    return {}

# Save user settings to file
def save_user_settings():
    with open(SETTINGS_FILE, 'w') as file:
        json.dump(user_settings, file)

def init_user(user_id: str):
    _user = {}
    _user['ip_address']       = None
    _user['label']            = ''
    _user['channel_id']       = None
    _user['to_bot']           = True
    _user['to_channel']       = False
    _user['ping_job']         = None
    _user['awaiting_ip']      = False
    _user['awaiting_label']   = False
    _user['awaiting_channel'] = False
    _user['last_state']       = None
    _user['last_ts']          = None
    user_settings[user_id] = _user

# Dictionary to store user-specific settings
user_settings = load_user_settings()
user_jobs = {}
