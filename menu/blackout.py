from common.logger import init_logger
import config as cfg
import user_settings as us
from structure.spot import Spot
import requests as urlr
from datetime import datetime, timedelta, tzinfo
import os, logging, traceback, time, pytz, json
from logging.handlers import TimedRotatingFileHandler

logger = init_logger('eSvitlo-blackout', './logs/esvitlo.log')

TIMEZONE       = pytz.timezone(cfg.TZ)
BO_GROUPS      = {'1':'group_1','2':'group_2','3':'group_3','4':'group_4','5':'group_5','6':'group_6'}
BO_GROUPS_TEXT = {'group_1':'Група I','group_2':'Група II','group_3':'Група III','group_4':'Група IV','group_5':'Група V','group_6':'Група VI'}
BO_CITIES      = {'Київ':'kiev', 'Дніпро':'dnipro', 'Софіївська Борщагівка':'sofiivska_borshchagivka', 'Ірпінь':'irpin'}

blackout_schedule = {}
shedulers = {}

def get_blackout_schedule():
    global blackout_schedule
    try:
        response = urlr.get(cfg.YASNO_URL)
        tmp_schedule = None
        tmp_schedule = response.json()
        tmp_schedule = tmp_schedule['components'][5]['schedule']
        response.close()    
    except Exception as e:
        logger.error(f"Exception happened in get_blackout_schedule(): {traceback.format_exc()}")
    if tmp_schedule:
        blackout_schedule = tmp_schedule
    adjust_dtek_schedule('dtek_sofiivska_borshchagivka.json')
    adjust_dtek_schedule('dtek_irpin.json')
    save_blackout_shedule()


# Save blackout shedule to file
def save_blackout_shedule():
    with open(cfg.SCHEDULE_FILE, 'w') as file:
        json.dump(blackout_schedule, file)

def load_custom_schedule_dtek(file: str):
    if os.path.exists(file):
        with open(file, encoding='utf-8', mode='r') as file:
            return json.load(file)

def adjust_dtek_schedule(file: str):
    custom_schedule = load_custom_schedule_dtek(file)
    city_id         = custom_schedule['city_id']
    city            = {}
    for group_id in BO_GROUPS.keys():
        #print(f"Group {group_id}")
        _days = []
        for day in range(7):
            #print(f"Group {group_id}, Day {str(day+1)}")
            _day = []
            prev_state = None
            opened = False
            for hour in range(24):
                state = custom_schedule['data'][group_id][str(day+1)][str(hour+1)]
                if state == 'no': t_type = 'DEFINITE_OUTAGE'
                elif state == 'maybe': t_type = 'POSSIBLE_OUTAGE'
                else: t_type = 'OUT_OF_SCHEDULE'
                if t_type != 'OUT_OF_SCHEDULE' and not prev_state:
                    # create first window
                    _window = {}
                    _window['start'] = hour
                    _window['end']   = hour+1
                    _window['type']  = t_type
                    prev_state = state
                    opened = True
                elif t_type != 'OUT_OF_SCHEDULE' and prev_state != state:
                    # create next window
                    if opened: 
                        _day.append(dict(_window))
                        #print(f"Window {_window}")
                    _window = {}
                    _window['start'] = hour
                    _window['end']   = hour+1
                    _window['type']  = t_type
                    opened = True
                    prev_state = state
                elif t_type != 'OUT_OF_SCHEDULE' and prev_state == state:
                    # update window
                    _window['end'] = hour+1
                    opened = True
                elif t_type == 'OUT_OF_SCHEDULE' and prev_state != state:
                    # close previous window
                    prev_state = state
                    if opened: 
                        _day.append(dict(_window))
                        #print(f"Window {_window}")
                    opened = False
                # close if this is the last hour
                if hour == 23 and opened: 
                    #print(f"Window {_window}")
                    _day.append(dict(_window))
            _days.append(_day[:])
        city[BO_GROUPS[group_id]] = _days[:]
    blackout_schedule[city_id] = city

