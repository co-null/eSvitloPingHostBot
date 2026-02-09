import bot_secrets, config as cfg, user_settings as us, utils, verbiages, actions
from structure.user import *
from structure.spot import *
from db.database import SessionMain
#import blackout_schedule as bos
from telegram.ext import Updater, CommandHandler, CallbackContext, MessageHandler, Filters, CallbackQueryHandler
from telegram import Update, Bot, ReplyKeyboardMarkup, ReplyKeyboardRemove, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup, constants
from telegram.utils.request import Request as TRequest
import logging, traceback, schedule, time, threading, pytz, json
from logging.handlers import TimedRotatingFileHandler
from safe_schedule import SafeScheduler, scheduler
from datetime import datetime
from flask import Flask, request, jsonify

# Create a logger
logger = logging.getLogger('eSvitlo-main')
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

PARSE_MODE = constants.PARSEMODE_MARKDOWN_V2
# Initialize Flask app
app = Flask(__name__)

# Telegram bot initialization
bot_request = TRequest(con_pool_size=8)
bot         = Bot(token=bot_secrets.BOT_TOKEN, request=bot_request)
updater     = Updater(bot=bot, use_context=True)
dispatcher  = updater.dispatcher

# Define the main menu keyboard
main_menu_keyboard = [[KeyboardButton('Отримати статус негайно')], 
                      [KeyboardButton('Старт'),
                       KeyboardButton('Стоп')],
                      [KeyboardButton('Налаштування'),
                       KeyboardButton('?')]]

# Define the settings menu
settings_menu_keyboard = [[KeyboardButton('Вказати IP'), 
                          KeyboardButton('Вказати назву'), 
                          KeyboardButton('Вказати канал')], 
                          [KeyboardButton('-> в бот (так/ні)'), 
                          KeyboardButton('-> в канал (так/ні)')], 
                          [KeyboardButton('Пінг (так/ні)'),
                           KeyboardButton('Слухати (так/ні)'),
                           KeyboardButton('Графік'), 
                           KeyboardButton('Нагадати')],
                          [KeyboardButton('Головне меню')]]

main_menu_markup     = ReplyKeyboardMarkup(main_menu_keyboard, resize_keyboard=True)
settings_menu_markup = ReplyKeyboardMarkup(settings_menu_keyboard, resize_keyboard=True)

#Global vars
sys_commands = {}

def reply_md(message:str, update: Update, reply_markup = None) -> None:
    chat_id = update.effective_chat.id
    message = utils.get_text_safe_to_markdown(message)
    bot.send_message(chat_id, text=message, reply_markup=reply_markup, parse_mode=PARSE_MODE)

def edit_md(message:str, update: Update, reply_markup = None) -> None:
    query = update.callback_query
    query.answer()
    message = utils.get_text_safe_to_markdown(message)
    query.edit_message_text(text=message, reply_markup=reply_markup, parse_mode=PARSE_MODE)

def get_syscommand(chat_id:str, cmd_type:str) -> bool:
    return utils.get_key_safe(utils.get_key_safe(sys_commands, chat_id, {}), cmd_type, False)

def start(update: Update, context: CallbackContext) -> None:
    user_id = str(update.message.from_user.id)
    user    = Userdb(int(user_id))
    if user.new :
        spot = Spot(user.user_id, str(user.user_id))
        reply_md(cfg.msg_greeting, update)
        user.new = False
    else:
        # Recreate the jobs if saved previously
        session = SessionMain()
        spots = session.query(models.Spot).filter_by(user_id=user.user_id).order_by(models.Spot.chat_id).all()
        for spot in spots:
            if spot.ping_job:
                if spot.chat_id in us.user_jobs.keys():
                    scheduler.cancel_job(us.user_jobs[spot.chat_id])
                if spot.ip_address and not spot.endpoint:
                    us.user_jobs[spot.chat_id] = scheduler.every(cfg.SCHEDULE_PING).minutes.do(_ping, user_id=spot.user_id, chat_id=spot.chat_id)
                elif spot.endpoint:
                    us.user_jobs[spot.chat_id] = scheduler.every(2*int(cfg.SCHEDULE_PING)).minutes.do(_ping, user_id=spot.user_id, chat_id=spot.chat_id)
            if spot.listener:
                if spot.chat_id in us.listeners.keys():
                    scheduler.cancel_job(us.listeners[spot.chat_id])
                us.listeners[spot.chat_id] = scheduler.every(cfg.SCHEDULE_LISTEN).minutes.do(_listen, user_id=spot.user_id, chat_id=spot.chat_id)
            #TODO Blackout shedule
            # if user.has_schedule:
            #     _gather_schedules()
            #     _notification_schedules()
        reply_md(cfg.msg_comeback, update, reply_markup=ReplyKeyboardRemove())
            #TODO Blackout shedule
        #bos.get_blackout_schedule()
        #bos.set_notifications()
    main_menu(update, context) 

def settings(update: Update, context: CallbackContext, args:str = None) -> None:
    user_id = update.effective_chat.id
    user    = Userdb(int(user_id)).get()
    #logger.info(f'User {user_id} invoked "settings"')
    if not user:
        reply_md(cfg.msg_error, update)
        logger.warning(f'settings: User {user_id} unknown')
        return
    if utils.get_system() == 'windows':
        link_base = cfg.LOCAL_URL + str(user_id)
    else: link_base = cfg.LISTENER_URL + str(user_id)
    button_set = []
    session = SessionMain()
    i = 0
    spots = session.query(models.Spot).filter_by(user_id=user.user_id).order_by(models.Spot.chat_id).all()
    for spot_m in spots:
        spot = Spot(spot_m.user_id, spot_m.chat_id).get()
        i += 1
        callback_data = json.dumps({'cmd':'ed_spot', 'uid':spot.user_id, 'cid':spot.chat_id})
        button_set.append([InlineKeyboardButton(f'Редагувати {spot.name}', callback_data=callback_data)])
        if i == 1: 
            link = f"*Для налаштування слухача для точки {i} робіть виклики* на {link_base}"
        else:
            link += '\n'
            link += f"*Для налаштування слухача для точки {i} робіть виклики* на {link_base}&spot_id={spot.chat_id}"
    # Create inline buttons
    button_set.append([InlineKeyboardButton("Додати точку", 
                                            callback_data=json.dumps({'cmd':'add_spot', 'uid':spot.user_id}))])
    button_set.append([InlineKeyboardButton(cfg.msg_mainmnu, 
                                            callback_data=json.dumps({'cmd':'main_menu', 'uid':user.user_id}))])
    # Send message with buttons
    reply_markup = InlineKeyboardMarkup(button_set)
    edit_md(verbiages.get_settings(user) + "\n" + link, update, reply_markup=reply_markup)


