import os
import json
from config import SETTINGS_FILE, STATES_FILE, TZ
import utils
import db
from db.models import User as db_user, Spot as db_spot, SpotState as db_spotstate, SpotJournal as db_spotjournal, SpotNotification as db_notification
from db.database import SessionMain
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

class Userdb:
    def __get_from_db(self):
        try:
            user_from_db = self.__session.query(db_user).filter_by(user_id=self.__user_id).first()
            self.__user_id   = user_from_db.user_id
            self.__new       = (user_from_db.new == 1)
            self.__num_spots = user_from_db.num_spots
            self.__is_active = (user_from_db.is_active == 1)
            self.__ts_ins    = user_from_db.ts_ins
        except Exception as e:
            logger.error(f'Error getting user from DB: {traceback.format_exc()}')

    def __init__(self, in_user_id: int):
        self.__session         = SessionMain()
        self.__user_id:int     = in_user_id
        self.__new:bool        = True
        self.__num_spots:int   = 0
        self.__is_active:bool  = True
        self.__ts_ins:datetime = datetime.now(use_tz)
        user_from_db = self.__session.query(db_user).filter_by(user_id=in_user_id).first()
        if not user_from_db:
            new_user = db_user(user_id=in_user_id, new=1, num_spots=0, is_active=1, ts_ins=datetime.now(use_tz))
            self.__session.add(new_user)
            self.__session.commit()
        self.__get_from_db()

    def __del__(self):
        SessionMain.remove()

    @property
    def user_id(self):
        return self.__user_id
    
    @property
    def new(self):
        self.__get_from_db()
        return self.__new
    
    @property
    def num_spots(self):
        self.__get_from_db()
        return self.__num_spots
    
    @property
    def is_active(self):
        self.__get_from_db()
        return self.__is_active
    
    def __get_user_for_update(self):
        return self.__session.query(db_user).filter_by(user_id=self.__user_id).first()
    
    def remove():
        SessionMain.remove()
    
    @new.setter
    def new(self, value: bool):
        user_to_update = self.__get_user_for_update()
        if not user_to_update.new == (1 if value else 0):
            user_to_update.new = (1 if value else 0)
            self.__session.commit()

    @num_spots.setter
    def num_spots(self, value: int):
        user_to_update = self.__get_user_for_update()
        if not user_to_update.num_spots == value:
            user_to_update.num_spots = value
            self.__session.commit()

    @is_active.setter
    def is_active(self, value: bool):
        user_to_update = self.__get_user_for_update()
        if not user_to_update.is_active == (1 if value else 0):
            user_to_update.is_active = (1 if value else 0)
            self.__session.commit()