def _get_window(hour: int, schedule: dict, today = True) -> dict:
    window = {}
    window['ends_tomorrow'] = not today

    for window_id in range(len(schedule)):
        # before the window
        if hour < int(schedule[window_id]['start']):
            # not in window
            window['type']  = 'OUT_OF_SCHEDULE'
            window['start'] = hour
            window['end']   = schedule[window_id]['start']
            return window
        # after the last window
        elif hour >= int(schedule[window_id]['end']) and window_id == (len(schedule) - 1):
            # not in window
            window['type']          = 'OUT_OF_SCHEDULE'
            window['start']         = int(schedule[window_id]['end'])
            window['end']           = None
            window['ends_tomorrow'] = True
            return window
        # looking for window
        if hour >= int(schedule[window_id]['start']) and hour < int(schedule[window_id]['end']):
            window   = dict(schedule[window_id])
            window['ends_tomorrow'] = not today
            # add real end
            if window['end'] == 24:
                window['end']           = None
                window['ends_tomorrow'] = True
            return window


def get_window(hour: int, schedule: dict, schedule_next: dict = None, today = True) -> dict:
    window = _get_window(hour, schedule, today)
    if not window['end'] and schedule_next:
        next = _get_window(0, schedule_next)
        if window['type'] == next['type']:
            window['end'] = next['end']
        else:
            window['end'] = 0
    return window


def get_window_by_ts(timestamp: datetime, city:str, group_id: str) -> dict:
    yesterday = (timestamp - timedelta(days=1)).replace(hour=23, minute=1)
    tomorrow  = timestamp + timedelta(days=1)
    sch_yest  = blackout_schedule[city][group_id][yesterday.weekday()]
    sch_today = blackout_schedule[city][group_id][timestamp.weekday()]
    sch_tom   = blackout_schedule[city][group_id][tomorrow.weekday()]
    out = {}
  
    # find current window
    current = get_window(timestamp.hour, sch_today, sch_tom, True)
    if current['start'] == 0:
        # get yesterday window
        previous = get_window(yesterday.hour, sch_yest)
        if current['type'] == previous['type']:
            # enlarge
            current['start'] = previous['start']

    # find second event
    if not current['ends_tomorrow']:
        second = get_window(int(current['end']), sch_today, sch_tom, True)
    else:
        second = get_window(int(current['end']), sch_tom, None, False)

    # find third event
    if not second['ends_tomorrow']:
        third = get_window(int(current['end']), sch_today, sch_tom, True)
    else:
        third = get_window(int(current['end']), sch_tom, None, False)

    out['current'] = current
    if current['type'] == 'OUT_OF_SCHEDULE' and second['type'] == 'DEFINITE_OUTAGE':
        out['next_outage'] = second
        out['gray_zone']   = third
    elif current['type'] == 'DEFINITE_OUTAGE' and second['type'] == 'POSSIBLE_OUTAGE':
        out['gray_zone']  = second
        out['next_alive'] = third
        # find fourth event
        if not third['ends_tomorrow']:
            fourth = get_window(int(current['end']), sch_today, sch_tom, True)
        else:
            fourth = get_window(int(current['end']), sch_tom, None, False)
        out['next_outage'] = fourth
    elif current['type'] == 'POSSIBLE_OUTAGE' and second['type'] == 'OUT_OF_SCHEDULE':
        out['next_alive']  = second
        out['next_outage'] = third
    else:
        if second['type'] == 'DEFINITE_OUTAGE': out['next_outage'] = second
        elif second['type'] == 'POSSIBLE_OUTAGE': out['gray_zone'] = second
        else: out['next_alive'] = second # should not happen
    return out