def settings_spot(update: Update, context: CallbackContext, args: str) -> None:
    params = json.loads(args)
    user_id = params['uid']
    spot_id = params['cid']
    spot    = Spot(user_id, spot_id).get()
    if utils.get_system() == 'windows':
        link_base = cfg.LOCAL_URL + str(user_id)
    else: link_base = cfg.LISTENER_URL + str(user_id)
    if str(spot_id).find('_') == -1:
        link = f"*Для налаштування слухача для точки робіть виклики* на {link_base}"
    else:
        link = f"*Для налаштування слухача для точки робіть виклики* на {link_base}&spot_id={spot.chat_id}"
    # Create inline buttons
    button_set = []
    button_set.append([InlineKeyboardButton('Вказати IP', 
                                            callback_data=json.dumps({'cmd':'sIp', 'uid':spot.user_id, 'cid':spot.chat_id})),
                       InlineKeyboardButton('Вказати назву', 
                                            callback_data=json.dumps({'cmd':'sLabel', 'uid':spot.user_id, 'cid':spot.chat_id})),
                       InlineKeyboardButton('Вказати канал', 
                                            callback_data=json.dumps({'cmd':'sChannel', 'uid':spot.user_id, 'cid':spot.chat_id}))])
    button_set.append([InlineKeyboardButton('-> в бот (так/ні)', 
                                            callback_data=json.dumps({'cmd':'sToBot', 'uid':spot.user_id, 'cid':spot.chat_id})),
                       InlineKeyboardButton('-> в канал (так/ні)', 
                                            callback_data=json.dumps({'cmd':'sToChannel', 'uid':spot.user_id, 'cid':spot.chat_id}))])
    button_set.append([InlineKeyboardButton('Пінг (так/ні)', 
                                            callback_data=json.dumps({'cmd':'sPing', 'uid':spot.user_id, 'cid':spot.chat_id})),
                       InlineKeyboardButton('Слухати (так/ні)', 
                                            callback_data=json.dumps({'cmd':'sLsn', 'uid':spot.user_id, 'cid':spot.chat_id}))])
    button_set.append([InlineKeyboardButton('Налаштування', 
                                            callback_data=json.dumps({'cmd':'settings', 'uid':user_id}))])
    button_set.append([InlineKeyboardButton(cfg.msg_mainmnu, 
                                            callback_data=json.dumps({'cmd':'main_menu', 'uid':spot.user_id}))])
    # Send message with buttons
    reply_markup = InlineKeyboardMarkup(button_set)
    edit_md(verbiages._get_settings(spot) + "\n" + link, update, reply_markup=reply_markup)


def main_menu(update: Update, context: CallbackContext) -> None:
    user_id = update.effective_chat.id
    user    = Userdb(int(user_id)).get()
    # Create inline buttons
    button_set = []
    spots = session.query(models.Spot).filter_by(user_id=user.user_id).order_by(models.Spot.chat_id).all()
    for spot_m in spots:
        spot = Spot(spot_m.user_id, spot_m.chat_id).get()          
        callback_data = json.dumps({'cmd':'ping', 'uid':spot.user_id, 'cid':spot.chat_id})
        button_set.append([InlineKeyboardButton('Запит по ' + spot.name, 
                                                callback_data=callback_data)])
    button_set.append([InlineKeyboardButton('Налаштування', 
                                            callback_data=json.dumps({'cmd':'settings', 'uid':user_id})),
                       InlineKeyboardButton('Довідка', 
                                            callback_data=json.dumps({'cmd':'help', 'uid':user_id}))])
    # Send message with buttons
    reply_markup = InlineKeyboardMarkup(button_set)
    reply_md(cfg.msg_mainmnu, update, reply_markup=reply_markup)

def ask_set_ip(update: Update, context: CallbackContext, args: str) -> None:
    query = update.callback_query
    context.user_data['temporary_callback'] = args
    context.user_data['requestor'] = 'ask_set_ip'
    # Send message
    query.edit_message_text(text=cfg.msg_setip)

def set_ip(update: Update, context: CallbackContext, args: str) -> None:
    query = update.callback_query
    context.user_data['temporary_callback'] = args
    entered = update.message.text[:20]
    params = json.loads(args)
    user_id = params['uid']
    spot_id = params['cid']
    spot    = Spot(user_id, spot_id).get()
    context.user_data['temporary_callback'] = None
    context.user_data['requestor'] = None
    callback_data=json.dumps({'cmd':'ed_spot', 'uid':spot.user_id, 'cid':spot.chat_id})
    buttons = [[InlineKeyboardButton('OK', callback_data=callback_data)]]
    reply_markup = InlineKeyboardMarkup(buttons)
    if entered == '-' and spot.ip_address:
        spot.ip_address = None
        spot.ping_job   = None
        reply_md('ІР адресу видалено', update, reply_markup=reply_markup)
        if spot.chat_id in us.user_jobs.keys():
            scheduler.cancel_job(us.user_jobs[spot.chat_id])
        return
    elif entered == '-' and not spot.ip_address:
        reply_md('Скасовано', update)
        return
    else:
        spot.ip_address = entered
    spot.refresh()
    if not spot.label or spot.label == '':
        query.edit_message_text(text=f'Вказано IP адресу {spot.ip_address}.')
        ask_set_label(update = update, context = context, args = args)
    else:
        reply_md(f'Вказано IP адресу {spot.ip_address}', update, reply_markup=reply_markup)

def ask_set_label(update: Update, context: CallbackContext, args: str) -> None:
    query = update.callback_query
    context.user_data['temporary_callback'] = args
    context.user_data['requestor'] = 'ask_set_label'
    # Send message
    query.edit_message_text(text=cfg.msg_setlabel)

