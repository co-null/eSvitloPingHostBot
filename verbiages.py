import config as cfg
import user_settings as us
import utils
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

def _get_settings(user: us.User) -> str:
    msg = ""
    if user.ip_address: msg += "IP адреса: " + user.ip_address + f" ({user.label}) \n" 
    else: msg += "IP адреса не вказана \n"
    if user.ping_job: msg += cfg.msg_ippingon 
    else: msg += cfg.msg_ippingoff
    if user.listener: msg += cfg.msg_listeneron
    else: msg += cfg.msg_listeneroff 
    if user.channel_id: msg += "Канал: " + str(user.channel_id) + "\n" 
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

def get_settings(user_id: str) -> str:
    user = us.User(user_id, us.user_settings[user_id]['chat_id'])
    msg  = cfg.msg_settings + '\n'
    return msg + _get_settings(user)

def get_full_info(user: us.User) -> str:
    info = f"ІД: {user.chat_id}:\n"
    info += _get_settings(user)
    info += "\nСтатуси:\n"
    info += f"Стан: {user.last_state}\n"
    info += f"Остання зміна стану (UTC): {user.last_ts}\n"
    info += f"Останній виклик слухача (UTC): {user.last_heared_ts}\n"
    #info += "*Extra*:\n"
    #info += f"Ендпоінт {str(user.endpoint)}:\n"
    #info += f"Хідер {str(user.headers)}:\n"
    return info

def get_key_list(dictionary:dict) -> str:
    msg = ''
    for label in dictionary.keys():
        msg += "- " + label + '\n'
    return msg

def get_outage_message(state: str, windows: dict) -> str:
    try:
        current = windows['current']
        next    = windows['next']
        next1   = utils.get_key_safe(windows, 'over_next1', None)
        next2   = utils.get_key_safe(windows, 'over_next2', None)
    except Exception as e:
        return ''
    # Got the next outage
    add  = ""
    gray = ""
    if next['type'] != 'DEFINITE_OUTAGE':
        if next1 and next1['type'] == 'DEFINITE_OUTAGE':
            add = f"\n⏰ Наступне відключення з *{next1['start']:02}:00* до *{next1['end']:02}:00*"
        elif next2 and next2['type'] == 'DEFINITE_OUTAGE':
            add = f"\n⏰ Наступне відключення з *{next2['start']:02}:00* до *{next2['end']:02}:00*"
    if utils.get_key_safe(next, 'end_po', None):
        gray = f"\n⚠️ Відключення в сірій зоні до *{next['end_po']:02}:00* год."
    elif next['type'] == 'POSSIBLE_OUTAGE':
        gray = f"\n⚠️ Відключення в сірій зоні до *{next['end']:02}:00* год."

    if state == cfg.ALIVE:
        if current['type'] == 'OUT_OF_SCHEDULE':
            # matched
            message = f"⏰ Відключення за графіком з *{next['start']:02}:00* до *{next['end']:02}:00*" + gray
        elif current['type'] == 'POSSIBLE_OUTAGE':
            # grey
            if utils.get_key_safe(current, 'end_po', None):
                prefix = f"До *{current['end_po']:02}:00* діє сіра зона."
            else: prefix = "Діє сіра зона."
            message = f"⏰ {prefix} Відключення за графіком з *{next['start']:02}:00* до *{next['end']:02}:00*"
        else:
            # outage
            message = f"⏰ Очікуване відключення з *{current['start']:02}:00* до *{current['end']:02}:00*" + gray + add
    else:
        if current['type'] == 'DEFINITE_OUTAGE':
            # matched
            if utils.get_key_safe(next, 'end_po', None):
                gray = f"⚠️ Відключення в сірій зоні до *{next['end_po']:02}:00* год."
            elif next['type'] == 'POSSIBLE_OUTAGE':
                gray = f"⚠️ Відключення в сірій зоні до *{next['end']:02}:00* год."
            message = f"⏰ Відключення за графіком до *{current['end']:02}:00* год.\n" + gray + add
        elif current['type'] == 'POSSIBLE_OUTAGE':
            if utils.get_key_safe(current, 'end_po', None):
                gray = f" до *{current['end_po']:02}:00* год."
            else: gray = ""
            message = f"⚠️ Відключення в сірій зоні{gray}\n⏰ Очікуване відключення з *{next['start']:02}:00* до *{next['end']:02}:00*"
        else:
            # out of schedule
            message = f"😒 Відключено поза графіком\n⏰ Очікуване відключення з *{next['start']:02}:00* до *{next['end']:02}:00*"
    return message

def get_notification_message(blackout: datetime, severity = 'DEFINITE_OUTAGE'):
    blackout_ts_short = blackout.strftime('%H:%M')
    if severity == 'DEFINITE_OUTAGE':
        return f"⏰ Увага, очікується відключення за графіком з *{blackout_ts_short}*"
    
def get_notification_message_long(window: dict):
    gray = ""
    if window['po_to'] != -1:
        gray = f"\n⚠️ Відключення в сірій зоні до *{window['po_to']:02}:00* год."
    start_ts_short = window['start'].strftime('%H:%M')
    end_ts_short   = window['end'].strftime('%H:%M')
    return f"⏰ Увага, очікується відключення за графіком з *{start_ts_short}* до *{end_ts_short}*" + gray

def get_notificatiom_tomorrow_schedule(schedule_tom):
    message = '🗓 Графік відключень на завтра:\n\n'
    for window in schedule_tom:
        if window['type'] == 'DEFINITE_OUTAGE':
            message += f"🔦 Відключення з *{window['start']:02}:00* до *{window['end']:02}:00*\n"
        elif window['type'] == 'POSSIBLE_OUTAGE':
            message += f"⚠️ Сіра зона до *{window['end_po']:02}:00*\n"
    return message