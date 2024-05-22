import os
import json
from config import SETTINGS_FILE, STATES_FILE

# Load user settings from file
def load_user_settings():
    if os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, 'r') as file:
            return json.load(file)
    return {}

def load_user_states():
    if os.path.exists(STATES_FILE):
        with open(STATES_FILE, 'r') as file:
            return json.load(file)
    return {}

# Save user settings to file
def save_user_settings():
    with open(SETTINGS_FILE, 'w') as file:
        json.dump(user_settings, file)

def save_user_states():
    with open(STATES_FILE, 'w') as file:
        json.dump(user_settings, file)

def init_user(user_id: str, chat_id: str):
    _user = {}
    _user['chat_id']          = chat_id
    _user['ip_address']       = None
    _user['listener']         = False
    _user['label']            = ''
    _user['channel_id']       = None
    _user['to_bot']           = True
    _user['to_channel']       = False
    _user['ping_job']         = None
    _user['awaiting_ip']      = False
    _user['awaiting_label']   = False
    _user['awaiting_channel'] = False
    user_settings[user_id]    = _user

    _states = {}
    _states['last_state']  = None
    _states['last_ts']     = None
    user_states[user_id] = _states

def reinit_user(user_id: str):
    init_user('dummy', None)
    dummy = user_settings['dummy']
    user  = user_settings[user_id]
    for key in dummy.keys():
        if key not in user.keys():
            user_settings[user_id][key] = dummy[key]
    del user_settings['dummy']

def init_states(user_id: str):
    _states = {}
    _states['last_state']  = None
    _states['last_ts']     = None
    user_states[user_id] = _states
# Dictionary to store user-specific settings
user_settings = load_user_settings()
user_states   = load_user_states()
user_jobs     = {}
listeners     = {}