'''
def get_window_by_ts_old(timestamp: datetime, city:str, group_id: str) -> dict:
    delta     = timedelta(days=1)
    tomorrow  = timestamp + delta
    weekday   = timestamp.weekday()
    next_wday = tomorrow.weekday()
    hour      = timestamp.hour
    sch_today = blackout_schedule[city][group_id][weekday]
    sch_tom   = blackout_schedule[city][group_id][next_wday]
    current   = {}
    next      = {}
    sch_type  = None
    #find current window
    for window_id in range(len(sch_today)):
        # before the window
        if not sch_type and hour < int(sch_today[window_id]['start']):
            # not in window
            sch_type         = 'OUT_OF_SCHEDULE'
            current['type']  = sch_type
            current['start'] = hour
            if sch_today[window_id]['type'] == 'DEFINITE_OUTAGE':
                # definite outage next
                current['end'] = sch_today[window_id]['start']
                #break
            else:
                current['end'] = None # will look for outage start
        # after the last window
        elif not sch_type and hour >= int(sch_today[window_id]['end']) and window_id == (len(sch_today) - 1):
            # not in window
            sch_type         = 'OUT_OF_SCHEDULE'
            current['type']  = sch_type
            current['start'] = int(sch_today[window_id]['end'])
            current['end']   = None # will look for outage start
        # looking for window
        if not sch_type:
            # in window
            if hour >= int(sch_today[window_id]['start']) and hour < int(sch_today[window_id]['end']):
                current  = dict(sch_today[window_id])
                sch_type = sch_today[window_id]['type']
                # add real end for 'grey' zone
                if sch_type == 'POSSIBLE_OUTAGE': 
                    current['end_po'] = sch_today[window_id]['end']
                    if current['end_po'] == 24:
                        current['end_po'] = None
                # we can't close it if it's the last window
                if window_id == (len(sch_today) - 1):
                    current['end']    = None
        # window was previously found, looking for next
        # we were out of schedule or in grey window, looking for outage window
        elif sch_type and sch_type != 'DEFINITE_OUTAGE':
            # may we close current window?
            if sch_today[window_id]['type'] == 'DEFINITE_OUTAGE':
                # found outage window to close the previous one
                current['end'] = sch_today[window_id]['start']
                # and fill in the next window
                next = dict(sch_today[window_id])
                break #finished
        # window was previously found, looking for next
        # we were at outage, looking for outage end
        elif sch_type and sch_type == 'DEFINITE_OUTAGE' and sch_today[window_id]['type'] != 'DEFINITE_OUTAGE':
            # next window is the outage end, let's save
                next = dict(sch_today[window_id])
                break #finished
        elif sch_type and sch_type == 'DEFINITE_OUTAGE' and sch_today[window_id]['type'] == 'DEFINITE_OUTAGE':
            # we can't close it if it's the last window
            if window_id == (len(sch_today) - 1):
                current['end'] = None
    #lets'close grey zone if still open
    if 'end_po' in current.keys() and not current['end_po'] and sch_tom[0]['type'] == 'POSSIBLE_OUTAGE':
        current['end_po'] = sch_tom[0]['end']
    elif 'end_po' in current.keys() and not current['end_po'] and sch_tom[0]['type'] != 'POSSIBLE_OUTAGE':
        current['end_po'] = sch_tom[0]['start']
    # find next window if not found it today
    if 'type' not in next.keys():
        for window_id in range(len(sch_tom)):
            # we are looking for next outage 
            if sch_type != 'DEFINITE_OUTAGE' and sch_tom[window_id]['type'] == 'DEFINITE_OUTAGE':
                # found outage window to close the previous one
                current['end']    = sch_tom[window_id]['start']
                #current['end_po'] = sch_today[window_id]['end']
                # and fill in the next window
                next = sch_tom[window_id]
                break #finished
            # we are at outage, looking for outage end
            # outage is still last from midnight
            elif sch_type == 'DEFINITE_OUTAGE' and sch_tom[window_id]['type'] == 'DEFINITE_OUTAGE' and not current['end']:
                # we'll close the current
                current['end'] = sch_tom[window_id]['end']
            # we are at outage and looks like it ended at midnight
            elif sch_type == 'DEFINITE_OUTAGE' and sch_tom[window_id]['type'] != 'DEFINITE_OUTAGE' and not current['end']:
                # we'll close the current
                current['end'] = sch_tom[window_id]['start']
                # and fill in the next window
                next = dict(sch_tom[window_id])
                break #finished
            # we just looking for next window after ourage
            elif sch_type == 'DEFINITE_OUTAGE' and sch_tom[window_id]['type'] != 'DEFINITE_OUTAGE' and current['end']:
                next = dict(sch_tom[window_id])
                break #finished
            # otherwise - look at next window

    # just get the state for 00:01 next day if next is outage and up for midnight
    if next['type'] == 'DEFINITE_OUTAGE' and next['end'] == 24:
        if sch_tom[0]['type'] == 'DEFINITE_OUTAGE' and sch_tom[0]['start'] == 0:
            next['end'] = sch_tom[0]['end']
    return {'current': current, 'next': next}
'''

