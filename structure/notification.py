from config import TZ
import pytz
from db.models import SpotNotification
from db.database import SessionMain
from datetime import datetime

TIMEZONE = pytz.timezone(TZ)

class Notification:
    def __get_from_db(self):
        notification_from_db = self.__session.query(SpotNotification).filter_by(chat_id=self.__chat_id).first()
        self.__chat_id              = notification_from_db.chat_id
        self.__notification_type    = notification_from_db.notification_type
        self.__next_notification_ts = notification_from_db.next_notification_ts
        self.__next_event_ts        = notification_from_db.next_event_ts

    def __init__(self, in_chat_id: str, in_notification_type: str):
        self.__session              = SessionMain()
        self.__chat_id              = in_chat_id
        self.__notification_type    = in_notification_type
        self.__next_notification_ts = None
        self.__next_event_ts        = None
        notification_from_db = self.__session.query(SpotNotification).filter_by(chat_id=in_chat_id, notification_type=in_notification_type).first()
        if not notification_from_db:
            new_notification = SpotNotification(chat_id=in_chat_id, notification_type=in_notification_type)
            self.__session.add(new_notification)
            self.__session.commit()
        self.__get_from_db()

    def __del__(self):
        SessionMain.remove()

    def __get_notification_for_update(self):
        return self.__session.query(SpotNotification).filter_by(chat_id=self.__chat_id, notification_type=self.__notification_type).first()
    
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