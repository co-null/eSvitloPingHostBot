import config as cfg
import requests as urlr
from datetime import datetime, timedelta
import time
import pytz

use_tz = pytz.timezone(cfg.TZ)
bo_groups = {'1':'group_1','2':'group_2','3':'group_3','4':'group_4'}
bo_cities = {'Київ':'kiev', 'Дніпро':'dnipro'}
blackout_schedule = {}

def get_blackout_schedule():
    global blackout_schedule
    response = urlr.get(cfg.YASNO_URL)
    blackout_schedule = response.json()
    blackout_schedule = blackout_schedule['components'][2]['schedule']
    response.close()

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
        if not sch_type and hour < sch_today[window_id]['start']:
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
            if hour >= sch_today[window_id]['start'] and hour < sch_today[window_id]['end']:
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
        elif sch_type and sch_type == 'DEFINITE_OUTAGE':
            # we can't close it if it's the last window
            if window_id == (len(sch_today) - 1):
                current['end'] = None
            else:
                # next window is the outage end, let's save
                next = dict(sch_today[window_id])
                break #finished
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