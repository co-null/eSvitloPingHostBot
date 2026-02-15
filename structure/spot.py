from config import TZ
import pytz
from db import models #import User, Spot, SpotState, SpotJournal
#from .user import User
#from .spot import Spot, SpotState, SpotJournal
from db.database import SessionMain
from datetime import datetime

TIMEZONE = pytz.timezone(TZ)

class Spot:
    def __get_from_db(self):
        spot_from_db = self.__session.query(models.Spot).filter_by(chat_id=self.__chat_id).first()
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
        self.__to_telegram      = (spot_from_db.to_telegram == 1)
        self.__ts_ins           = spot_from_db.ts_ins
        self.__ts_upd           = spot_from_db.ts_upd
        self.__is_active        = True if spot_from_db.is_active else (spot_from_db.is_active == 1)

        spot_state_from_db = self.__session.query(models.SpotState).filter_by(chat_id=self.__chat_id).first()
        self.__last_state     = spot_state_from_db.last_state
        self.__last_ts        = spot_state_from_db.last_ts
        self.__last_heared_ts = spot_state_from_db.last_heared_ts

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
        self.__to_telegram:bool      = True
        self.__ts_ins:datetime       = datetime.now(TIMEZONE)
        self.__ts_upd:datetime       = datetime.now(TIMEZONE)
        self.__last_state:str        = None
        self.__last_ts:datetime      = None
        self.__last_heared_ts:datetime = None
        self.__is_active:bool        = True

        spot_from_db = self.__session.query(models.Spot).filter_by(chat_id=in_chat_id).first()
        if not spot_from_db:
            new_spot = models.Spot(user_id=in_user_id, chat_id=in_chat_id, ts_ins=datetime.now(TIMEZONE), ts_upd=datetime.now(TIMEZONE))
            self.__session.add(new_spot)
            new_spot_state = models.SpotState(chat_id=in_chat_id)
            self.__session.add(new_spot_state)
            new_spot_journal = models.SpotJournal(chat_id=in_chat_id, from_ts=datetime.now(TIMEZONE), active_record=1)
            self.__session.add(new_spot_journal)
            user_to_update = self.__session.query(models.User).filter_by(user_id=in_user_id).first()
            user_to_update.num_spots += 1
            self.__session.commit()
        self.__get_from_db()

    def __del__(self):
        SessionMain.remove()

    def refresh(self):
        self.__get_from_db()

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
    
    @property
    def name(self):
        if self.__label and not self.__label == '': name = self.__label
        elif self.__ip_address and not self.__ip_address == '': name = self.__ip_address
        else: name = 'Без назви'
        return name

    @property
    def channel_id(self):
        return self.__channel_id
    
    @property
    def treated_channel_id(self):
        thread_pos = self.__channel_id.find(':')
        if not thread_pos == -1:
            channel = self.__channel_id[:thread_pos]
        else: # No thread
            channel = self.__channel_id
        if str(channel).startswith('-') and str(channel)[1:].isnumeric():
            #Private channel
            channel:int = int(channel)
        return channel
    
    @property
    def thread_id(self) -> int:
        if self.__channel_id:
            thread_pos = self.__channel_id.find(':')
            if not thread_pos == -1:
                return  int(self.__channel_id[thread_pos+1:])
            else: return None
        else: # No thread
            return None
    
    @property
    def to_bot(self):
        return self.__to_bot
    
    @property
    def to_channel(self):
        return self.__to_channel
    
    @property
    def ping_job(self):
        return self.__ping_job
    
    @property
    def awaiting_ip(self):
        return self.__awaiting_ip
    
    @property
    def awaiting_label(self):
         return self.__awaiting_label
    
    @property
    def awaiting_channel(self):
        return self.__awaiting_channel
    
    @property
    def awaiting_city(self):
        return self.__awaiting_city
    
    @property
    def awaiting_group(self):
        return self.__awaiting_group
    
    @property
    def has_schedule(self):
        return self.__has_schedule
    
    @property
    def city(self):
        return self.__city
    
    @property
    def group(self):
        return self.__group
    
    @property
    def endpoint(self):
        return self.__endpoint
    
    @property
    def headers(self):
        return self.__headers
    
    @property
    def api_details(self):
        return self.__api_details
    
    @property
    def interval(self):
        return self.__interval
    
    @property
    def to_remind(self):
        return self.__to_remind

    @property
    def to_telegram(self):
        return self.__to_telegram
   
    @property
    def ts_ins(self):
        return self.__ts_ins
    
    @property
    def ts_upd(self):
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
    
    @property
    def is_active(self):
        return self.__is_active
    
    @property
    def is_multipost(self):
        spots = self.__session.query(models.Spot).filter_by(user_id=self.__user_id, 
                                                            channel_id=self.__channel_id).count()
        return True if spots and spots > 1 else False
    
    def __get_spot_for_update(self):
        return self.__session.query(models.Spot).filter_by(chat_id=self.__chat_id).first()
    
    def get(self):
        self.__get_spot_for_update()
        return self
    
    @ip_address.setter
    def ip_address(self, value: str):
        spot_to_update = self.__get_spot_for_update()
        if not spot_to_update.ip_address == value:
            spot_to_update.ip_address = value
            spot_to_update.ts_upd = datetime.now(TIMEZONE)
            self.__session.commit()

    @listener.setter
    def listener(self, value: bool):
        spot_to_update = self.__get_spot_for_update()
        if not spot_to_update.listener == (1 if value else 0):
            spot_to_update.listener = (1 if value else 0)
            spot_to_update.ts_upd = datetime.now(TIMEZONE)
            self.__session.commit()

    @label.setter
    def label(self, value: str):
        spot_to_update = self.__get_spot_for_update()
        if not spot_to_update.label == value:
            spot_to_update.label = value
            spot_to_update.ts_upd = datetime.now(TIMEZONE)
            self.__session.commit()

    @channel_id.setter
    def channel_id(self, value: str):
        spot_to_update = self.__get_spot_for_update()
        if value:
            if value.startswith('https://t.me/'): value = value.replace('https://t.me/', '')
            thread_pos = value.find(':')
            if not value.startswith('@') and not str(value[:thread_pos])[1:].isnumeric(): value = '@' + value
        if not spot_to_update.channel_id == value:
            spot_to_update.channel_id = value
            spot_to_update.ts_upd = datetime.now(TIMEZONE)
            self.__session.commit()

    @to_bot.setter
    def to_bot(self, value: bool):
        spot_to_update = self.__get_spot_for_update()
        if not spot_to_update.to_bot == (1 if value else 0):
            spot_to_update.to_bot = (1 if value else 0)
            spot_to_update.ts_upd = datetime.now(TIMEZONE)
            self.__session.commit()

    @to_channel.setter
    def to_channel(self, value: bool):
        spot_to_update = self.__get_spot_for_update()
        if not spot_to_update.to_channel == (1 if value else 0):
            spot_to_update.to_channel = (1 if value else 0)
            spot_to_update.ts_upd = datetime.now(TIMEZONE)
            self.__session.commit()

    @ping_job.setter
    def ping_job(self, value: str):
        spot_to_update = self.__get_spot_for_update()
        if not spot_to_update.ping_job == value:
            spot_to_update.ping_job = value
            spot_to_update.ts_upd = datetime.now(TIMEZONE)
            self.__session.commit()

    @awaiting_ip.setter
    def awaiting_ip(self, value: bool):
        spot_to_update = self.__get_spot_for_update()
        if not spot_to_update.awaiting_ip == (1 if value else 0):
            spot_to_update.awaiting_ip = (1 if value else 0)
            spot_to_update.ts_upd = datetime.now(TIMEZONE)
            self.__session.commit()

    @awaiting_label.setter
    def awaiting_label(self, value: bool):
        spot_to_update = self.__get_spot_for_update()
        if not spot_to_update.awaiting_label == (1 if value else 0):
            spot_to_update.awaiting_label = (1 if value else 0)
            spot_to_update.ts_upd = datetime.now(TIMEZONE)
            self.__session.commit()

    @awaiting_channel.setter
    def awaiting_channel(self, value: bool):
        spot_to_update = self.__get_spot_for_update()
        if not spot_to_update.awaiting_channel == (1 if value else 0):
            spot_to_update.awaiting_channel = (1 if value else 0)
            spot_to_update.ts_upd = datetime.now(TIMEZONE)
            self.__session.commit()

    @awaiting_city.setter
    def awaiting_city(self, value: bool):
        spot_to_update = self.__get_spot_for_update()
        if not spot_to_update.awaiting_city == (1 if value else 0):
            spot_to_update.awaiting_city = (1 if value else 0)
            spot_to_update.ts_upd = datetime.now(TIMEZONE)
            self.__session.commit()

    @awaiting_group.setter
    def awaiting_group(self, value: bool):
        spot_to_update = self.__get_spot_for_update()
        if not spot_to_update.awaiting_group == (1 if value else 0):
            spot_to_update.awaiting_group = (1 if value else 0)
            spot_to_update.ts_upd = datetime.now(TIMEZONE)
            self.__session.commit()

    @has_schedule.setter
    def has_schedule(self, value: bool):
        spot_to_update = self.__get_spot_for_update()
        if not spot_to_update.has_schedule == (1 if value else 0):
            spot_to_update.has_schedule = (1 if value else 0)
            spot_to_update.ts_upd = datetime.now(TIMEZONE)
            self.__session.commit()

    @city.setter
    def city(self, value: str):
        spot_to_update = self.__get_spot_for_update()
        if not spot_to_update.city == value:
            spot_to_update.city = value
            spot_to_update.ts_upd = datetime.now(TIMEZONE)
            self.__session.commit()

    @group.setter
    def group(self, value: str):
        spot_to_update = self.__get_spot_for_update()
        if not spot_to_update.sch_group == value:
            spot_to_update.sch_group = value
            spot_to_update.ts_upd = datetime.now(TIMEZONE)
            self.__session.commit()

    @endpoint.setter
    def endpoint(self, value: str):
        spot_to_update = self.__get_spot_for_update()
        if not spot_to_update.endpoint == value:
            spot_to_update.endpoint = value
            spot_to_update.ts_upd = datetime.now(TIMEZONE)
            self.__session.commit()

    @headers.setter
    def headers(self, value: str):
        spot_to_update = self.__get_spot_for_update()
        if not spot_to_update.headers == value:
            spot_to_update.headers = value
            spot_to_update.ts_upd = datetime.now(TIMEZONE)
            self.__session.commit()

    @api_details.setter
    def api_details(self, value: str):
        spot_to_update = self.__get_spot_for_update()
        if not spot_to_update.api_details == value:
            spot_to_update.api_details = value
            spot_to_update.ts_upd = datetime.now(TIMEZONE)
            self.__session.commit()

    @interval.setter
    def interval(self, value: int):
        spot_to_update = self.__get_spot_for_update()
        if not spot_to_update.interval == value:
            spot_to_update.interval = value
            spot_to_update.ts_upd = datetime.now(TIMEZONE)
            self.__session.commit()

    @to_remind.setter
    def to_remind(self, value: bool):
        spot_to_update = self.__get_spot_for_update()
        if not spot_to_update.to_remind == (1 if value else 0):
            spot_to_update.to_remind = (1 if value else 0)
            spot_to_update.ts_upd = datetime.now(TIMEZONE)
            self.__session.commit()

    @to_telegram.setter
    def to_telegram(self, value: bool):
        spot_to_update = self.__get_spot_for_update()
        if not spot_to_update.to_telegram == (1 if value else 0):
            spot_to_update.to_telegram = (1 if value else 0)
            spot_to_update.ts_upd = datetime.now(TIMEZONE)
            self.__session.commit()

    @last_state.setter
    def last_state(self, value: str):
        spotstate_to_update = self.__session.query(models.SpotState).filter_by(chat_id=self.__chat_id).first()
        if (value and spotstate_to_update.last_state and not spotstate_to_update.last_state == value) or (value and not spotstate_to_update.last_state):
            spotstate_to_update.last_state = value
            self.__session.commit()

    @last_ts.setter
    def last_ts(self, value: datetime):
        spotstate_to_update = self.__session.query(models.SpotState).filter_by(chat_id=self.__chat_id).first()
        journal_to_update   = self.__session.query(models.SpotJournal).filter_by(chat_id=self.__chat_id, active_record=1).first()
        if not journal_to_update:
            journal_to_update = models.SpotJournal(chat_id=self.__chat_id, spot_state=value, last_ts=value, 
                                               last_heared_ts=spotstate_to_update.last_heared_ts, from_ts=value, active_record=1)
        if value and not spotstate_to_update.last_ts == value:
            journal_to_update.last_ts   = value
            spotstate_to_update.last_ts = value
            self.__session.commit()

    @last_heared_ts.setter
    def last_heared_ts(self, value: datetime):
        spotstate_to_update = self.__session.query(models.SpotState).filter_by(chat_id=self.__chat_id).first()
        journal_to_update   = self.__session.query(models.SpotJournal).filter_by(chat_id=self.__chat_id, active_record=1).first()
        if not journal_to_update:
            journal_to_update = models.SpotJournal(chat_id=self.__chat_id, spot_state=spotstate_to_update.last_state, last_ts=value, 
                                               last_heared_ts=spotstate_to_update.last_heared_ts, from_ts=value, active_record=1)
        if value and not spotstate_to_update.last_heared_ts == value:
            journal_to_update.last_heared_ts   = value
            spotstate_to_update.last_heared_ts = value
            self.__session.commit()

    @is_active.setter
    def is_active(self, value: bool):
        spot_to_update = self.__get_spot_for_update()
        if not spot_to_update.is_active == (1 if value else 0):
            spot_to_update.is_active = (1 if value else 0)
            spot_to_update.ts_upd = datetime.now(TIMEZONE)
            self.__session.commit()

    def new_state(self, value: str):
        if not value: return
        spotstate_to_update = self.__session.query(models.SpotState).filter_by(chat_id=self.__chat_id).first()
        journal_to_update   = self.__session.query(models.SpotJournal).filter_by(chat_id=self.__chat_id, active_record=1).first()
        spotstate_to_update.last_ts = datetime.now(TIMEZONE)
        if not journal_to_update:
            journal_to_update = models.SpotJournal(chat_id=self.__chat_id, spot_state=value, 
                                                   last_ts=spotstate_to_update.last_ts, 
                                                   last_heared_ts=spotstate_to_update.last_heared_ts, 
                                                   from_ts=spotstate_to_update.last_ts, active_record=1)
        if spotstate_to_update.last_state and not spotstate_to_update.last_state == value:
           if not journal_to_update.spot_state == value:
                journal_to_update.to_ts         = datetime.now(TIMEZONE)
                journal_to_update.active_record = 0
                new_journal = models.SpotJournal(chat_id=self.__chat_id, spot_state=value, 
                                                 last_ts=spotstate_to_update.last_ts, 
                                                 last_heared_ts=spotstate_to_update.last_heared_ts, 
                                                 from_ts=spotstate_to_update.last_ts, active_record=1)
                self.__session.add(new_journal)
        elif not spotstate_to_update.last_state:
            if not journal_to_update.spot_state == value:
                journal_to_update.spot_state = value
                journal_to_update.last_ts    = datetime.now(TIMEZONE)
                journal_to_update.from_ts    = datetime.now(TIMEZONE)
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