def set_label(update: Update, context: CallbackContext, args: str) -> None:
    query = update.callback_query
    context.user_data['temporary_callback'] = args
    entered = update.message.text[:255]
    params = json.loads(args)
    user_id = params['uid']
    spot_id = params['cid']
    spot    = Spot(user_id, spot_id).get()
    context.user_data['temporary_callback'] = None
    context.user_data['requestor'] = None
    callback_data=json.dumps({'cmd':'ed_spot', 'uid':spot.user_id, 'cid':spot.chat_id})
    buttons = [[InlineKeyboardButton('OK', callback_data=callback_data)]]
    reply_markup = InlineKeyboardMarkup(buttons)
    if entered == '-' and spot.label:
        spot.label = None
        reply_md('Назву видалено', update, reply_markup=reply_markup)
    elif entered == '-' and not spot.label:
        reply_md('Скасовано', update, reply_markup=reply_markup)
    else:
        spot.label = entered
        spot.refresh()
        reply_md(f'Назву оновлено на {spot.label}. Тепер можна активізувати моніторинг', update, reply_markup=reply_markup)

def ask_set_channel(update: Update, context: CallbackContext, args: str) -> None:
    query = update.callback_query
    context.user_data['temporary_callback'] = args
    context.user_data['requestor'] = 'ask_set_channel'
    # Send message
    query.edit_message_text(text=cfg.msg_setchannel)

def set_channel(update: Update, context: CallbackContext, args: str) -> None:
    query = update.callback_query
    context.user_data['temporary_callback'] = args
    entered = update.message.text[:255]
    params = json.loads(args)
    user_id = params['uid']
    spot_id = params['cid']
    spot    = Spot(user_id, spot_id).get()
    context.user_data['temporary_callback'] = None
    context.user_data['requestor'] = None
    callback_data=json.dumps({'cmd':'ed_spot', 'uid':spot.user_id, 'cid':spot.chat_id})
    buttons = [[InlineKeyboardButton('OK', callback_data=callback_data)]]
    reply_markup = InlineKeyboardMarkup(buttons)

    if entered == '-' and spot.channel_id:
        spot.channel_id = None
        reply_md('Канал видалено', update, reply_markup=reply_markup)
    elif entered == '-' and not spot.channel_id:
        reply_md('Скасовано', update)
    elif ' ' in entered:
        reply_md(cfg.msg_badinput, update)
    else:
        spot.channel_id = entered
        spot.refresh()
        reply_md(f'Налаштовано публікацію в канал {spot.channel_id}', update, reply_markup=reply_markup)

def add_spot(update: Update, context: CallbackContext, args: str) -> None:
    params  = json.loads(args)
    user_id = params['uid']
    user    = Userdb(int(user_id))
    spot    = Spot(user_id, str(user_id) + '_' + str(user.num_spots + 1))
    spot.label = 'Нова'
    spot.refresh()
    callback_data = json.dumps({'cmd':'ed_spot', 'uid':spot.user_id, 'cid':spot.chat_id})
    edit_md(cfg.msg_spotadded, update)
    ask_set_label(update, context, callback_data)

def post_to_bot(update: Update, context: CallbackContext, args: str) -> None:
    params = json.loads(args)
    user_id = params['uid']
    spot_id = params['cid']
    spot    = Spot(user_id, spot_id).get()
    context.user_data['temporary_callback'] = None
    context.user_data['requestor'] = None
    callback_data=json.dumps({'cmd':'ed_spot', 'uid':spot.user_id, 'cid':spot.chat_id})
    buttons = [[InlineKeyboardButton('OK', callback_data=callback_data)]]
    reply_markup = InlineKeyboardMarkup(buttons)
    if not spot.to_bot:
        #Turn on:
        spot.to_bot = True
        msg = cfg.msg_postbot
    else:
        #Turn off:
        spot.to_bot = False
        msg = cfg.msg_nopostbot
    spot.refresh()
    edit_md(msg + "\n" + verbiages._get_settings(spot), update, reply_markup=reply_markup)

def post_to_channel(update: Update, context: CallbackContext, args: str) -> None:
    params = json.loads(args)
    user_id = params['uid']
    spot_id = params['cid']
    spot    = Spot(user_id, spot_id).get()
    context.user_data['temporary_callback'] = None
    context.user_data['requestor'] = None
    callback_data=json.dumps({'cmd':'ed_spot', 'uid':spot.user_id, 'cid':spot.chat_id})
    buttons = [[InlineKeyboardButton('OK', callback_data=callback_data)]]
    reply_markup = InlineKeyboardMarkup(buttons)
    if not spot.to_channel:
        if spot.channel_id: 
            # turn on
            spot.to_channel = True
            msg = cfg.msg_postchannel
        else:
            spot.to_channel = False
            msg = cfg.msg_nochannel
    else:
        # turn off
        spot.to_channel = False
        msg = cfg.msg_nopostchannel
    spot.refresh()
    edit_md(msg + "\n" + verbiages._get_settings(spot), update, reply_markup=reply_markup)

def _ping(user_id, chat_id, force_state = None):
    user = Userdb(int(user_id)).get()
    if not user: return
    spot = Spot(user.user_id, chat_id).get()
    if not spot.ip_address and not spot.endpoint:
        spot.ping_job = None
        if spot.chat_id in us.user_jobs.keys():
            scheduler.cancel_job(us.user_jobs[spot.chat_id])
            del us.user_jobs[spot.chat_id]
    try:
        result = actions._ping_ip(spot, False, force_state)
        msg    = utils.get_text_safe_to_markdown(result.message)
        if msg and spot.to_bot: 
            try:
                header = utils.get_text_safe_to_markdown(f'*{spot.name}*\n' if not spot.is_multipost else '')
                bot.send_message(chat_id=spot.user_id, 
                                 text=header + msg, 
                                 parse_mode=PARSE_MODE)
            except Exception as e:
                logger.error(f'Forbidden: bot is not a member of the channel chat, {user_id} tried to send to {spot.user_id}')
        if msg and spot.to_channel and spot.channel_id:
            try:
                bot.send_message(chat_id = spot.treated_channel_id, 
                                 message_thread_id = spot.thread_id, 
                                 text=msg, 
                                 parse_mode=PARSE_MODE)
            except Exception as e:
                logger.error(f'Forbidden: bot is not a member of the channel chat, {user_id} tried to send to {spot.channel_id}')
    except Exception as e:
        logger.error(f"Exception in _ping({user_id}, {chat_id}): {traceback.format_exc()}")
        bot.send_message(chat_id=bot_secrets.ADMIN_ID, text=f"Exception in _ping({user_id}, {chat_id}): {e}")
        return 
    
