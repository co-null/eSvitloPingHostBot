from common.logger import init_logger
import config as cfg
import user_settings as us
from structure.user import *
from structure.spot import *
#TODO Fix blackout schedule
#from blackout_schedule import BO_GROUPS, BO_GROUPS_TEXT, BO_CITIES, get_windows_analysis
import common.utils as utils
from datetime import datetime, timedelta
import pytz

# Create a logger
logger = init_logger('eSvitlo-verbiages', './logs/esvitlo.log')

TIMEZONE = pytz.timezone(cfg.TZ)

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

def _get_settings(spot: Spot) -> str:
    msg = ""
    msg += f"Назва: {spot.name}\n" 
    if spot.ip_address: msg += f"IP адреса: {spot.ip_address}\n"
    else: msg += "IP адреса не вказана \n"
    if spot.endpoint: msg += f"API: {utils.get_key_safe(cfg.api_list, spot.endpoint, 'не налаштовано')}\n"
    else: msg += "API не налаштовано \n"
    if spot.ping_job: msg += cfg.msg_ippingon 
    else: msg += cfg.msg_ippingoff
    if spot.listener: msg += cfg.msg_listeneron
    else: msg += cfg.msg_listeneroff 
    if spot.channel_id: msg += "Канал: " + str(spot.channel_id) + "\n" 
    if spot.to_bot: msg += cfg.msg_boton
    else: msg += cfg.msg_botoff
    if spot.to_channel: msg += cfg.msg_channelon
    else: msg += cfg.msg_channeloff
    #TODO Fix blackout schedule
    # if spot.has_schedule: 
    #     msg += f'Налаштовано графік для {spot.city}: Група {spot.group}'+ "\n"
    #     if spot.to_remind:
    #         msg += cfg.msg_reminder_on
    #     else: 
    #         msg += cfg.msg_reminder_off
    #if spot.to_telegram: msg += cfg.msg_telegram_news_on
    #else: msg += cfg.msg_telegram_news_off
    return msg

def get_settings_spot(spot: Spot, order: str) -> str:
    msg  = '*Точка ' + order + '*:\n'
    return msg + _get_settings(spot)

def get_settings(user: Userdb) -> str:
    msg  = cfg.msg_settings + '\n'
    msg += f"ID користувача: {user.user_id}\n"
    order = 0
    session = SessionMain()
    spots = session.query(models.Spot).filter_by(user_id=user.user_id, is_active=1).order_by(models.Spot.chat_id).all()
    for spot_m in spots:
        order += 1
        spot = Spot(spot_m.user_id, spot_m.chat_id)
        if order > 1: msg += '\n'
        msg += get_settings_spot(spot, str(order))
    session.close()
    return msg

def get_full_info(spot: Spot) -> str:
    info = f"ІД користувача: {spot.user_id}:\n"
    info += f"ІД точки: {spot.chat_id}:\n"
    info += _get_settings(spot)
    info += "\nСтатуси:\n"
    info += f"Стан: {spot.last_state}\n"
    info += f"Остання зміна стану: {spot.last_ts}\n"
    info += f"Останній виклик слухача: {spot.last_heared_ts}\n"
    if spot.endpoint or spot.headers:
        info += "*Extra*:\n"
        info += f"Ендпоінт {str(spot.endpoint)}:\n"
        info += f"Хідер {str(spot.headers)}:\n"
    return info

def get_key_list(dictionary:dict) -> str:
    msg = ''
    for label in dictionary.keys():
        msg += "- " + label + '\n'
    return msg

def get_state_msg(spot: Spot, status: str, immediately: bool = False) -> str:
    now_ts_short = datetime.now(TIMEZONE).strftime('%H:%M')
    msg     = ""
    add     = ""
    windows = None
    if spot.is_multipost:
        msg += f"*{spot.name}*\n"
    # if spot.has_schedule: 
    #     try:
    #         windows = get_windows_analysis(BO_CITIES[spot.city], BO_GROUPS[spot.group])
    #         add = "\n" + get_outage_message(status, windows)
    #     except Exception as e:
    #         logger.error(f'Exception in get_state_msg: {e}, status={status}, windows={windows}')
    # if last_state is not set
    if not spot.last_state:
        if spot.label and spot.label != '':
            msg += f"{spot.label} тепер моніториться на наявність електрохарчування\n"
        else:
            msg += "Моніториться на наявність електрохарчування\n"
    # turned on
    if spot.last_state and status == cfg.ALIVE and spot.last_state == cfg.OFF:
        delta = datetime.now(TIMEZONE).replace(tzinfo=None) - spot.last_ts
        msg += f"💡*{now_ts_short}* Юху! Світло повернулося!\n" + "⏱ Було відсутнє *" + get_string_period(delta) + "*"
        msg += add
    # turned off
    elif spot.last_state and status == cfg.OFF and spot.last_state == cfg.ALIVE:
        delta = datetime.now(TIMEZONE).replace(tzinfo=None) - spot.last_ts
        msg += f"🔦*{now_ts_short}* Йой… Халепа, знову без світла 😒\n" + "⏱ Було наявне *" + get_string_period(delta) + "*"
        msg += add
    # same
    elif cfg.isPostOK == 'T' or immediately:
        delta = datetime.now(TIMEZONE).replace(tzinfo=None) - spot.last_ts if spot.last_ts else timedelta(seconds=1)
        if status == cfg.ALIVE:
            msg += cfg.msg_alive
            msg += "\n" + "⏱ Світло є вже *" + get_string_period(delta) + "*"
            msg += add
        else:
            msg += cfg.msg_blackout
            msg += "\n" + "⏱ Світла немає вже *" + get_string_period(delta) + "*"
            msg += add
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
            message += f"⚠️ Сіра зона до *{window['end']:02}:00*\n"
    return message

