import config as cfg
import user_settings as us
from datetime import datetime
import pytz

use_tz = pytz.timezone(cfg.TZ)

def get_string_period(delta_sec: int) -> str:
    hours    = int(delta_sec/3600)
    minutes  = int((delta_sec - 3600*hours)/60)

    if hours > 0 and hours < 48: 
        hour_str = f"{hours} год."
    elif hours >= 48:
        hour_str = "більше 48 год."
    else: hour_str = ''
    if minutes > 0 and hours < 48:
        min_str = f"{minutes} хв."
    else: min_str  = ''
    if hours == 0 and minutes < 1:
        return "менше хвилини"
    elif hours == 0 and minutes > 0:
        return min_str
    else: return hour_str + " " + min_str

def get_settings(user_id: str) -> str:
    user = us.user_settings[user_id]
    msg  = cfg.msg_settings + '\n'
    if user['ip_address']: msg += "IP адреса: " + user['ip_address'] + f" ({user['label']}) \n" 
    else: msg += "IP адреса не вказана \n"
    if user['ping_job']: msg += cfg.msg_ippingon 
    else: msg += cfg.msg_ippingoff
    if user['listener']: msg += cfg.msg_listeneron
    else: msg += cfg.msg_listeneroff 
    if user['channel_id']: msg += "Канал: " + user['channel_id'] + "\n" 
    if user['to_bot']: msg += cfg.msg_boton
    else: msg += cfg.msg_botoff
    if user['to_channel']: msg += cfg.msg_channelon
    else: msg += cfg.msg_channeloff
    return msg