def _start_ping(spot: Spot) -> None:
    # Stop any existing job before starting a new one
    if spot.chat_id in us.user_jobs.keys():
        scheduler.cancel_job(us.user_jobs[spot.chat_id])
    # Schedule the ping job every min
    if spot.ip_address and not spot.endpoint:
        us.user_jobs[spot.chat_id] = scheduler.every(cfg.SCHEDULE_PING).minutes.do(_ping, user_id=spot.user_id, chat_id=spot.chat_id)
    elif spot.endpoint:
        us.user_jobs[spot.chat_id] = scheduler.every(2*int(cfg.SCHEDULE_PING)).minutes.do(_ping, user_id=spot.user_id, chat_id=spot.chat_id)
    spot.ping_job = 'scheduled'
    spot.refresh()
    # Initial ping immediately
    _ping(spot.user_id, spot.chat_id)

def _stop_ping(spot: Spot) -> None:
    if spot.chat_id in us.user_jobs.keys():
        scheduler.cancel_job(us.user_jobs[spot.chat_id])
        del us.user_jobs[spot.chat_id]
    spot.ping_job = None

def ping(update: Update, context: CallbackContext, args: str = '{}') -> None:
    params = json.loads(args)
    user_id = params['uid']
    spot_id = params['cid']
    spot    = Spot(user_id, spot_id).get()
    context.user_data['temporary_callback'] = None
    context.user_data['requestor'] = None
    callback_data=json.dumps({'cmd':'ed_spot', 'uid':spot.user_id, 'cid':spot.chat_id})
    buttons = [[InlineKeyboardButton('OK', callback_data=callback_data)]]
    reply_markup = InlineKeyboardMarkup(buttons)
    if not spot.ping_job == 'scheduled':
        # If need to turn on
        if not spot.ip_address and not spot.endpoint:
            edit_md(cfg.msg_noip, update, reply_markup=reply_markup)
            return
        _start_ping(spot)
        msg = f'Тепер бот перевірятиме доступність {spot.label} і повідомлятиме про зміну статусу'
    else:
        # If need to turn off
        if spot.chat_id in us.user_jobs.keys():
            msg = cfg.msg_stopped
        else:
            msg = cfg.msg_notset
        _stop_ping(spot)
    spot.refresh()
    edit_md(msg + "\n" + verbiages._get_settings(spot), update, reply_markup=reply_markup)

def _listen(user_id, chat_id):
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
        delta   = datetime.now() - max(spot.last_heared_ts, spot.last_ts)
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
        if status==spot.last_state: changed = False
        else: changed = True
        if changed: 
            msg = actions.get_state_msg(spot, status, False)
            msg = utils.get_text_safe_to_markdown(msg)
            spot.last_ts    = max(spot.last_heared_ts, spot.last_ts)
            spot.last_state = status
            logger.info(f'Heared: Spot {spot.chat_id} - status: {status}, changed:{changed}')
        spot.refresh()
        if changed and msg and spot.to_bot: 
            try:
                header = utils.get_text_safe_to_markdown(f'*{spot.name}*\n' if not spot.is_multipost else '')
                bot.send_message(chat_id=spot.user_id, 
                                 text=header + msg, 
                                 parse_mode=PARSE_MODE)
            except Exception as e:
                print(f'Forbidden: bot is not a member of the channel chat, {spot.chat_id} tried to send to {spot.user_id}')
                logger.error(f'Forbidden: bot is not a member of the channel chat, {spot.chat_id} tried to send to {spot.user_id}')
        if changed and msg and spot.to_channel and spot.channel_id:
            try:
                bot.send_message(chat_id=spot.treated_channel_id, 
                                 message_thread_id = spot.thread_id, 
                                 text=msg, 
                                 parse_mode=PARSE_MODE)
            except Exception as e:
                print(f'Forbidden: bot is not a member of the channel chat, {spot.chat_id} tried to send to {spot.treated_channel_id}')
                logger.error(f'Forbidden: bot is not a member of the channel chat, {spot.chat_id} tried to send to {spot.treated_channel_id}')
    except Exception as e:
        logger.error(f"Exception in _listen({user_id}, {chat_id}): {str(e)}")
        bot.send_message(chat_id=bot_secrets.ADMIN_ID, text=f"Exception in _listen({user_id}, {chat_id}): {str(e)}", parse_mode=PARSE_MODE)
        return 
    
def _start_listen(spot: Spot):
    # Stop any existing job before starting a new one
    if spot.chat_id in us.listeners.keys():
        scheduler.cancel_job(us.listeners[spot.chat_id])
    # Schedule the listen job every min
    us.listeners[spot.chat_id] = scheduler.every(cfg.SCHEDULE_LISTEN).minutes.do(_listen, user_id=spot.user_id, chat_id=spot.chat_id)
    spot.listener = True
    # Initial check immediately
    _listen(spot.user_id, spot.chat_id)

def _stop_listen(spot: Spot):
    if spot.chat_id in us.listeners.keys():
        scheduler.cancel_job(us.listeners[spot.chat_id])
        del us.listeners[spot.chat_id]
    spot.listener = False

def listen(update: Update, context: CallbackContext, args: str = '{}') -> None:
    params = json.loads(args)
    user_id = params['uid']
    spot_id = params['cid']
    spot    = Spot(user_id, spot_id).get()
    context.user_data['temporary_callback'] = None
    context.user_data['requestor'] = None
    callback_data=json.dumps({'cmd':'ed_spot', 'uid':spot.user_id, 'cid':spot.chat_id})
    buttons = [[InlineKeyboardButton('OK', callback_data=callback_data)]]
    reply_markup = InlineKeyboardMarkup(buttons)
    if not spot.listener:
        # If need to turn on
        _start_listen(spot)
        msg = cfg.msg_listeneron
        msg += f'Тепер бот слухатиме {spot.label} і повідомлятиме про зміну статусу, якщо повідомлення припиняться більше, ніж на 3 хв.\n'
    else:
        # If need to turn off
        _stop_listen(spot)
        msg = cfg.msg_listeneroff
    spot.refresh()
    edit_md(msg + "\n" + verbiages._get_settings(spot), update, reply_markup=reply_markup)

