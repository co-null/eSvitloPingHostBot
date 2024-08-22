# db/models.py
from sqlalchemy import Column, Integer, String, TIMESTAMP, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.schema import PrimaryKeyConstraint

Base = declarative_base()

class User(Base):
    __tablename__ = 'user'
    user_id   = Column(Integer, primary_key=True)
    new       = Column(Integer)
    num_spots = Column(Integer, default=1)
    is_active = Column(Integer, default=1)
    ts_ins    = Column(TIMESTAMP)
    spots = relationship('Spot')

class Spot(Base):
    __tablename__ = 'spot'
    chat_id          = Column(String, primary_key=True)
    user_id          = Column(Integer, ForeignKey('user.user_id'))
    ip_address       = Column(String)
    listener         = Column(Integer, default=0)
    label            = Column(String, default='')
    channel_id       = Column(String)
    to_bot           = Column(Integer, default=1)
    to_channel       = Column(Integer, default=0)
    ping_job         = Column(String)
    awaiting_ip      = Column(Integer, default=0)
    awaiting_label   = Column(Integer, default=0)
    awaiting_channel = Column(Integer, default=0)
    awaiting_city    = Column(Integer, default=0)
    awaiting_group   = Column(Integer, default=0)
    has_schedule     = Column(Integer, default=0)
    city             = Column(String)
    sch_group        = Column(String)
    endpoint         = Column(String)
    headers          = Column(String)
    api_details      = Column(String)
    interval         = Column(Integer, default=0)
    to_remind        = Column(Integer, default=0)
    ts_ins           = Column(TIMESTAMP)
    ts_upd           = Column(TIMESTAMP)

    spotstate     = relationship('SpotState', back_populates='spot')
    journals      = relationship('SpotJournal')
    notifications = relationship('SpotNotification')

class SpotState(Base):
    __tablename__ = 'spot_state'
    chat_id        = Column(String, ForeignKey('spot.chat_id'), primary_key=True)
    last_state     = Column(String)
    last_ts        = Column(TIMESTAMP)
    last_heared_ts = Column(TIMESTAMP)

    spot = relationship('Spot', back_populates="spotstate")

class SpotJournal(Base):
    __tablename__ = 'spot_journal'
    chat_id        = Column(String, ForeignKey('spot.chat_id'), primary_key=True)
    spot_state     = Column(String)
    last_ts        = Column(TIMESTAMP)
    last_heared_ts = Column(TIMESTAMP)
    from_ts        = Column(TIMESTAMP, primary_key=True)
    to_ts          = Column(TIMESTAMP)
    active_record  = Column(Integer)
    __table_args__ = (PrimaryKeyConstraint('chat_id', 'from_ts'),)

class SpotNotification(Base):
    __tablename__ = 'spot_notification'
    chat_id              = Column(String, ForeignKey('spot.chat_id'), primary_key=True)
    notification_type    = Column(String, primary_key=True)
    next_notification_ts = Column(TIMESTAMP)
    next_event_ts        = Column(TIMESTAMP)
    __table_args__ = (PrimaryKeyConstraint('chat_id', 'notification_type'),)