def get_windows_for_tomorrow(user: Spot):
    city      = BO_CITIES[user.city]
    group_id  = BO_GROUPS[user.group]
    now_ts    = datetime.now(TIMEZONE)
    before     = now_ts.replace(hour=23, minute=1)
    tomorrow  = (now_ts + timedelta(days=1)).replace(hour=0, minute=1)
    after_tom = now_ts + timedelta(days=2)
    sch_today = blackout_schedule[city][group_id][before.weekday()]
    sch_tom   = blackout_schedule[city][group_id][tomorrow.weekday()]
    sch_ttom  = blackout_schedule[city][group_id][after_tom.weekday()]
    sch     = []
    last    = None

    # find first window
    window = get_window(tomorrow.hour, sch_tom, sch_ttom)
    if window['start'] == 0:
        # get today last window
        previous = get_window(before.hour, sch_today, sch_tom)
        if window['type'] == previous['type']:
            # enlarge
            window['start'] = previous['start']

    if window['type'] == 'DEFINITE_OUTAGE':
        last = dict(window)
        sch.append(dict(window))

    for _ in range(24):
        before = before + timedelta(hours=1)
        window = get_window(before.hour, sch_tom, sch_ttom)

        if not last:
            last = dict(window)
            sch.append(dict(window))
        if window['type'] != last['type']:
            last = dict(window)
            sch.append(dict(window))

        if window['ends_tomorrow']: break
    return sch

def get_windows_analysis(city:str, group_id: str) -> dict:
    now_ts  = datetime.now(TIMEZONE)
    for city_key in BO_CITIES:
        if BO_CITIES[city_key] not in blackout_schedule.keys():
            get_blackout_schedule()
            time.sleep(5)
    windows = get_window_by_ts(now_ts, city, group_id)
    print(windows)
    if windows['next']['type'] != 'DEFINITE_OUTAGE':
        if windows['next']['start'] > windows['current']['start'] and windows['next']['end'] <= 23:
            over_next_ts = now_ts.replace(hour=windows['next']['end'], minute=30, second=0)
        elif windows['next']['end'] > 23:
            over_next_ts = now_ts.replace(hour=windows['next']['end'] - 1, minute=30, second=0) + timedelta(hours=1)
        else:
            over_next_ts = now_ts.replace(hour=windows['next']['end'], minute=30, second=0) + timedelta(hours=24)
        over_next    = get_window_by_ts(over_next_ts, city, group_id)
        windows['over_next1'] = over_next['current']
        windows['over_next2'] = over_next['next']
    return windows

def get_next_outage(city:str, group_id: str) -> datetime:
    now_ts  = datetime.now(TIMEZONE)
    windows = get_window_by_ts(now_ts, city, group_id)
    return now_ts.replace(hour=windows['next_outage']['start'], minute=0, second=0)


def get_next_outage_window(user: Spot):
    now_ts  = datetime.now(TIMEZONE)
    windows = get_window_by_ts(now_ts, BO_CITIES[user.city], BO_GROUPS[user.group])
    next_ts = now_ts.replace(hour=windows['current']['end']) + timedelta(hours=1)
    after   = get_window_by_ts(next_ts, BO_CITIES[user.city], BO_GROUPS[user.group])
    gray    = -1
    if after['current']['type'] == 'POSSIBLE_OUTAGE':
        gray = after['current']['end_po']
    if windows['next']['type'] == 'DEFINITE_OUTAGE':
        start = now_ts.replace(hour=windows['next']['start'], minute=0, second=0)
        end   = now_ts.replace(hour=windows['next']['end'], minute=0, second=0)
        return {'start': start, 'end': end, 'po_to' : gray}
    else: 
        return None

def get_notification_ts(next_outage: datetime) -> datetime:
    delta = timedelta(minutes=16)
    if next_outage:
        return next_outage-delta
    else: return None