# def go(update: Update, context: CallbackContext) -> None:
#     user_id = str(update.message.from_user.id)
#     chat_id = update.message.chat_id
#     if user_id not in us.user_settings.keys():
#         reply_md(cfg.msg_error, update)
#         return
#     user = us.User(user_id, chat_id)
#     if not user.ping_job == 'scheduled':
#         reply_md(cfg.msg_ippingondetailed, update)
#         ping(update, context)

# def stop(update: Update, context: CallbackContext) -> None:
#     user_id = str(update.message.from_user.id)
#     chat_id = update.message.chat_id
#     logger.info(f'User {user_id} stopped both ping and listener')
#     if user_id not in us.user_settings.keys():
#         reply_md(cfg.msg_error, update)
#         return
#     user = us.User(user_id, chat_id)
#     if user.ping_job == 'scheduled':
#         ping(update, context)
#     if user.listener:
#         listen(update, context)

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

def handle_input(update: Update, context: CallbackContext) -> None:
    global sys_commands

    try:
        requestor = context.user_data['requestor']
        callback  = context.user_data['temporary_callback']
    except Exception as e:
        requestor = None
    
    if requestor == "ask_set_ip":
        set_ip(update = update, context = context, args = callback)
    elif requestor == "ask_set_label":
        set_label(update = update, context = context, args = callback)
    elif requestor == "ask_set_channel": 
        set_channel(update = update, context = context, args = callback)
        
    try:
        user_id = str(update.message.from_user.id)
        chat_id = update.message.chat_id
    except Exception as e:
        logger.error(f'Error processing handle_input: {str(e)}')
        return
    user = Userdb(int(user_id))
    spot = Spot(user.user_id, str(user.user_id))
    # if user.awaiting_ip:
    #     user.toggle_nowait()
    #     if update.message.text[:20] == '-' and user.ip_address:
    #         update.message.reply_text('ІР адресу видалено')
    #         logger.info(f'User {user_id} deleted IP')
    #         user.ip_address = None
    #         user.ping_job = None
    #         if user.user_id in us.user_jobs.keys():
    #             scheduler.cancel_job(us.user_jobs[user.user_id])
    #         user.save()
    #         return 
    #     elif update.message.text[:20] == '-' and not user.ip_address:
    #         update.message.reply_text('Скасовано')
    #         user.save()
    #         return
    #     else:
    #         user.ip_address = update.message.text[:20]
    #     if not user.label or user.label == '':
    #         user.toggle_awaiting_label()
    #         logger.info(f'User {user_id} specified {user.ip_address} as IP')
    #         update.message.reply_text(f'Вказано IP адресу {user.ip_address}. Тепер вкажіть, будь-ласка, назву:')
    #     else:
    #         logger.info(f'User {user_id} specified {user.ip_address} as IP')
    #         reply_md(f'Вказано IP адресу {user.ip_address}', update)
    # elif user.awaiting_label:
    #     user.toggle_nowait()
    #     if update.message.text[:255] == '-' and user.label:
    #         update.message.reply_text('Назву видалено')
    #         logger.info(f'User {user_id} deleted label')
    #         user.label = None
    #         user.save()
    #         return 
    #     elif update.message.text[:255] == '-' and not user.label:
    #         update.message.reply_text('Скасовано')
    #         user.save()
    #         return
    #     else:
    #         user.label = update.message.text[:255]
    #         logger.info(f'User {user_id} specified label "{user.label}"')
    #         update.message.reply_text(f'Назву оновлено на {user.label}. Тепер можна активізувати моніторинг')
    # if user.awaiting_channel:
    #      user.toggle_nowait()
    #      if update.message.text[:255] == '-' and user.channel_id:
    #         update.message.reply_text('Канал видалено')
    #         logger.info(f'User {user_id} deleted channel')
    #         user.channel_id = None
    #         user.save()
    #         return 
    #      elif update.message.text[:255] == '-' and not user.channel_id:
    #         update.message.reply_text('Скасовано')
    #         user.save()
    #         return
    #      elif ' ' in update.message.text:
    #         reply_md(cfg.msg_badinput, update, main_menu_markup)
    #         user.save()
    #         return
    #      else:
    #         channel_id = update.message.text[:255]
    #         if channel_id.startswith('https://t.me/'): channel_id = channel_id.replace('https://t.me/', '')
    #         if not channel_id.startswith('@') and not channel_id[1:].isnumeric(): channel_id = '@' + channel_id
    #         user.channel_id = channel_id
    #         logger.info(f'User {user_id} specified channel "{user.channel_id}"')
    #         update.message.reply_text(f'Налаштовано публікацію в канал {channel_id}')
    # if user.awaiting_city:
    #     user.toggle_nowait()
    #     if update.message.text[:255] == '-':
    #         update.message.reply_text('Скасовано')
    #         user.city         = None
    #         user.group        = None
    #         user.has_schedule = False
    #     else:
    #         user.city = None
    #         entered = str(update.message.text[:255])
    #         #for city in bos.bo_cities.keys():
    #         #    if entered == city:
    #         user.city = entered
    #         if not user.city: 
    #             reply_md(cfg.msg_badinput, update, main_menu_markup)
    #             user.save()
    #             return            
    #         user.toggle_awaiting_group()
    #         logger.info(f'User {user_id} specified city "{user.city}"')
    #         update.message.reply_text(f'Вказано {user.city}. {cfg.msg_setgroup}')
    # elif user.awaiting_group:
    #     user.toggle_nowait()
    #     if update.message.text[:1] == '-':
    #         update.message.reply_text('Скасовано')
    #         user.city         = None
    #         user.group        = None
    #         user.has_schedule = False
    #     else:
    #         user.group = None
    #         entered = str(update.message.text[:1])
    #         #for group in bos.bo_groups.keys():
    #         #    if entered == str(group):
    #         user.group = entered
    #         if not user.group: 
    #             reply_md(cfg.msg_badinput, update, main_menu_markup)
    #             user.save()
    #             return            
    #         user.has_schedule = True
    #         logger.info(f'User {user_id} specified group "{user.group}"')
    #         update.message.reply_text(f'Вказано {user.city}: Група {user.group}')
    #         #_gather_schedules()
    if get_syscommand(spot.user_id, 'ask_get_user') and str(spot.user_id) == bot_secrets.ADMIN_ID:
        spot = Spot(int(update.message.text), update.message.text)
        bot.send_message(chat_id=chat_id, text=verbiages.get_full_info(spot))
        sys_commands[chat_id]['ask_get_user'] = False
    elif get_syscommand(spot.user_id, 'ask_set_user_param'):
        sys_commands[chat_id]['ask_set_user_param'] = False
        cmd = json.loads(update.message.text)
        user_in = str(utils.get_key_safe(cmd, 'user', spot.user_id))
        if not str(spot.user_id) == bot_secrets.ADMIN_ID and str(user_in) != str(user.user_id):
            reply_md(cfg.msg_badinput, update)
            return
        param_in = str(utils.get_key_safe(cmd, 'param', None))
        if not param_in:
            reply_md(cfg.msg_badinput, update)
            return
        try:
            spot = Spot(int(user_in), str(user_in))
            value_in = utils.get_key_safe(cmd, 'value', None)
            if param_in == 'last_ts' or param_in == 'last_heared_ts' or param_in == 'next_notification_ts' \
                or param_in == 'next_outage_ts'or param_in == 'tom_notification_ts'or param_in == 'tom_schedule_ts':
                code = f"spot.{param_in} = datetime.strptime('{value_in}', '%Y-%m-%d %H:%M:%S')"
            elif param_in == 'listener' or param_in == 'to_bot' or param_in == 'to_channel' \
                or param_in == 'has_schedule' or param_in == 'to_remind' or param_in == 'to_telegram':
                code = f"spot.{param_in} = {value_in}"
            else:
                code = f"spot.{param_in} = '{value_in}'"
            if not value_in:
                reply_md(cfg.msg_badinput, update)
                return
            exec(code)
        except Exception as e:
            logger.error(f'User {user_id} tried to perform "{code}" and got {str(e)}')
        logger.info(f'User {user_id} specified param {param_in} for {user.user_id} as "{value_in}"')
        bot.send_message(chat_id=chat_id, text=verbiages.get_full_info(user)) 
    elif get_syscommand(spot.user_id, 'ask_help'):
        help_point = update.message.text
        help_msg = utils.get_key_safe(cfg.msg_help, help_point, '')
        sys_commands[chat_id]['ask_help'] = False
        if help_msg == '':
            reply_md(cfg.msg_badinput, update)
            return
        reply_md(help_msg, update, main_menu_markup)
    # elif get_syscommand(spot.user_id, 'ask_broadcast'):
    #     msg = update.message.text
    #     sys_commands[chat_id]['ask_broadcast'] = False
    #     if msg == '':
    #         reply_md(cfg.msg_badinput, update)
    #         return
    #     for user_id in us.user_settings.keys():
    #         try:
    #             bot.send_message(chat_id=user_id, text=msg) 
    #         except:
    #             logger.error(f"Error occured while sending\n{traceback.format_exc()}")
    #             continue
    else: return

