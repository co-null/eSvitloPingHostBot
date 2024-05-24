import os
import json
from config import SETTINGS_FILE, STATES_FILE
import utils
from datetime import datetime

class User:
    def __init__(self, user_id: str, chat_id: str):
        self.user_id                  = user_id
        self.chat_id                  = chat_id
        if user_id not in user_settings.keys():
            self.ip_address: str          = None
            self.listener: bool           = False
            self.label: str               = ''
            self.channel_id: str          = None
            self.to_bot: bool             = True
            self.to_channel: bool         = False
            self.ping_job                 = None
            self.awaiting_ip: bool        = False
            self.awaiting_label: bool     = False
            self.awaiting_channel: bool   = False
            self.last_state: str          = None
            self.last_ts: datetime        = None
            self.last_heared_ts: datetime = None
            self.new                      = True
        else:
            _user  = user_settings[user_id]
            _state = utils.get_key_safe(user_states, self.user_id, {})
            self.ip_address: str          = utils.get_key_safe(_user, 'ip_address', None)
            self.listener: bool           = utils.get_key_safe(_user, 'listener', False)
            self.label: str               = utils.get_key_safe(_user, 'label', '')
            self.channel_id: str          = utils.get_key_safe(_user, 'channel_id', None)
            self.to_bot: bool             = utils.get_key_safe(_user, 'to_bot', True)
            self.to_channel: bool         = utils.get_key_safe(_user, 'to_channel', False)
            self.ping_job                 = utils.get_key_safe(_user, 'ping_job', None)
            self.awaiting_ip: bool        = utils.get_key_safe(_user, 'awaiting_ip', False)
            self.awaiting_label: bool     = utils.get_key_safe(_user, 'awaiting_label', False)
            self.awaiting_channel: bool   = utils.get_key_safe(_user, 'awaiting_channel', False)
            self.last_state: str          = utils.get_key_safe(_state, 'last_state', None)

            date_str = utils.get_key_safe(_state, 'last_ts', None)
            if date_str:
                self.last_ts = datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
            else: self.last_ts = None
            date_str = utils.get_key_safe(_state, 'last_heared_ts', None)
            if date_str:
                self.last_heared_ts = datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
            else: self.last_heared_ts = None
            self.new = False
        self.save()

    def save(self):
        self.refresh()
        save_user_settings()
        save_user_states()

    def save_state(self):
        self.refresh()
        save_user_states()

    def refresh(self):
        _user = utils.get_key_safe(user_settings, self.user_id, {})
        _user['chat_id']          = self.chat_id
        _user['ip_address']       = self.ip_address
        _user['listener']         = self.listener
        _user['label']            = self.label
        _user['channel_id']       = self.channel_id
        _user['to_bot']           = self.to_bot
        _user['to_channel']       = self.to_channel
        _user['ping_job']         = self.ping_job
        _user['awaiting_ip']      = self.awaiting_ip
        _user['awaiting_label']   = self.awaiting_label
        _user['awaiting_channel'] = self.awaiting_channel
        _state = utils.get_key_safe(user_states, self.user_id, {})
        _state['last_state']     = self.last_state
        if self.last_ts:
            _state['last_ts'] = self.last_ts.strftime('%Y-%m-%d %H:%M:%S')
        if self.last_heared_ts:
            _state['last_heared_ts'] = self.last_heared_ts.strftime('%Y-%m-%d %H:%M:%S')
        user_settings[self.user_id] = _user
        user_states[self.user_id]   = _state

# Load user settings from file
def load_user_settings():
    if os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, 'r') as file:
            return json.load(file)
    return {}

# Load user states from file
def load_user_states():
    if os.path.exists(STATES_FILE):
        with open(STATES_FILE, 'r') as file:
            return json.load(file)
    return {}

# Save user settings to file
def save_user_settings():
    with open(SETTINGS_FILE, 'w') as file:
        json.dump(user_settings, file)

# Save user states to file
def save_user_states():
    with open(STATES_FILE, 'w') as file:
        json.dump(user_states, file)

# Dictionary to store user-specific settings
user_settings = load_user_settings()
user_states   = load_user_states()
user_jobs     = {}
listeners     = {}