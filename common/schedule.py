from common.logger import init_logger
from common.safe_schedule import SafeScheduler, scheduler
from user_settings import user_jobs, listeners
from structure.spot import Spot
#from actions import _ping, _listen

logger = init_logger('eSvitlo-schedule', './logs/esvitlo.log')

def add_ping_job(spot: Spot, function, bot):
    user_jobs[spot.chat_id] = scheduler.every(spot.interval).minutes.do(function, user_id=spot.user_id, chat_id=spot.chat_id, bot=bot)

def add_listen_job(spot: Spot, function, bot):
    listeners[spot.chat_id] = scheduler.every(spot.interval).minutes.do(function, user_id=spot.user_id, chat_id=spot.chat_id, bot=bot)

def cancel_ping_job(spot: Spot):
    try:
        scheduler.cancel_job(user_jobs[spot.chat_id])
    except Exception as e:
        #logger.error(f"cancel_ping_job({spot.chat_id}):{str(e)}")
        None

def cancel_listener_job(spot: Spot):
    try:
        scheduler.cancel_job(listeners[spot.chat_id])
    except Exception as e:
        #logger.error(f"cancel_listener_job({spot.chat_id}):{str(e)}")
        None

def delete_ping_job(spot: Spot):
    cancel_ping_job(spot)
    if spot.chat_id in user_jobs.keys():
        del user_jobs[spot.chat_id]

def delete_listener_job(spot: Spot):
    cancel_listener_job(spot)
    if spot.chat_id in listeners.keys():
        del listeners[spot.chat_id]

def recreate_job(spot: Spot, function_ping, function_listen, bot):
    if spot.listener: 
        cancel_listener_job(spot)
        add_listen_job(spot, function_listen, bot)
    if spot.ip_address and spot.ping_job: 
        cancel_ping_job(spot)
        add_ping_job(spot, function_ping, bot)
        return
    if spot.endpoint and spot.ping_job: 
        cancel_ping_job(spot)
        add_ping_job(spot, function_ping, bot)