def ping_now(update: Update, context: CallbackContext, args:str = '{}') -> None:
    params = json.loads(args)
    user_id = params['uid']
    spot_id = params['cid']
    spot    = Spot(user_id, spot_id).get()
    context.user_data['temporary_callback'] = None
    context.user_data['requestor'] = None

    buttons = [[InlineKeyboardButton('OK', callback_data=json.dumps({'cmd':'main_menu'}))]]
    reply_markup = InlineKeyboardMarkup(buttons)
    if not spot.ip_address and not spot.listener and not spot.endpoint:
        reply_md(cfg.msg_noip, update, reply_markup)
        return
    if spot.ip_address or spot.endpoint:
        result = actions._ping_ip(spot, True)
        msg    = utils.get_text_safe_to_markdown(result.message)
    else:
        if not spot.last_heared_ts: spot.last_heared_ts = spot.last_ts
        delta   = datetime.now() - max(spot.last_heared_ts, spot.last_ts)
        seconds = 86400*delta.days + delta.seconds
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
        msg = actions.get_state_msg(spot, status, True)
        msg = utils.get_text_safe_to_markdown(msg)
        result = utils.PingResult(False, msg)
    if result.message: 
        header = utils.get_text_safe_to_markdown(f'*{spot.name}*\n' if not spot.is_multipost else '')
        bot.send_message(chat_id=spot.user_id,
                         text=header + msg,
                         parse_mode=PARSE_MODE)
    if msg and result.changed and spot.to_channel and spot.channel_id:
        bot.send_message(chat_id=spot.treated_channel_id, 
                         message_thread_id=spot.thread_id, 
                         text=msg, 
                         parse_mode=PARSE_MODE)

def _heard(user_id: str, chat_id: str) -> None:
    msg = None
    user = Userdb(int(user_id)).get()
    if not user: return
    spot = Spot(user.user_id, chat_id).get()
    if spot.listener:
        msg  = actions.get_state_msg(spot, cfg.ALIVE, False)
        msg  = utils.get_text_safe_to_markdown(msg)
        if spot.last_state != cfg.ALIVE:
            spot.last_state = cfg.ALIVE
            spot.last_ts    = datetime.now()
        spot.last_heared_ts = datetime.now()
        try:
            if msg and spot.to_bot: 
                header = utils.get_text_safe_to_markdown(f'*{spot.name}*\n' if not spot.is_multipost else '')
                bot.send_message(chat_id=spot.user_id, 
                                text=header + msg, 
                                parse_mode=PARSE_MODE)
            if msg and spot.to_channel and spot.channel_id:
                bot.send_message(chat_id=spot.treated_channel_id, 
                                message_thread_id=spot.thread_id, 
                                text=msg, 
                                parse_mode=PARSE_MODE)
        except Exception as e:
            logger.error(f'Error in _heard({user_id},{chat_id}): bot {spot.user_id} tried to send to {spot.treated_channel_id}, exception: {str(e)}')

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