class Spot:
    def __get_from_db(self):
        try:
            spot_from_db = self.__session.query(db_spot).filter_by(chat_id=self.__chat_id).first()
            self.__chat_id          = spot_from_db.chat_id
            self.__user_id          = spot_from_db.user_id
            self.__ip_address       = spot_from_db.ip_address
            self.__listener         = (spot_from_db.listener == 1)
            self.__label            = spot_from_db.label
            self.__channel_id       = spot_from_db.channel_id
            self.__to_bot           = (spot_from_db.to_bot == 1)
            self.__to_channel       = (spot_from_db.to_channel == 1)
            self.__ping_job         = spot_from_db.ping_job
            self.__awaiting_ip      = (spot_from_db.awaiting_ip == 1)
            self.__awaiting_label   = (spot_from_db.awaiting_label == 1)
            self.__awaiting_channel = (spot_from_db.awaiting_channel == 1)
            self.__awaiting_city    = (spot_from_db.awaiting_city == 1)
            self.__awaiting_group   = (spot_from_db.awaiting_group == 1)
            self.__has_schedule     = (spot_from_db.has_schedule == 1)
            self.__city             = spot_from_db.city
            self.__group            = spot_from_db.sch_group
            self.__endpoint         = spot_from_db.endpoint
            self.__headers          = spot_from_db.headers
            self.__api_details      = spot_from_db.api_details 
            self.__interval         = spot_from_db.interval
            self.__to_remind        = (spot_from_db.to_remind == 1)
            self.__ts_ins           = spot_from_db.ts_ins
            self.__ts_upd           = spot_from_db.ts_upd

            spot_state_from_db = self.__session.query(db_spotstate).filter_by(chat_id=self.__chat_id).first()
            self.__last_state     = spot_state_from_db.last_state
            self.__last_ts        = spot_state_from_db.last_ts
            self.__last_heared_ts = spot_state_from_db.last_heared_ts
        except Exception as e:
            logger.error(f'Error getting spot from DB: {traceback.format_exc()}')

    def __init__(self, in_user_id: int, in_chat_id: str):
        self.__session               = SessionMain()
        self.__chat_id:str           = in_chat_id
        self.__user_id:int           = in_user_id
        self.__ip_address:str        = None
        self.__listener:bool         = False
        self.__label:str             = None
        self.__channel_id:str        = None
        self.__to_bot:bool           = True
        self.__to_channel:bool       = False
        self.__ping_job:str          = None
        self.__awaiting_ip:bool      = False
        self.__awaiting_label:bool   = False
        self.__awaiting_channel:bool = False
        self.__awaiting_city:bool    = False
        self.__awaiting_group:bool   = False
        self.__has_schedule:bool     = False
        self.__city:str              = None
        self.__group:str             = None
        self.__endpoint:str          = None
        self.__headers:str           = None
        self.__api_details:str       = None
        self.__interval:int          = None
        self.__to_remind:bool        = False
        self.__ts_ins:datetime       = datetime.now(use_tz)
        self.__ts_upd:datetime       = datetime.now(use_tz)
        self.__last_state:str        = None
        self.__last_ts:datetime      = None
        self.__last_heared_ts:datetime = None

        spot_from_db = self.__session.query(db_spot).filter_by(chat_id=in_chat_id).first()
        if not spot_from_db:
            new_spot = db_spot(user_id=in_user_id, chat_id=in_chat_id, ts_ins=datetime.now(use_tz), ts_upd=datetime.now(use_tz))
            self.__session.add(new_spot)
            new_spot_state = db_spotstate(chat_id=in_chat_id)
            self.__session.add(new_spot_state)
            new_spot_journal = db_spotjournal(chat_id=in_chat_id, from_ts=datetime.now(use_tz), active_record=1)
            self.__session.add(new_spot_journal)
            user_to_update = self.__session.query(db_user).filter_by(user_id=in_user_id).first()
            user_to_update.num_spots += 1
            self.__session.commit()
        self.__get_from_db()

    def __del__(self):
        SessionMain.remove()

    @property
    def chat_id(self):
        return self.__chat_id
    
    @property
    def user_id(self):
        return self.__user_id
    
    @property
    def ip_address(self):
        self.__get_from_db()
        return self.__ip_address
    
    @property
    def listener(self):
        self.__get_from_db()
        return self.__listener
    
    @property
    def label(self):
        self.__get_from_db()
        return self.__label

    @property
    def channel_id(self):
        self.__get_from_db()
        return self.__channel_id
    
    @property
    def to_bot(self):
        self.__get_from_db()
        return self.__to_bot
    
    @property
    def to_channel(self):
        self.__get_from_db()
        return self.__to_channel
    
    @property
    def ping_job(self):
        self.__get_from_db()
        return self.__ping_job
    
    @property
    def awaiting_ip(self):
        self.__get_from_db()
        return self.__awaiting_ip
    
    @property
    def awaiting_label(self):
        self.__get_from_db()
        return self.__awaiting_label
    
    @property
    def awaiting_channel(self):
        self.__get_from_db()
        return self.__awaiting_channel
    
    @property
    def awaiting_city(self):
        self.__get_from_db()
        return self.__awaiting_city
    
    @property
    def awaiting_group(self):
        self.__get_from_db()
        return self.__awaiting_group
    
    @property
    def has_schedule(self):
        self.__get_from_db()
        return self.__has_schedule
    
    @property
    def city(self):
        self.__get_from_db()
        return self.__city
    
    @property
    def group(self):
        self.__get_from_db()
        return self.__group
    
    @property
    def endpoint(self):
        self.__get_from_db()
        return self.__endpoint
    
    @property
    def headers(self):
        self.__get_from_db()
        return self.__headers
    
    @property
    def api_details(self):
        self.__get_from_db()
        return self.__api_details
    
    @property
    def interval(self):
        self.__get_from_db()
        return self.__interval
    
    @property
    def to_remind(self):
        self.__get_from_db()
        return self.__to_remind
    
    @property
    def ts_ins(self):
        self.__get_from_db()
        return self.__ts_ins
    
    @property
    def ts_upd(self):
        self.__get_from_db()
        return self.__ts_upd
    
    @property
    def last_state(self):
        self.__get_from_db()
        return self.__last_state
    
    @property
    def last_ts(self):
        self.__get_from_db()
        return self.__last_ts
    
    @property
    def last_heared_ts(self):
        self.__get_from_db()
        return self.__last_heared_ts
    
    def __get_spot_for_update(self):
        return self.__session.query(db_spot).filter_by(chat_id=self.__chat_id).first()
    
    def remove():
        SessionMain.remove()
    
    @ip_address.setter
    def ip_address(self, value: str):
        spot_to_update = self.__get_spot_for_update()
        if not spot_to_update.ip_address == value:
            spot_to_update.ip_address = value
            spot_to_update.ts_upd = datetime.now(use_tz)
            self.__session.commit()

    @listener.setter
    def listener(self, value: bool):
        spot_to_update = self.__get_spot_for_update()
        if not spot_to_update.listener == (1 if value else 0):
            spot_to_update.listener = (1 if value else 0)
            spot_to_update.ts_upd = datetime.now(use_tz)
            self.__session.commit()

    @label.setter
    def label(self, value: str):
        spot_to_update = self.__get_spot_for_update()
        if not spot_to_update.label == value:
            spot_to_update.label = value
            spot_to_update.ts_upd = datetime.now(use_tz)
            self.__session.commit()

    @channel_id.setter
    def channel_id(self, value: str):
        spot_to_update = self.__get_spot_for_update()
        if not spot_to_update.channel_id == value:
            spot_to_update.channel_id = value
            spot_to_update.ts_upd = datetime.now(use_tz)
            self.__session.commit()

    @to_bot.setter
    def to_bot(self, value: bool):
        spot_to_update = self.__get_spot_for_update()
        if not spot_to_update.to_bot == (1 if value else 0):
            spot_to_update.to_bot = (1 if value else 0)
            spot_to_update.ts_upd = datetime.now(use_tz)
            self.__session.commit()

    @to_channel.setter
    def to_channel(self, value: bool):
        spot_to_update = self.__get_spot_for_update()
        if not spot_to_update.to_channel == (1 if value else 0):
            spot_to_update.to_channel = (1 if value else 0)
            spot_to_update.ts_upd = datetime.now(use_tz)
            self.__session.commit()

    @ping_job.setter
    def ping_job(self, value: str):
        spot_to_update = self.__get_spot_for_update()
        if not spot_to_update.ping_job == value:
            spot_to_update.ping_job = value
            spot_to_update.ts_upd = datetime.now(use_tz)
            self.__session.commit()

    @awaiting_ip.setter
    def awaiting_ip(self, value: bool):
        spot_to_update = self.__get_spot_for_update()
        if not spot_to_update.awaiting_ip == (1 if value else 0):
            spot_to_update.awaiting_ip = (1 if value else 0)
            spot_to_update.ts_upd = datetime.now(use_tz)
            self.__session.commit()

    @awaiting_label.setter
    def awaiting_label(self, value: bool):
        spot_to_update = self.__get_spot_for_update()
        if not spot_to_update.awaiting_label == (1 if value else 0):
            spot_to_update.awaiting_label = (1 if value else 0)
            spot_to_update.ts_upd = datetime.now(use_tz)
            self.__session.commit()

    @awaiting_channel.setter
    def awaiting_channel(self, value: bool):
        spot_to_update = self.__get_spot_for_update()
        if not spot_to_update.awaiting_channel == (1 if value else 0):
            spot_to_update.awaiting_channel = (1 if value else 0)
            spot_to_update.ts_upd = datetime.now(use_tz)
            self.__session.commit()

    @awaiting_city.setter
    def awaiting_city(self, value: bool):
        spot_to_update = self.__get_spot_for_update()
        if not spot_to_update.awaiting_city == (1 if value else 0):
            spot_to_update.awaiting_city = (1 if value else 0)
            spot_to_update.ts_upd = datetime.now(use_tz)
            self.__session.commit()

    @awaiting_group.setter
    def awaiting_group(self, value: bool):
        spot_to_update = self.__get_spot_for_update()
        if not spot_to_update.awaiting_group == (1 if value else 0):
            spot_to_update.awaiting_group = (1 if value else 0)
            spot_to_update.ts_upd = datetime.now(use_tz)
            self.__session.commit()

    @has_schedule.setter
    def has_schedule(self, value: bool):
        spot_to_update = self.__get_spot_for_update()
        if not spot_to_update.has_schedule == (1 if value else 0):
            spot_to_update.has_schedule = (1 if value else 0)
            spot_to_update.ts_upd = datetime.now(use_tz)
            self.__session.commit()

    @city.setter
    def city(self, value: str):
        spot_to_update = self.__get_spot_for_update()
        if not spot_to_update.city == value:
            spot_to_update.city = value
            spot_to_update.ts_upd = datetime.now(use_tz)
            self.__session.commit()

    @group.setter
    def group(self, value: str):
        spot_to_update = self.__get_spot_for_update()
        if not spot_to_update.sch_group == value:
            spot_to_update.sch_group = value
            spot_to_update.ts_upd = datetime.now(use_tz)
            self.__session.commit()

    @endpoint.setter
    def endpoint(self, value: str):
        spot_to_update = self.__get_spot_for_update()
        if not spot_to_update.endpoint == value:
            spot_to_update.endpoint = value
            spot_to_update.ts_upd = datetime.now(use_tz)
            self.__session.commit()

    @headers.setter
    def headers(self, value: str):
        spot_to_update = self.__get_spot_for_update()
        if not spot_to_update.headers == value:
            spot_to_update.headers = value
            spot_to_update.ts_upd = datetime.now(use_tz)
            self.__session.commit()

    @api_details.setter
    def api_details(self, value: str):
        spot_to_update = self.__get_spot_for_update()
        if not spot_to_update.api_details == value:
            spot_to_update.api_details = value
            spot_to_update.ts_upd = datetime.now(use_tz)
            self.__session.commit()

    @interval.setter
    def interval(self, value: int):
        spot_to_update = self.__get_spot_for_update()
        if not spot_to_update.interval == value:
            spot_to_update.interval = value
            spot_to_update.ts_upd = datetime.now(use_tz)
            self.__session.commit()

    @to_remind.setter
    def to_remind(self, value: bool):
        spot_to_update = self.__get_spot_for_update()
        if not spot_to_update.to_remind == (1 if value else 0):
            spot_to_update.to_remind = (1 if value else 0)
            spot_to_update.ts_upd = datetime.now(use_tz)
            self.__session.commit()

    @last_state.setter
    def last_state(self, value: str):
        spotstate_to_update = self.__session.query(db_spotstate).filter_by(chat_id=self.__chat_id).first()
        if (value and spotstate_to_update.last_state and not spotstate_to_update.last_state == value) or (value and not spotstate_to_update.last_state):
            spotstate_to_update.last_state = value
            self.__session.commit()

    @last_ts.setter
    def last_ts(self, value: datetime):
        spotstate_to_update = self.__session.query(db_spotstate).filter_by(chat_id=self.__chat_id).first()
        journal_to_update   = self.__session.query(db_spotjournal).filter_by(chat_id=self.__chat_id, active_record=1).first()
        if not journal_to_update:
            journal_to_update = db_spotjournal(chat_id=self.__chat_id, spot_state=value, last_ts=value, 
                                               last_heared_ts=spotstate_to_update.last_heared_ts, from_ts=value, active_record=1)
        if value and not spotstate_to_update.last_ts == value:
            journal_to_update.last_ts   = value
            spotstate_to_update.last_ts = value
            self.__session.commit()

    @last_heared_ts.setter
    def last_heared_ts(self, value: datetime):
        spotstate_to_update = self.__session.query(db_spotstate).filter_by(chat_id=self.__chat_id).first()
        journal_to_update   = self.__session.query(db_spotjournal).filter_by(chat_id=self.__chat_id, active_record=1).first()
        if not journal_to_update:
            journal_to_update = db_spotjournal(chat_id=self.__chat_id, spot_state=spotstate_to_update.last_state, last_ts=value, 
                                               last_heared_ts=spotstate_to_update.last_heared_ts, from_ts=value, active_record=1)
        if value and not spotstate_to_update.last_heared_ts == value:
            journal_to_update.last_heared_ts   = value
            spotstate_to_update.last_heared_ts = value
            self.__session.commit()

    def new_state(self, value: str):
        if not value: return
        spotstate_to_update = self.__session.query(db_spotstate).filter_by(chat_id=self.__chat_id).first()
        journal_to_update   = self.__session.query(db_spotjournal).filter_by(chat_id=self.__chat_id, active_record=1).first()
        spotstate_to_update.last_ts = datetime.now(use_tz)
        if not journal_to_update:
            journal_to_update = db_spotjournal(chat_id=self.__chat_id, spot_state=value, last_ts=spotstate_to_update.last_ts, 
                                               last_heared_ts=spotstate_to_update.last_heared_ts, from_ts=spotstate_to_update.last_ts, active_record=1)
        if spotstate_to_update.last_state and not spotstate_to_update.last_state == value:
           if not journal_to_update.spot_state == value:
                journal_to_update.to_ts         = datetime.now(use_tz)
                journal_to_update.active_record = 0
                new_journal = db_spotjournal(chat_id=self.__chat_id, spot_state=value, last_ts=spotstate_to_update.last_ts, 
                                            last_heared_ts=spotstate_to_update.last_heared_ts, from_ts=spotstate_to_update.last_ts, active_record=1)
                self.__session.add(new_journal)
        elif not spotstate_to_update.last_state:
            if not journal_to_update.spot_state == value:
                journal_to_update.spot_state = value
                journal_to_update.last_ts    = datetime.now(use_tz)
                journal_to_update.from_ts    = datetime.now(use_tz)
        spotstate_to_update.last_state = value
        self.__session.commit()

    def toggle_awaiting_ip(self):
        spot_to_update = self.__get_spot_for_update()
        spot_to_update.awaiting_ip      = 1
        spot_to_update.awaiting_label   = 0
        spot_to_update.awaiting_channel = 0
        spot_to_update.awaiting_city    = 0
        spot_to_update.awaiting_group   = 0
        self.__session.commit()

    def toggle_awaiting_label(self):
        spot_to_update = self.__get_spot_for_update()
        spot_to_update.awaiting_ip      = 0
        spot_to_update.awaiting_label   = 1
        spot_to_update.awaiting_channel = 0
        spot_to_update.awaiting_city    = 0
        spot_to_update.awaiting_group   = 0
        self.__session.commit()

    def toggle_awaiting_channel(self):
        spot_to_update = self.__get_spot_for_update()
        spot_to_update.awaiting_ip      = 0
        spot_to_update.awaiting_label   = 0
        spot_to_update.awaiting_channel = 1
        spot_to_update.awaiting_city    = 0
        spot_to_update.awaiting_group   = 0
        self.__session.commit()

    def toggle_awaiting_city(self):
        spot_to_update = self.__get_spot_for_update()
        spot_to_update.awaiting_ip      = 0
        spot_to_update.awaiting_label   = 0
        spot_to_update.awaiting_channel = 0
        spot_to_update.awaiting_city    = 1
        spot_to_update.awaiting_group   = 0
        self.__session.commit()

    def toggle_awaiting_group(self):
        spot_to_update = self.__get_spot_for_update()
        spot_to_update.awaiting_ip      = 0
        spot_to_update.awaiting_label   = 0
        spot_to_update.awaiting_channel = 0
        spot_to_update.awaiting_city    = 0
        spot_to_update.awaiting_group   = 1
        self.__session.commit()

    def toggle_nowait(self):
        spot_to_update = self.__get_spot_for_update()
        spot_to_update.awaiting_ip      = 0
        spot_to_update.awaiting_label   = 0
        spot_to_update.awaiting_channel = 0
        spot_to_update.awaiting_city    = 0
        spot_to_update.awaiting_group   = 0
        self.__session.commit()