def set_notifications():
    #print("Start set notifications job")
    now_ts  = datetime.now(TIMEZONE)
    for user_id in us.user_settings.keys():
        chat_id = us.user_settings[user_id]['chat_id']
        user    = us.User(user_id, chat_id)
        try:
            # has schedule and notification not set
            if user.has_schedule and user.to_remind and user.last_ts and not user.next_notification_ts:
                delta = datetime.now(TIMEZONE) - user.last_ts.replace(tzinfo=TIMEZONE)
                if delta.days > 0: continue
                next_outage = get_next_outage(BO_CITIES[user.city], BO_GROUPS[user.group])
                if next_outage:
                    user.next_outage_ts       = next_outage
                    user.next_notification_ts = get_notification_ts(next_outage)
                    user.save_state()
            if user.has_schedule and user.to_remind and user.last_ts and not user.tom_notification_ts:
                    delta = datetime.now(TIMEZONE) - user.last_ts
                    if delta.days > 0: continue
                    user.tom_schedule_ts     = now_ts.replace(hour=21, minute=5, second=0)
                    user.tom_notification_ts = now_ts.replace(hour=20, minute=45, second=0)
                    user.save_state()
        except Exception as e:
            logger.error(f"Exception happened in set_notifications(): userid={user_id}, user.city={user.city}, user.group = {user.group}, exception: {traceback.format_exc()}")

#TODO Blackout shedule
# def yasno_schedule(update: Update, context: CallbackContext) -> None:
#     user_id = str(update.message.from_user.id)
#     chat_id = update.message.chat_id
#     logger.info(f'User {user_id} invoked "yasno_schedule"')
#     if user_id not in us.user_settings.keys():
#         reply_md(cfg.msg_error, update)
#         logger.warning(f'User {user_id} unknown')
#         return
#     user = us.User(user_id, chat_id)
#     msg = f'{cfg.msg_setcity}\n{verbiages.get_key_list(bos.bo_cities)}'
#     msg += cfg.msg_setcitybottom
#     user.toggle_awaiting_city()
#     user.save()
#     update.message.reply_text(msg)

# def get_tom_schedule(update: Update, context: CallbackContext) -> None:
#     user_id = str(update.message.from_user.id)
#     chat_id = update.message.chat_id
#     logger.info(f'User {user_id} invoked "get_tom_schedule"')
#     if user_id not in us.user_settings.keys():
#         reply_md(cfg.msg_error, update)
#         logger.warning(f'User {user_id} unknown')
#         return
#     user = us.User(user_id, chat_id)
#     msg = verbiages.get_notificatiom_tomorrow_schedule(bos.get_windows_for_tomorrow(user))
#     reply_md(msg, update)

# def reminder(update: Update, context: CallbackContext) -> None:
#     user_id = str(update.message.from_user.id)
#     chat_id = update.message.chat_id
#     logger.info(f'User {user_id} invoked "reminder"')
#     if user_id not in us.user_settings.keys():
#         reply_md(cfg.msg_error, update)
#         logger.warning(f'User {user_id} unknown')
#         return
#     user = us.User(user_id, chat_id)
#     if not user.to_remind and not user.has_schedule:
#         reply_md(cfg.msg_reminder_no_schedule, update)
#     elif not user.to_remind and user.has_schedule:
#         user.to_remind = True
#         reply_md(cfg.msg_reminder_turnon, update)
#     elif user.to_remind and user.has_schedule:
#         user.to_remind = False
#         reply_md(cfg.msg_reminder_off, update)
#     #_notification_schedules()
#     user.save()

#TODO Blackout schedule
# def _gather_schedules():
#     # Stop any existing job before starting a new one
#     if 'yasno' in bos.shedulers.keys():
#         scheduler.cancel_job(bos.shedulers['yasno'])
#     # Schedule gathering job every 60 min
#     bos.shedulers['yasno'] = scheduler.every(cfg.SCHEDULE_GATHER_SCHEDULE).minutes.do(bos.get_blackout_schedule)

# def _notification_schedules():
#     # Stop any existing job before starting a new one
#     if 'set_notification' in bos.shedulers.keys():
#         scheduler.cancel_job(bos.shedulers['set_notification'])
#     # Schedule set_notification job every 30 min
#     bos.shedulers['set_notification'] = scheduler.every(cfg.SCHEDULE_SET_NOTIFICATION).minutes.do(bos.set_notifications)
#     if 'send_notification' in bos.shedulers.keys():
#         scheduler.cancel_job(bos.shedulers['send_notification'])
#     # Schedule send_notification job every min
#     bos.shedulers['send_notification'] = scheduler.every(cfg.SCHEDULE_SEND_NOTIFICATION).minutes.do(_send_notifications)