def schedule_pings():
    while True:
        scheduler.run_pending()
        time.sleep(1)

def get_scheduled_jobs(update: Update, context: CallbackContext) -> None:
    chat_id = update.effective_chat.id
    if str(chat_id) == bot_secrets.ADMIN_ID:
        jobs = scheduler.get_jobs()
        for job in range(len(jobs)):
            bot.send_message(chat_id=chat_id, text=str(jobs[job]))

def get_users(update: Update, context: CallbackContext) -> None:
    chat_id = update.effective_chat.id
    if str(chat_id) == bot_secrets.ADMIN_ID:
        session = SessionMain()
        spots = session.query(models.Spot).all()
        for spot in spots:
            bot.send_message(chat_id=chat_id, text=verbiages.get_full_info(spot))

def get_user(update: Update, context: CallbackContext) -> None:
    global sys_commands
    chat_id = update.effective_chat.id
    if str(chat_id) == bot_secrets.ADMIN_ID:
        sys_commands[chat_id] = {}
        sys_commands[chat_id]['ask_get_user'] = True
        update.message.reply_text('Введіть ІД користувача:')
    else:
        spot = Spot(int(chat_id), str(chat_id))
        bot.send_message(chat_id=chat_id, text=verbiages.get_full_info(spot))

def get_user_params(update: Update, context: CallbackContext) -> None:
    update.message.reply_text(cfg.msg_listparams)

def set_user_param(update: Update, context: CallbackContext) -> None:
    global sys_commands
    chat_id = update.effective_chat.id
    sys_commands[chat_id] = {}
    sys_commands[chat_id]['ask_set_user_param'] = True
    update.message.reply_text('Введіть команду:')

def broadcast(update: Update, context: CallbackContext) -> None:
    chat_id = update.effective_chat.id
    if str(chat_id) == bot_secrets.ADMIN_ID:
        sys_commands[chat_id] = {}
        sys_commands[chat_id]['ask_broadcast'] = True
        update.message.reply_text('Введіть повідомлення для розсилки:')

def help(update: Update, context: CallbackContext, args:str = None) -> None:
    global sys_commands
    chat_id = update.effective_chat.id
    sys_commands[chat_id] = {}
    sys_commands[chat_id]['ask_help'] = True
    reply_md(cfg.msg_helplist, update)
    update.message.reply_text('Введіть пункт довідки:')

# Load user settings to DB
us.sync_user_settings()

# Up jobs if were saved
session = SessionMain()
spots = session.query(models.Spot).all()
for cur_spot in spots:
    try:
        if cur_spot.ping_job:
            if cur_spot.chat_id in us.user_jobs.keys():
                scheduler.cancel_job(us.user_jobs[cur_spot.chat_id])
            if cur_spot.ip_address and not cur_spot.endpoint:
                us.user_jobs[cur_spot.chat_id] = scheduler.every(cfg.SCHEDULE_PING).minutes.do(_ping, user_id=cur_spot.user_id, chat_id=cur_spot.chat_id)
            elif cur_spot.endpoint:
                us.user_jobs[cur_spot.chat_id] = scheduler.every(2*int(cfg.SCHEDULE_PING)).minutes.do(_ping, user_id=cur_spot.user_id, chat_id=cur_spot.chat_id)
        if cur_spot.listener:
            if cur_spot.chat_id in us.listeners.keys():
                scheduler.cancel_job(us.listeners[cur_spot.chat_id])
            us.listeners[cur_spot.chat_id] = scheduler.every(cfg.SCHEDULE_LISTEN).minutes.do(_listen, user_id=cur_spot.user_id, chat_id=cur_spot.chat_id)
    except Exception as e:
        continue
session.close()

#TODO Blackout schedule
# _gather_schedules()
# _notification_schedules()
# bos.get_blackout_schedule()
# bos.set_notifications()

# Function to handle button clicks (callbacks)
def button_callback(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    try:
        query.answer()  # Acknowledge the callback
    except Exception as e:
        return
    params = json.loads(query.data)
    cmd = params['cmd']

    # Take action based on which button was clicked
    if cmd == "start":
        start(update = update, context = context)
    elif cmd == "main_menu":
        main_menu(update = update, context = context)
    elif cmd == "ed_spot":
        settings_spot(update = update, context = context, args = query.data)
    elif cmd == "add_spot":
        add_spot(update = update, context = context, args = query.data)
    elif cmd == "sIp":
        ask_set_ip(update = update, context = context, args = query.data)
    elif cmd == "sLabel":
        ask_set_label(update = update, context = context, args = query.data)
    elif cmd == "sChannel":
        ask_set_channel(update = update, context = context, args = query.data)
    elif cmd == "sToBot":
        post_to_bot(update = update, context = context, args = query.data)    
    elif cmd == "sToChannel":
        post_to_channel(update = update, context = context, args = query.data)
    elif cmd == "sPing":
        ping(update = update, context = context, args = query.data)
    elif cmd == "sLsn":
        listen(update = update, context = context, args = query.data)
    elif cmd == "ping":
        ping_now(update = update, context = context, args = query.data)
    elif cmd == "settings":
        settings(update = update, context = context, args = query.data)
    elif cmd == "help":
        help(update = update, context = context, args = query.data)
        

# Register command handlers
dispatcher.add_handler(CommandHandler("start", start))
dispatcher.add_handler(CommandHandler("settings", settings))
dispatcher.add_handler(CommandHandler("mainmenu", main_menu))
#dispatcher.add_handler(CommandHandler("go", go))
#dispatcher.add_handler(CommandHandler("stop", stop))
dispatcher.add_handler(CommandHandler("check", ping_now))
dispatcher.add_handler(CommandHandler("ping", ping))
dispatcher.add_handler(CommandHandler("listen", listen))
dispatcher.add_handler(CommandHandler("setip", set_ip))
dispatcher.add_handler(CommandHandler("setlabel", set_label))
dispatcher.add_handler(CommandHandler("setchannel", set_channel))
#dispatcher.add_handler(CommandHandler("yasnoschedule", yasno_schedule))
#dispatcher.add_handler(CommandHandler("reminder", reminder))
dispatcher.add_handler(CommandHandler("posttobot", post_to_bot))
dispatcher.add_handler(CommandHandler("posttochannel", post_to_channel))
#dispatcher.add_handler(CommandHandler("gettomschedule", get_tom_schedule))
dispatcher.add_handler(CommandHandler("getscheduledjobs", get_scheduled_jobs))
dispatcher.add_handler(CommandHandler("getusers", get_users))
dispatcher.add_handler(CommandHandler("getuser", get_user))
dispatcher.add_handler(CommandHandler("setuserparam", set_user_param))
dispatcher.add_handler(CommandHandler("getuserparams", get_user_params))
dispatcher.add_handler(CommandHandler("broadcast", broadcast))
dispatcher.add_handler(CommandHandler("help", help))

#dispatcher.add_handler(MessageHandler(Filters.regex('^Старт$'), lambda update, context: go(update, context)))
dispatcher.add_handler(MessageHandler(Filters.regex('^Отримати статус негайно$'), ping_now))
dispatcher.add_handler(MessageHandler(Filters.regex('^Налаштування$'), settings))
dispatcher.add_handler(MessageHandler(Filters.regex('^Головне меню$'), main_menu))
#dispatcher.add_handler(MessageHandler(Filters.regex('^Стоп$'), stop))
dispatcher.add_handler(MessageHandler(Filters.regex('^Вказати IP$'), set_ip))
dispatcher.add_handler(MessageHandler(Filters.regex('^Вказати назву$'), set_label))
dispatcher.add_handler(MessageHandler(Filters.regex('^Вказати канал$'), set_channel))
#dispatcher.add_handler(MessageHandler(Filters.regex('^Графік$'), yasno_schedule))
#dispatcher.add_handler(MessageHandler(Filters.regex('^Нагадати$'), reminder))
dispatcher.add_handler(MessageHandler(Filters.regex('^-> в канал \(так/ні\)$'), lambda update, context: post_to_channel(update, context)))
dispatcher.add_handler(MessageHandler(Filters.regex('^-> в бот \(так/ні\)$'), lambda update, context: post_to_bot(update, context)))
dispatcher.add_handler(MessageHandler(Filters.regex('^Пінг \(так/ні\)$'), lambda update, context: ping(update, context)))
dispatcher.add_handler(MessageHandler(Filters.regex('^Слухати \(так/ні\)$'), lambda update, context: listen(update, context)))
dispatcher.add_handler(MessageHandler(Filters.regex('^\?$'), help))
dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_input))

