import config as cfg
import requests as urlr
import os
import json
from datetime import datetime, timedelta
import time
import pytz

use_tz = pytz.timezone(cfg.TZ)
bo_groups = {'1':'group_1','2':'group_2','3':'group_3','4':'group_4'}
bo_groups_text = {'group_1':'Група I','group_2':'Група II','group_3':'Група III','group_4':'Група IV'}
bo_cities = {'Київ':'kiev', 'Дніпро':'dnipro', 'Софіївська Борщагівка':'sofiivska_borshchagivka'}
blackout_schedule = {}

def get_blackout_schedule():
    global blackout_schedule
    response = urlr.get(cfg.YASNO_URL)
    blackout_schedule = response.json()
    blackout_schedule = blackout_schedule['components'][2]['schedule']
    response.close()
    adjust_dtek_schedule('dtek_sofiivska_borshchagivka.json')
    save_blackout_shedule()

# Save blackout shedule to file
def save_blackout_shedule():
    with open("blackout_shedule.json", 'w') as file:
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
        _days = []
        for day in range(7):
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
                    # create next wimdow
                    if opened: _day.append(dict(_window))
                    _window = {}
                    _window['start'] = hour
                    _window['end']   = hour+1
                    _window['type']  = t_type
                    opened = True
                    prev_state = state
                elif t_type != 'OUT_OF_SCHEDULE' and prev_state == state:
                    # update window
                    _window['end'] = hour+1
                elif t_type == 'OUT_OF_SCHEDULE' and prev_state != state:
                    # close previous window
                    prev_state = state
                    if opened: _day.append(dict(_window))
                    opened = False

                # close if this is the last hour
                if hour == 23 and opened: _day.append(dict(_window))
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
        # looking for window
        if not sch_type:
            # in window
            if hour >= int(sch_today[window_id]['start']) and hour < int(sch_today[window_id]['end']):
                current  = dict(sch_today[window_id])
                sch_type = sch_today[window_id]['type']
                # we can't close it if it's the last window
                if window_id == (len(sch_today) - 1):
                    current['end'] = None
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
            #else:
                # next window is the outage end, let's save
             #   next = dict(sch_today[window_id])
            #s    break #finished
        # else: no need in "else"

    # find next window if not found it today
    if 'type' not in next.keys():
        for window_id in range(len(sch_tom)):
            # we are looking for next outage 
            if sch_type != 'DEFINITE_OUTAGE' and sch_tom[window_id]['type'] == 'DEFINITE_OUTAGE':
                # found outage window to close the previous one
                current['end'] = sch_tom[window_id]['start']
                # and fill in the next window
                next = sch_tom[window_id]
                break #finished
            # we are at outage, looking for outage end
            # outage is till last from midnight
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


def get_windows_analysis(city:str, group_id: str) -> dict:
    now_ts  = datetime.now(use_tz)
    for city_key in bo_cities:
        if bo_cities[city_key] not in blackout_schedule.keys():
            get_blackout_schedule()
            time.sleep(5)
    return get_window_by_ts(now_ts, city, group_id)