#TODO Blackout schedule
# def _send_notifications():
#     #print("Start send notifications job")
#     #logger.info('Start send notifications job')
#     try:
#         # here all timestamp are in Kyiv TZ
#         use_tz  = pytz.timezone(cfg.TZ)
#         now_ts0 = datetime.now(use_tz)
#         # make tz-naive
#         now_ts = datetime.strptime((now_ts0.strftime('%Y-%m-%d %H:%M:%S')), '%Y-%m-%d %H:%M:%S')
#         for user_id in us.user_settings.keys():
#             chat_id = us.user_settings[user_id]['chat_id']
#             user    = us.User(user_id, chat_id)
#             if user.has_schedule and user.to_remind and user.next_notification_ts and user.next_outage_ts:
#                 if user.next_notification_ts < now_ts and user.next_outage_ts > now_ts and user.last_state == cfg.ALIVE:
#                     # will send
#                     msg = None #utils.get_text_safe_to_markdown(verbiages.get_notification_message_long(bos.get_next_outage_window(user)))
#                     if msg and user.to_bot: 
#                         try:
#                             bot.send_message(chat_id=user.chat_id, text=msg, parse_mode=PARSE_MODE)
#                         except Exception as e:
#                             print(f'Forbidden: bot {user_id} tried to send to {user.chat_id}, exception: {traceback.format_exc()}')
#                             logger.error(f'Forbidden: bot {user_id} tried to send to {user.chat_id}, exception: {traceback.format_exc()}')
#                     if msg and user.to_channel and user.channel_id:
#                         try:
#                             bot.send_message(chat_id=user.channel_id, text=msg, parse_mode=PARSE_MODE)
#                         except Exception as e:
#                             print(f'Forbidden: bot is not a member of the channel chat, {user_id} tried to send to {user.channel_id}, exception: {traceback.format_exc()}')
#                             logger.error(f'Forbidden: bot is not a member of the channel chat, {user_id} tried to send to {user.channel_id}, exception: {traceback.format_exc()}')
#                     # update next_notification_ts so we'll not send again
#                     user.next_notification_ts = user.next_outage_ts
#                     user.save_state()
#                 elif user.next_notification_ts < now_ts and user.next_outage_ts > now_ts and user.last_state != cfg.ALIVE:
#                     # already off
#                     user.next_notification_ts = None
#                     user.next_outage_ts       = None
#                     user.save_state()
#                 elif user.next_outage_ts < now_ts:
#                     # outdated
#                     user.next_notification_ts = None
#                     user.next_outage_ts       = None
#                     user.save_state()
#             if user.has_schedule and user.to_remind and user.tom_notification_ts and user.tom_schedule_ts:
#                 if user.tom_notification_ts < now_ts and user.tom_schedule_ts > now_ts:
#                     # will send
#                     msg = None #verbiages.get_notificatiom_tomorrow_schedule(bos.get_windows_for_tomorrow(user))
#                     if msg and user.to_bot: 
#                         try:
#                             bot.send_message(chat_id=user.chat_id, text=msg, parse_mode=PARSE_MODE)
#                         except Exception as e:
#                             print(f'Forbidden: bot is not a member of the channel chat, {user_id} tried to send to {user.chat_id}')
#                             logger.error(f'Forbidden: bot is not a member of the channel chat, {user_id} tried to send to {user.chat_id}')
#                     if msg and user.to_channel and user.channel_id:
#                         try:
#                             bot.send_message(chat_id=user.channel_id, text=msg, parse_mode=PARSE_MODE)
#                         except Exception as e:
#                             print(f'Forbidden: bot is not a member of the channel chat, {user_id} tried to send to {user.channel_id}')
#                             logger.error(f'Forbidden: bot is not a member of the channel chat, {user_id} tried to send to {user.channel_id}')
#                     # update next_notification_ts so we'll not send again
#                     user.tom_notification_ts = user.tom_schedule_ts
#                     user.save_state()
#                 elif user.tom_schedule_ts < now_ts:
#                     # outdated
#                     user.tom_notification_ts = None
#                     user.tom_schedule_ts     = None
#                     user.save_state()
#     except Exception as e:
#         print(f"Exception in _send_notifications(): {traceback.format_exc()}")
#         logger.error(f"Exception in _send_notifications(): {traceback.format_exc()}")