dispatcher.add_handler(CallbackQueryHandler(button_callback))# For inline button callbacks

# Start the scheduler thread
scheduler_thread = threading.Thread(target=schedule_pings)
scheduler_thread.start()

# Flask endpoint to send message
@app.route('/send', methods=['GET'])
def send():
    # here is the mess: external chat_id is the telegram user_id, but internal it's a compound spot_id \
    # that equal to external chat_iв + spot_id (sequence of chat_if with 1,2,3 spot index)
    sender = request.args.get('chat_id')
    spot   = request.args.get('spot_id')
    TIMEZONE = pytz.timezone(cfg.TZ)
    ts = datetime.now(TIMEZONE).strftime('%d.%m.%Y %H:%M:%S')
    spot = sender if not spot else spot
    #caller_ip = request.remote_addr
    if not sender:
        return jsonify({"error": "chat_id is required"}), 400
    try:
        _heard(sender, spot)
        return jsonify({"status": "OK", "time": ts}), 200
    except Exception as e:
        return jsonify({"error": 'Unexpected error'}), 500
    
@app.route('/get', methods=['GET'])
def get():
    # here is the mess: external chat_id is the telegram user_id, but internal it's a compound spot_id \
    # that equal to external chat_iв + spot_id (sequence of chat_if with 1,2,3 spot index)
    sender = request.args.get('chat_id')
    _spot  = request.args.get('spot_id')
    TIMEZONE = pytz.timezone(cfg.TZ)
    ts = datetime.now(TIMEZONE).strftime('%d.%m.%Y %H:%M:%S')
    _spot = sender if not _spot else _spot
    #caller_ip = request.remote_addr
    if not sender:
        return jsonify({"error": "chat_id is required"}), 400
    try:
        spot = Spot(sender, _spot).get()
        message = verbiages.get_state_msg(spot, spot.last_state, True)
        return jsonify({"message": message, "state": spot.last_state, "time": ts}), 200
    except Exception as e:
        return jsonify({"error": 'Unexpected error'}), 500
    
@app.route('/on', methods=['GET'])
def on():
    # here is the mess: external chat_id is the telegram user_id, but internal it's a compound spot_id \
    # that equal to external chat_iв + spot_id (sequence of chat_if with 1,2,3 spot index)
    sender = request.args.get('chat_id')
    spot   = request.args.get('spot_id')
    TIMEZONE = pytz.timezone(cfg.TZ)
    ts = datetime.now(TIMEZONE).strftime('%d.%m.%Y %H:%M:%S')
    spot = sender if not spot else spot
    #caller_ip = request.remote_addr
    if not sender:
        return jsonify({"error": "chat_id is required"}), 400
    try:
        _ping(sender, spot, cfg.ALIVE)
        return jsonify({"status": "OK", "time": ts}), 200
    except Exception as e:
        return jsonify({"error": 'Unexpected error'}), 500
    
@app.route('/off', methods=['GET'])
def off():
    # here is the mess: external chat_id is the telegram user_id, but internal it's a compound spot_id \
    # that equal to external chat_iв + spot_id (sequence of chat_if with 1,2,3 spot index)
    sender = request.args.get('chat_id')
    spot   = request.args.get('spot_id')
    TIMEZONE = pytz.timezone(cfg.TZ)
    ts = datetime.now(TIMEZONE).strftime('%d.%m.%Y %H:%M:%S')
    spot = sender if not spot else spot  
    #caller_ip = request.remote_addr
    if not sender:
        return jsonify({"error": "chat_id is required"}), 400
    try:
        _ping(sender, spot, cfg.OFF)
        return jsonify({"status": "OK", "time": ts}), 200
    except Exception as e:
        return jsonify({"error": 'Unexpected error'}), 500
    
if __name__ == '__main__':
    # Start the Telegram bot
    updater.start_polling()
    #updater.idle()

    # Run the Flask app
    app.run(host='0.0.0.0', port=5000)    