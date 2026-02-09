import os
import json
from config import SETTINGS_FILE, STATES_FILE, TZ
import utils
#from db.models import User as db_user, Spot as db_spot, SpotState as db_spotstate, SpotJournal as db_spotjournal, SpotNotification as db_notification
from structure.user import Userdb
from structure.spot import Spot
from structure.notification import Notification
from datetime import datetime, timedelta
import logging, traceback, schedule, time, threading, pytz, json
from logging.handlers import TimedRotatingFileHandler
import pytz

# Create a logger
logger = logging.getLogger('eSvitlo-user-settings')
logger.setLevel(logging.DEBUG)

# Create a file handler
fh = TimedRotatingFileHandler('./logs/esvitlo.log', encoding='utf-8', when="D", interval=1, backupCount=30)
fh.setLevel(logging.INFO)

# Create a console handler
ch = logging.StreamHandler()
ch.setLevel(logging.ERROR)

# Create a formatter
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
fh.setFormatter(formatter)
ch.setFormatter(formatter)

# Add handlers to the logger
logger.addHandler(fh)
logger.addHandler(ch)

use_tz = pytz.timezone(TZ)


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
            self.awaiting_city: bool      = False
            self.awaiting_group: bool     = False
            self.has_schedule             = False
            self.city                     = None
            self.group                    = None
            self.to_remind                = False
            self.to_telegram              = True
            self.endpoint                 = None
            self.headers                  = None
            self.last_state: str          = None
            self.last_ts: datetime        = None
            self.last_heared_ts: datetime = None
            self.next_notification_ts: datetime = None
            self.next_outage_ts: datetime = None
            self.tom_notification_ts: datetime = None
            self.tom_schedule_ts: datetime= None
            self.new                      = True
            self.save()
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
            self.awaiting_city: bool      = utils.get_key_safe(_user, 'awaiting_city', False)
            self.awaiting_group: bool     = utils.get_key_safe(_user, 'awaiting_group', False)
            self.has_schedule: bool       = utils.get_key_safe(_user, 'has_schedule', False)
            self.city: str                = utils.get_key_safe(_user, 'city', None)
            self.group: str               = utils.get_key_safe(_user, 'group', None)
            self.to_remind: bool          = utils.get_key_safe(_user, 'to_remind', False)
            self.to_telegram: bool        = utils.get_key_safe(_user, 'to_telegram', True)
            self.endpoint: str            = utils.get_key_safe(_user, 'endpoint', None)
            self.headers: str             = utils.get_key_safe(_user, 'headers', None)
            self.last_state: str          = utils.get_key_safe(_state, 'last_state', None)

            date_str = utils.get_key_safe(_state, 'last_ts', None)
            if date_str:
                self.last_ts = datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
            else: self.last_ts = None
            date_str = utils.get_key_safe(_state, 'last_heared_ts', None)
            if date_str:
                self.last_heared_ts = datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
            else: self.last_heared_ts = None
            date_str = utils.get_key_safe(_state, 'next_notification_ts', None)
            if date_str:
                self.next_notification_ts = datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
            else: self.next_notification_ts = None
            date_str = utils.get_key_safe(_state, 'next_outage_ts', None)
            if date_str:
                self.next_outage_ts = datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
            else: self.next_outage_ts = None
            date_str = utils.get_key_safe(_state, 'tom_notification_ts', None)
            if date_str:
                self.tom_notification_ts = datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
            else: self.tom_notification_ts = None
            date_str = utils.get_key_safe(_state, 'tom_schedule_ts', None)
            if date_str:
                self.tom_schedule_ts = datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
            else: self.tom_schedule_ts = None
            self.new = False

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
        _user['awaiting_city']    = self.awaiting_city
        _user['awaiting_group']   = self.awaiting_group
        _user['has_schedule']     = self.has_schedule
        _user['city']             = self.city
        _user['group']            = self.group
        _user['to_remind']        = self.to_remind
        _user['to_telegram']      = self.to_telegram
        _user['endpoint']         = self.endpoint
        _user['headers']          = self.headers
        _state = utils.get_key_safe(user_states, self.user_id, {})
        _state['last_state'] = self.last_state
        if self.last_ts and isinstance(self.last_ts, str): 
            self.last_ts:datetime = datetime.strptime(self.last_ts, '%Y-%m-%d %H:%M:%S')
        if self.last_ts: 
            _state['last_ts'] = self.last_ts.strftime('%Y-%m-%d %H:%M:%S')
        if self.last_heared_ts and isinstance(self.last_heared_ts, str): 
            self.last_heared_ts:datetime = datetime.strptime(self.last_heared_ts, '%Y-%m-%d %H:%M:%S')
        if self.last_heared_ts:
            _state['last_heared_ts'] = self.last_heared_ts.strftime('%Y-%m-%d %H:%M:%S')
        if self.next_notification_ts: 
            _state['next_notification_ts'] = self.next_notification_ts.strftime('%Y-%m-%d %H:%M:%S')
        else: _state['next_notification_ts'] = None
        if self.next_outage_ts:
            _state['next_outage_ts'] = self.next_outage_ts.strftime('%Y-%m-%d %H:%M:%S')
        else: _state['next_outage_ts'] = None
        if self.tom_notification_ts: 
            _state['tom_notification_ts'] = self.tom_notification_ts.strftime('%Y-%m-%d %H:%M:%S')
        else: _state['tom_notification_ts'] = None
        if self.tom_schedule_ts:
            _state['tom_schedule_ts'] = self.tom_schedule_ts.strftime('%Y-%m-%d %H:%M:%S')
        else: _state['tom_schedule_ts'] = None
        user_settings[self.user_id] = _user
        user_states[self.user_id]   = _state

    def toggle_awaiting_ip(self):
        self.awaiting_ip      = True
        self.awaiting_label   = False
        self.awaiting_channel = False
        self.awaiting_city    = False
        self.awaiting_group   = False

    def toggle_awaiting_label(self):
        self.awaiting_ip      = False
        self.awaiting_label   = True
        self.awaiting_channel = False
        self.awaiting_city    = False
        self.awaiting_group   = False

    def toggle_awaiting_channel(self):
        self.awaiting_ip      = False
        self.awaiting_label   = False
        self.awaiting_channel = True
        self.awaiting_city    = False
        self.awaiting_group   = False

    def toggle_awaiting_city(self):
        self.awaiting_ip      = False
        self.awaiting_label   = False
        self.awaiting_channel = False
        self.awaiting_city    = True
        self.awaiting_group   = False

    def toggle_awaiting_group(self):
        self.awaiting_ip      = False
        self.awaiting_label   = False
        self.awaiting_channel = False
        self.awaiting_city    = False
        self.awaiting_group   = True

    def toggle_nowait(self):
        self.awaiting_ip      = False
        self.awaiting_label   = False
        self.awaiting_channel = False
        self.awaiting_city    = False
        self.awaiting_group   = False