def get_battery_state_msg(spot: Spot, battery:Invertor, status: utils.InvertorStatus, immediately: bool = False) -> str:
    def battery_level_verbiage() -> str:
        return f"{'🔋' if status.battery >= 40.0 else '🪫'} Рівень заряду батарей: *{status.battery:.0f}%*\n"
    
    def battery_level_changed(treshold_level:float, new_level:float) -> bool:
        if not treshold_level: return False # Let's wait until treshold will be set
        if new_level >= 95.0 and treshold_level >= 95.0: return False # Do not spam for charged
        if new_level >= 95.0 and treshold_level < 95.0: return True # Charged
        return (not int(new_level/10) == int(treshold_level/10))
    
    now_ts_short = datetime.now(TIMEZONE).strftime('%H:%M')
    delta = datetime.now(TIMEZONE).replace(tzinfo=None) - spot.last_ts if spot.last_ts else timedelta(seconds=1)
    msg     = ""
    if spot.is_multipost:
        msg += f"*{spot.name}*\n"
    if not spot.last_state:
        if spot.label and spot.label != '':
            msg += f"{spot.label} тепер моніториться статус батареї\n"
        else:
            msg += "Моніториться статус батареї\n"
        return
    # turned on
    if spot.last_state and status.status == cfg.ALIVE and spot.last_state != cfg.ALIVE:
        msg += f"⚡️*{now_ts_short}* Батареї заряджаються!\n"
        msg += battery_level_verbiage()
        msg +=  "⏱ Час роботи від батарей *" + get_string_period(delta) + "*"

    # turned off
    elif spot.last_state and status.status == cfg.OFF and spot.last_state != cfg.OFF:
        msg += f"🔦*{now_ts_short}* Знову робота від батарей 😒\n"
        msg += battery_level_verbiage()
        msg +=  "⏱ Час роботи від мережі *" + get_string_period(delta) + "*"
    
    # if offline
    #elif status.status == cfg.OFFLINE and not battery.is_offline:
    #    msg += f"❗️*{now_ts_short}* Нажаль, зараз інвертор офлайн, перевірте зв'язок 😒\n"

    # error
    elif spot.last_state and status.status == cfg.ERR and spot.last_state != cfg.ERR:
        msg += f"❗️*{now_ts_short}* Некоректний статус у відповіді, перевірте налаштування 😒\n"
    
    # instant
    elif cfg.isPostOK == 'T' or immediately:
        if status.status == cfg.ALIVE:
            msg += cfg.msg_alive
            msg += "\n" + "⏱ Час роботи від мережі *" + get_string_period(delta) + "*\n"
            msg += battery_level_verbiage()
        elif status.status == cfg.OFF:
            msg += cfg.msg_blackout
            msg += "\n" + "⏱ Час роботи від батарей *" + get_string_period(delta) + "*\n"
            msg += battery_level_verbiage()
        else:
            msg += battery_level_verbiage()

    # follow the battery state
    elif spot.last_state and spot.last_state == status.status:
        # Battery level changed
        if battery_level_changed(battery.last_battery_treshold, status.battery):
            if status.battery >= 95.0 and status.battery > battery.battery_lvl: 
                msg += "🔋 Батареї заряджено!\n"
            elif status.battery >= 95.0: msg = ""
            else: 
                if status.status == cfg.ALIVE:
                    msg += "⏱ Час роботи від мережі *" + get_string_period(delta) + "*\n"
                elif status.status == cfg.OFF:
                    msg += "⏱ Час роботи від батарей *" + get_string_period(delta) + "*\n"
                msg += battery_level_verbiage()
        else: msg = "" #make empty if any matched
    else: msg = "" #make empty if any matched
    return msg