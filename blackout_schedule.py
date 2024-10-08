import config as cfg
import user_settings as us
import requests as urlr
import utils
from datetime import datetime, timedelta
import os, logging, traceback, time, pytz, json
from logging.handlers import TimedRotatingFileHandler

# Create a logger
logger = logging.getLogger('eSvitlo-blackout-schedule')
logger.setLevel(logging.DEBUG)

# Create a file handler
#fh = logging.FileHandler('errors.log', encoding='utf-8')
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

use_tz         = pytz.timezone(cfg.TZ)
bo_groups      = {'1':'group_1','2':'group_2','3':'group_3','4':'group_4','5':'group_5','6':'group_6'}
bo_groups_text = {'group_1':'Група I','group_2':'Група II','group_3':'Група III','group_4':'Група IV','group_5':'Група V','group_6':'Група VI'}
bo_cities      = {'Київ':'kiev', 'Дніпро':'dnipro', 'Софіївська Борщагівка':'sofiivska_borshchagivka', 'Ірпінь':'irpin'}

blackout_schedule = {}
shedulers = {}

def get_blackout_schedule():
    global blackout_schedule
    try:
        response = urlr.get(cfg.YASNO_URL)
        tmp_schedule = None
        tmp_schedule = response.json()
        tmp_schedule = tmp_schedule['components'][3]['schedule']
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
    for group_id in bo_groups.keys():
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
        city[bo_groups[group_id]] = _days[:]
    blackout_schedule[city_id] = city

def get_window_by_ts(timestamp: datetime, city:str, group_id: str) -> dict:
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

def get_windows_for_tomorrow(user: us.User):
    city     = bo_cities[user.city]
    group_id = bo_groups[user.group]
    sch     = []
    now_ts  = datetime.now(use_tz)
    delta   = timedelta(hours=1)
    before  = now_ts.replace(hour=23, minute=59, second=59)
    windows = get_window_by_ts(before, city, group_id)
    last    = None
    if windows['current']['type'] == 'DEFINITE_OUTAGE':
        last = windows['current']
        sch.append(dict(windows['current']))
    for hour in range(24):
        before = before + delta
        windows = get_window_by_ts(before, city, group_id)
        if not last:
            last = windows['current']
            sch.append(dict(windows['current']))
        if windows['current']['type'] != last['type']:
            last = windows['current']
            sch.append(dict(windows['current']))
    return sch

def get_windows_analysis(city:str, group_id: str) -> dict:
    now_ts  = datetime.now(use_tz)
    for city_key in bo_cities:
        if bo_cities[city_key] not in blackout_schedule.keys():
            get_blackout_schedule()
            time.sleep(5)
    windows = get_window_by_ts(now_ts, city, group_id)
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
    now_ts  = datetime.now(use_tz)
    windows = get_window_by_ts(now_ts, city, group_id)
    if windows['next']['type'] == 'DEFINITE_OUTAGE':
        return now_ts.replace(hour=windows['next']['start'], minute=0, second=0)
    else: return None

def get_next_outage_window(user: us.User):
    now_ts  = datetime.now(use_tz)
    windows = get_window_by_ts(now_ts, bo_cities[user.city], bo_groups[user.group])
    next_ts = now_ts.replace(hour=windows['current']['end']) + timedelta(hours=1)
    after   = get_window_by_ts(next_ts, bo_cities[user.city], bo_groups[user.group])
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
    now_ts  = datetime.now(use_tz)
    for user_id in us.user_settings.keys():
        chat_id = us.user_settings[user_id]['chat_id']
        user    = us.User(user_id, chat_id)
        try:
            # has schedule and notification not set
            if user.has_schedule and user.to_remind and user.last_ts and not user.next_notification_ts:
                delta = datetime.now() - user.last_ts
                if delta.days > 0: continue
                next_outage = get_next_outage(bo_cities[user.city], bo_groups[user.group])
                if next_outage:
                    user.next_outage_ts       = next_outage
                    user.next_notification_ts = get_notification_ts(next_outage)
                    user.save_state()
            if user.has_schedule and user.to_remind and user.last_ts and not user.tom_notification_ts:
                    delta = datetime.now() - user.last_ts
                    if delta.days > 0: continue
                    user.tom_schedule_ts     = now_ts.replace(hour=21, minute=5, second=0)
                    user.tom_notification_ts = now_ts.replace(hour=20, minute=45, second=0)
                    user.save_state()
        except Exception as e:
            logger.error(f"Exception happened in set_notifications(): userid={user_id}, user.city={user.city}, user.group = {user.group}, exception: {traceback.format_exc()}")