# Load user settings from file
def load_user_settings():
    if os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, 'r', encoding='utf-8-sig') as file:
            return json.load(file)

# Load user states from file
def load_user_states():
    if os.path.exists(STATES_FILE):
        with open(STATES_FILE, 'r') as file:
            return json.load(file)
    return {}

# Save user settings to file
def save_user_settings():
    with open(SETTINGS_FILE, 'w') as file:
        json.dump(user_settings, file, indent=2)

# Load user settings to DB
def sync_user_settings():
    if os.path.exists('user_settings_sync.flag'):
        return
    logger.info('Start sync user settings to DB')
    delta   = timedelta(hours=3)
    for user_id in user_settings.keys():
        chat_id = user_settings[user_id]['chat_id']
        user    = User(user_id, chat_id)
        userdb  = Userdb(int(user_id))
        userdb.new = False
        spot_id = str(user_id)
        spotdb  = Spot(userdb.user_id, spot_id)
        spotdb.ip_address = user.ip_address
        spotdb.listener = user.listener
        spotdb.label = user.label
        spotdb.channel_id=user.channel_id
        spotdb.to_bot=user.to_bot
        spotdb.to_channel=user.to_channel
        spotdb.ping_job=user.ping_job
        spotdb.awaiting_ip=user.awaiting_ip
        spotdb.awaiting_label=user.awaiting_label
        spotdb.awaiting_channel=user.awaiting_channel
        spotdb.awaiting_city=user.awaiting_city
        spotdb.awaiting_group=user.awaiting_group
        spotdb.has_schedule=user.has_schedule
        spotdb.city=user.city
        spotdb.group=user.group
        spotdb.endpoint=None if str(user.endpoint) == 'None' else str(user.endpoint)
        spotdb.headers=None if str(user.headers) == 'None' else str(user.headers)
        if spotdb.endpoint:
            spotdb.api_details='1001f89cc4'
        else: spotdb.api_details=None 
        spotdb.to_remind=user.to_remind
        spotdb.to_telegram=user.to_telegram
        spotdb.last_state=user.last_state
        if user.last_ts:
            spotdb.last_ts=user.last_ts + delta
        if user.last_heared_ts:
            spotdb.last_heared_ts=user.last_heared_ts + delta
        notification1 = Notification(chat_id, 'next_outage')
        notification1.next_notification_ts=user.next_notification_ts
        notification1.next_event_ts=user.next_outage_ts
        notification2 = Notification(chat_id, 'tomorrow_schedule')
        notification2.next_notification_ts=user.tom_notification_ts
        notification2.next_event_ts=user.tom_schedule_ts
        user          = None
        userdb        = None
        spotdb        = None
        notification1 = None
        notification2 = None
    with open('user_settings_sync.flag', 'w') as file:
        json.dump({"syncronized":str(datetime.now())}, file, indent=2)


# Save user states to file
def save_user_states():
    delta   = timedelta(hours=3)
    for user_id in user_settings.keys():
        chat_id = user_settings[user_id]['chat_id']
        user    = User(user_id, chat_id)
        spot_id = str(user_id)
        spotdb  = Spot(int(user_id), spot_id)
        if user.last_state and not spotdb.last_state==user.last_state:
            spotdb.new_state(user.last_state)
        if user.last_ts:
            spotdb.last_ts=user.last_ts + delta
        if user.last_heared_ts:
            spotdb.last_heared_ts=user.last_heared_ts + delta
        notification1 = Notification(chat_id, 'next_outage')
        notification1.next_notification_ts=user.next_notification_ts
        notification1.next_event_ts=user.next_outage_ts
        notification2 = Notification(chat_id, 'tomorrow_schedule')
        notification2.next_notification_ts=user.tom_notification_ts
        notification2.next_event_ts=user.tom_schedule_ts
    with open(STATES_FILE, 'w') as file:
        json.dump(user_states, file, indent=2)

# Dictionary to store user-specific settings
user_settings = load_user_settings()
user_states   = load_user_states()
user_jobs     = {}
listeners     = {}