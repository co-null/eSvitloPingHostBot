from config import TZ
import pytz
from db.models import User
from db.database import SessionMain
from datetime import datetime

TIMEZONE = pytz.timezone(TZ)

class Userdb:
    def __get_from_db(self):
            user_from_db = self.__session.query(User).filter_by(user_id=self.__user_id).first()
            self.__user_id   = user_from_db.user_id
            self.__new       = (user_from_db.new == 1)
            self.__num_spots = user_from_db.num_spots
            self.__is_active = (user_from_db.is_active == 1)
            self.__ts_ins    = user_from_db.ts_ins

    def __init__(self, in_user_id: int):
        self.__session         = SessionMain()
        self.__user_id:int     = in_user_id
        self.__new:bool        = True
        self.__num_spots:int   = 0
        self.__is_active:bool  = True
        self.__ts_ins:datetime = datetime.now(TIMEZONE)
        user_from_db = self.__session.query(User).filter_by(user_id=in_user_id).first()
        if not user_from_db:
            new_user = User(user_id=in_user_id, new=1, num_spots=0, is_active=1, ts_ins=datetime.now(TIMEZONE))
            self.__session.add(new_user)
            self.__session.commit()
        self.__get_from_db()

    def __del__(self):
        SessionMain.remove()

    def get(self):
        self.__get_from_db()
        return self

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
        return self.__session.query(User).filter_by(user_id=self.__user_id).first()
    
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