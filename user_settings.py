import os
import json
from config import SETTINGS_FILE, STATES_FILE, TZ
import utils
import db
from datetime import datetime
import pytz

use_tz = pytz.timezone(TZ)

sql_user_select = "SELECT user_id, new, ts_ins FROM user WHERE user_id = ?;"
sql_user_insert = "INSERT INTO user (user_id, new, ts_ins) VALUES (?, ?, ?);"
sql_user_update = "UPDATE user SET ? = ? WHERE user_id = ?;"
sql_spot_select = "SELECT chat_id, user_id, ip_address, listener, label, channel_id, to_bot, to_channel, ping_job,awaiting_ip, awaiting_label, awaiting_channel, awaiting_city, awaiting_group, has_schedule, city, sch_group, to_remind, ts_ins, ts_upd FROM spot WHERE chat_id = ?;"
sql_spot_insert = "INSERT INTO spot (chat_id, user_id, ts_ins, ts_upd) VALUES (?, ?, ?, ?);"
sql_spot_state_select = "SELECT chat_id, last_state, last_ts, last_heared_ts FROM spot_state WHERE chat_id = ?;"
sql_spot_state_select = "SELECT chat_id, last_state, last_ts, last_heared_ts FROM spot_state WHERE chat_id = ?;"

class Userdb:
    def __get_from_db(self):
        db.cur.execute(sql_user_select, (self.__user_id,))
        records = db.cur.fetchall()
        for row in records:
            self.__user_id = row[0]
            self.__new     = (row[1] == 1)
            self.__ts_ins  = row[2]

    def __init__(self, user_id: str):
        db.cur.execute(sql_user_select, (user_id,))
        records = db.cur.fetchall()
        for row in records:
            self.__user_id = row[0]
            self.__new     = (row[1] == 1)
            self.__ts_ins  = row[2]
        if not self.__user_id:
            self.__user_id = user_id
            self.__new     = True
            self.__ts_ins  = datetime.now(use_tz)
            db.cur.execute(sql_user_insert, (user_id, 1, self.__ts_ins))
        db.con.commit()


    def exists(user_id: str):
        db.cur.execute(sql_user_select, (user_id,))
        records = db.cur.fetchall()
        for row in records:
            id = row[0]
        return True if id else False

    @property
    def new(self):
        self.__get_from_db()
        return self.__new
    
    @new.setter
    def new(self, new: bool):
        self.__new = new
        db.cur.execute(sql_user_update, ('new', {1 if new else 0}, self.__user_id))
        db.con.commit()

class Spot:
    def __get_from_db(self):
        db.cur.execute(sql_spot_select, (self.__chat_id,))
        records = db.cur.fetchall()
        for row in records:
            self.__chat_id          = row[0]
            self.__user_id          = row[1]
            self.__ip_address       = row[2]
            self.__listener         = (row[3] == 1)
            self.__label            = row[4]
            self.__channel_id       = row[5]
            self.__to_bot           = (row[6] == 1)
            self.__to_channel       = (row[7] == 1)
            self.__ping_job         = row[8]
            self.__awaiting_ip      = (row[9] == 1)
            self.__awaiting_label   = (row[10] == 1)
            self.__awaiting_channel = (row[11] == 1)
            self.__awaiting_city    = (row[12] == 1)
            self.__awaiting_group   = (row[13] == 1)
            self.__has_schedule     = (row[14] == 1)
            self.__city             = row[15]
            self.__group            = row[16]
            self.__to_remind        = (row[17] == 1)
            self.__ts_ins           = row[18]
            self.__ts_upd           = row[19]
        db.cur.execute(sql_spot_state_select, (self.__chat_id,))
        records = db.cur.fetchall()
        for row in records:
            self.__last_state     = row[1]
            self.__last_ts        = row[2]
            self.__last_heared_ts = row[3]

    def __init__(self, user_id: int, chat_id: str):
        self.__chat_id = chat_id
        self.__get_from_db()
        if not self.__user_id:
            self.__chat_id = chat_id
            self.__user_id = user_id
            self.__ts_ins  = datetime.now(use_tz)
            self.__ts_upd  = datetime.now(use_tz)
            db.cur.execute(sql_spot_insert, (chat_id, user_id, self.__ts_ins, self.__ts_upd))
        db.con.commit()

    @property
    def chat_id(self):
        return self.__chat_id
    
    @property
    def user_id(self):
        return self.__user_id
    
    @property
    def ip_address(self):
        return self.__ip_address
    
    @property
    def listener(self):
        return self.__listener
    
    @property
    def label(self):
        return self.__label

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
        _user['awaiting_city']    = self.awaiting_city
        _user['awaiting_group']   = self.awaiting_group
        _user['has_schedule']     = self.has_schedule
        _user['city']             = self.city
        _user['group']            = self.group
        _user['to_remind']        = self.to_remind
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