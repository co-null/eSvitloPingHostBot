from common.logger import init_logger
from telegram import Update, Bot
from telegram.ext import CallbackContext
from telegram import Update, Bot, InlineKeyboardButton, InlineKeyboardMarkup, constants
from bot_secrets import ADMIN_ID
import common.utils as utils, config as cfg
from verbiages import get_state_msg
from structure.spot import Spot
from structure.user import Userdb
from common.safe_schedule import SafeScheduler, scheduler
from user_settings import user_jobs, listeners
from datetime import datetime
import pytz, json

# Create a logger
logger = init_logger('eSvitlo-actions', './logs/esvitlo.log')

def _ping_ip(spot: Spot, immediately: bool = False, force_state:str = None) -> utils.PingResult:
    if force_state:
        status = force_state
        if spot.last_state and status==spot.last_state: changed = False
        else: changed = True
        msg = get_state_msg(spot, status, True)
        if changed: spot.new_state(status)
        if status == cfg.ALIVE: spot.last_heared_ts = datetime.now(pytz.timezone(cfg.TZ))
        return utils.PingResult(changed, msg)
    elif spot.ip_address:
        port_pos =  spot.ip_address.find(':')
        if port_pos == -1:
            status = utils.get_ip_status(spot.ip_address)
            if spot.last_state and status==spot.last_state: changed = False
            else: changed = True
            if changed or immediately:
                msg = get_state_msg(spot, status, immediately)
            else: msg = ""
            if changed: spot.new_state(status)
            if status == cfg.ALIVE: spot.last_heared_ts = datetime.now(pytz.timezone(cfg.TZ))  
            return utils.PingResult(changed, msg)
        else:
            host = spot.ip_address[:port_pos]
            port = spot.ip_address[port_pos+1:]
            status = utils.check_port(host, port)
            if spot.last_state and status==spot.last_state: changed = False
            else: changed = True
            if changed or immediately:
                logger.info(f'Pinging: User {spot.user_id} - status: {status}, changed:{changed}')
                msg = get_state_msg(spot, status, immediately)
            else: msg = ""
            if changed: spot.new_state(status)
            if status == cfg.ALIVE: spot.last_heared_ts = datetime.now(pytz.timezone(cfg.TZ))  
            return utils.PingResult(changed, msg)
    elif not spot.ip_address and spot.endpoint:
        status = utils.check_custom_api1(spot.endpoint, spot.headers, spot.api_details)
        if spot.last_state and status==spot.last_state: changed = False
        else: changed = True
        if changed or immediately:
            logger.info(f'API call: User {spot.user_id} - status: {status}, changed:{changed}')
            msg = get_state_msg(spot, status, immediately)
        else: msg = ""
        if changed: spot.new_state(status)
        if status == cfg.ALIVE: spot.last_heared_ts = datetime.now(pytz.timezone(cfg.TZ))  
        return utils.PingResult(changed, msg)
    else: utils.PingResult(False, "")


def _ping(user_id:int, chat_id:str, bot:Bot, force_state:str = None):
    user = Userdb(int(user_id)).get()
    if not user: return
    spot = Spot(user.user_id, chat_id).get()
    if not spot.ip_address and not spot.endpoint:
        spot.ping_job = None
        if spot.chat_id in user_jobs.keys():
            scheduler.cancel_job(user_jobs[spot.chat_id])
            del user_jobs[spot.chat_id]
    try:
        result = _ping_ip(spot, False, force_state)
        msg    = utils.get_text_safe_to_markdown(result.message)
        utils._sender(spot, msg, bot, f'_ping({user_id},{chat_id},bot,{force_state})')
    except Exception as e:
        logger.error(f"Exception in _ping({user_id},{chat_id},bot,{force_state}): {str(e)}")
        bot.send_message(chat_id=ADMIN_ID, text=f"Exception in _ping({user_id},{chat_id},bot,{force_state}): {str(e)}")

def _listen(user_id:int, chat_id:str, bot:Bot):
    try:
        user = Userdb(int(user_id)).get()
        if not user: return
        spot = Spot(user.user_id, chat_id).get()
        if not spot.listener: 
            # was turned off somehow
            return
        # Do not spam if never worked
        if not spot.last_state or not spot.last_ts or not spot.last_heared_ts: 
            return
        delta   = datetime.now(pytz.timezone(cfg.TZ)).replace(tzinfo=None) - spot.last_heared_ts
        seconds = 86400*delta.days + delta.seconds
        # If >180 sec (3 mins) and was turned on - consider blackout
        if seconds >= 180 and spot.last_state == cfg.ALIVE:
            status = cfg.OFF
        elif seconds < 180 and spot.last_state == cfg.ALIVE:
            # still enabled
            status = cfg.ALIVE
        elif seconds < 180 and spot.last_state == cfg.OFF:
            # already turned off
            status = cfg.OFF
        else:    
            # still turned off
            status = spot.last_state
        changed = not (status==spot.last_state)
        if changed: 
            msg = get_state_msg(spot, status, False)
            msg = utils.get_text_safe_to_markdown(msg)
            spot.new_state(status)
            logger.info(f'Heared: Spot {spot.chat_id} - status: {status}, changed:{changed}')
            spot.refresh()
        if changed: 
            utils._sender(spot, msg, bot, f'_listen({user_id},{chat_id},bot)')
    except Exception as e:
        logger.error(f"Exception in _listen({user_id}, {chat_id}, bot): {str(e)}")
        bot.send_message(chat_id=ADMIN_ID, text=f"Exception in _listen({user_id},{chat_id}, bot): {str(e)}")
        return 
    
def ping_now(update: Update, context: CallbackContext, bot:Bot, args:str = '{}') -> None:
    params = json.loads(args)
    user_id = params['uid']
    spot_id = params['cid']
    spot    = Spot(user_id, spot_id).get()
    context.user_data['temporary_callback'] = None
    context.user_data['requestor'] = None
    buttons = [[InlineKeyboardButton('OK', callback_data=json.dumps({'cmd':'main_menu'}))]]
    reply_markup = InlineKeyboardMarkup(buttons)
    if not spot.ip_address and not spot.listener and not spot.endpoint:
        utils.reply_md(cfg.msg_notset, update, bot, reply_markup)
        return
    message = get_state_msg(spot, spot.last_state, True)
    message  = utils.get_text_safe_to_markdown(message)
    utils._sender(spot, message, bot, 'ping_now()', True)

def _heard(user_id: str, chat_id: str, bot:Bot) -> None:
    msg = None
    user = Userdb(int(user_id)).get()
    if not user: return
    spot = Spot(user.user_id, chat_id).get()
    if spot.listener:
        spot.last_heared_ts = datetime.now(pytz.timezone(cfg.TZ))
        if spot.last_state != cfg.ALIVE:
            msg  = get_state_msg(spot, cfg.ALIVE, False)
            msg  = utils.get_text_safe_to_markdown(msg)
            spot.new_state(cfg.ALIVE)
        spot.refresh()
        utils._sender(spot, msg, bot, f'_heard({user_id},{chat_id})') 