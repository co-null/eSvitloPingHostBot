import config as cfg
import user_settings as us
from datetime import datetime, timedelta
import pytz

use_tz = pytz.timezone(cfg.TZ)

def get_string_period(delta: timedelta) -> str:
    days    = delta.days
    hours   = int(delta.seconds/3600)
    minutes = int((delta.seconds - 3600*hours)/60)
    days_str = ''
    hour_str = ''
    min_str  = ''
    if days > 0: 
        days_str = f"{days} д."
    if hours > 0: #and hours < 48: 
        hour_str = f"{hours} год."
    #elif hours >= 48:
    #    hour_str = "більше 48 год."
    if minutes > 0: #and hours < 48:
        min_str = f"{minutes} хв."
    if days == 0 and hours == 0 and minutes < 1:
        return "менше хвилини"
    elif days == 0 and hours == 0 and minutes > 0:
        return min_str
    if days > 0 and (hours > 0 or minutes > 0):
        days_str = days_str + ' '
    if hours > 0 and minutes > 0:
        hour_str = hour_str + ' '
    return days_str + hour_str + min_str

def get_settings(user_id: str) -> str:
    user = us.User(user_id, us.user_settings[user_id]['chat_id'])
    msg  = cfg.msg_settings + '\n'
    if user.ip_address: msg += "IP адреса: " + user.ip_address + f" ({user.label}) \n" 
    else: msg += "IP адреса не вказана \n"
    if user.ping_job: msg += cfg.msg_ippingon 
    else: msg += cfg.msg_ippingoff
    if user.listener: msg += cfg.msg_listeneron
    else: msg += cfg.msg_listeneroff 
    if user.channel_id: msg += "Канал: " + user.channel_id + "\n" 
    if user.to_bot: msg += cfg.msg_boton
    else: msg += cfg.msg_botoff
    if user.to_channel: msg += cfg.msg_channelon
    else: msg += cfg.msg_channeloff
    if user.has_schedule: 
        msg += f'Налаштовано графік для {user.city}: Група {user.group}'+ "\n"
        if user.to_remind:
            msg += cfg.msg_reminder_on
        else: 
            msg += cfg.msg_reminder_off
    return msg

def get_key_list(dictionary:dict) -> str:
    msg = ''
    for label in dictionary.keys():
        msg += "- " + label + '\n'
    return msg

def get_outage_message(state: str, windows: dict) -> str:
    try:
        current = windows['current']
        next    = windows['next']
    except Exception as e:
        return ''
    if state == cfg.ALIVE:
        if current['type'] == 'OUT_OF_SCHEDULE':
            # matched
            message = f"⏰ Відключення за графіком з *{next['start']:02}:00* до *{next['end']:02}:00*"
        elif current['type'] == 'POSSIBLE_OUTAGE':
            # grey
            message = f"⏰ Діє сіра зона. Відключення за графіком з *{next['start']:02}:00* до *{next['end']:02}:00*"
        else:
            # out of schedule
            message = f"⏰ Очікуване відключення з *{current['start']:02}:00* до *{current['end']:02}:00*"
    else:
        if current['type'] == 'DEFINITE_OUTAGE':
            # matched
            message = f"⏰ Відключення за графіком до *{current['end']:02}:00* год."
        elif current['type'] == 'POSSIBLE_OUTAGE':
            message = f"⏰ Відключення в сірій зоні\n⏰ Очікуване відключення з *{next['start']:02}:00* до *{next['end']:02}:00*"
        else:
            # out of schedule
            message = f"😒 Відключено поза графіком\n⏰ Очікуване відключення з *{next['start']:02}:00* до *{next['end']:02}:00*"
    return message

def get_notification_message(blackout: datetime, severity = 'DEFINITE_OUTAGE'):
    blackout_ts_short = blackout.strftime('%H:%M')
    if severity == 'DEFINITE_OUTAGE':
        return f"⏰ Увага, очікується відключення за графіком з *{blackout_ts_short}*"
    
def get_notification_message_long(window: dict):
    start_ts_short = window['start'].strftime('%H:%M')
    end_ts_short   = window['end'].strftime('%H:%M')
    return f"⏰ Увага, очікується відключення за графіком з *{start_ts_short}* до *{end_ts_short}*"