class Notification:
    def __get_from_db(self):
        try:
            notification_from_db = self.__session.query(db_notification).filter_by(chat_id=self.__chat_id).first()
            self.__chat_id              = notification_from_db.chat_id
            self.__notification_type    = notification_from_db.notification_type
            self.__next_notification_ts = notification_from_db.next_notification_ts
            self.__next_event_ts        = notification_from_db.next_event_ts
        except Exception as e:
            logger.error(f'Error getting notifications from DB: {traceback.format_exc()}')

    def __init__(self, in_chat_id: str, in_notification_type: str):
        self.__session              = SessionMain()
        self.__chat_id              = in_chat_id
        self.__notification_type    = in_notification_type
        self.__next_notification_ts = None
        self.__next_event_ts        = None
        notification_from_db = self.__session.query(db_notification).filter_by(chat_id=in_chat_id, notification_type=in_notification_type).first()
        if not notification_from_db:
            new_notification = db_notification(chat_id=in_chat_id, notification_type=in_notification_type)
            self.__session.add(new_notification)
            self.__session.commit()
        self.__get_from_db()

    def __del__(self):
        SessionMain.remove()

    def __get_notification_for_update(self):
        return self.__session.query(db_notification).filter_by(chat_id=self.__chat_id, notification_type=self.__notification_type).first()
    
    def remove():
        SessionMain.remove()

    @property
    def chat_id(self):
        return self.__chat_id
    
    @property
    def notification_type(self):
        return self.__notification_type
    
    @property
    def next_notification_ts(self):
        self.__get_from_db()
        return self.__next_notification_ts
    
    @property
    def next_event_ts(self):
        self.__get_from_db()
        return self.__next_event_ts
    
    @next_notification_ts.setter
    def next_notification_ts(self, value: datetime):
        notification_for_update = self.__get_notification_for_update()
        if not notification_for_update.next_notification_ts or not value == notification_for_update.next_notification_ts:
            notification_for_update.next_notification_ts = value
            self.__session.commit()

    @next_event_ts.setter
    def next_event_ts(self, value: datetime):
        notification_for_update = self.__get_notification_for_update()
        if not notification_for_update.next_event_ts or not value == notification_for_update.next_event_ts:
            notification_for_update.next_event_ts = value
            self.__session.commit()

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
    logger.info('Start sync user settings to DB')
    delta   = timedelta(hours=3)
    for user_id in user_settings.keys():
        chat_id = user_settings[user_id]['chat_id']
        user    = User(user_id, chat_id)
        userdb  = Userdb(int(user_id))
        userdb.new = False
        spot_id = str(user_id)
        spotdb  = Spot(userdb.user_id, spot_id)
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
        spotdb.endpoint=str(user.endpoint)
        spotdb.headers=str(user.headers)
        if spotdb.endpoint:
            spotdb.api_details='1001f89cc4'
        spotdb.to_remind=user.to_remind
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
        userdb.remove()
        spotdb.remove()
        notification1.remove()
        notification2.remove()
        user          = None
        userdb        = None
        spotdb        = None
        notification1 = None
        notification2 = None

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