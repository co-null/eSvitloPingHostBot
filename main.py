import bot_secrets, config as cfg, user_settings as us, utils, verbiages, actions, blackout_schedule as bos
from telegram.ext import Updater, CommandHandler, CallbackContext, MessageHandler, Filters
from telegram import Update, Bot, ReplyKeyboardMarkup, KeyboardButton, constants
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
fh = TimedRotatingFileHandler('esvitlo.log', encoding='utf-8', when="D", interval=1, backupCount=30)
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
                      [KeyboardButton('Старт моніторингу'),
                       KeyboardButton('Зупинка моніторингу')],
                       [KeyboardButton('Налаштування')]]

# Define the settings menu
settings_menu_keyboard = [[KeyboardButton('Вказати IP'), 
                          KeyboardButton('Вказати назву'), 
                          KeyboardButton('Вказати канал')], 
                          [KeyboardButton('-> в бот (так/ні)'), 
                          KeyboardButton('-> в канал (так/ні)')], 
                          [KeyboardButton('Пінгувати (так/ні)'),
                           KeyboardButton('Слухати (так/ні)'),
                           KeyboardButton('Графік'), 
                           KeyboardButton('Нагадати')],
                          [KeyboardButton('Головне меню')]]

main_menu_markup     = ReplyKeyboardMarkup(main_menu_keyboard, resize_keyboard=True)
settings_menu_markup = ReplyKeyboardMarkup(settings_menu_keyboard, resize_keyboard=True)

#Global vars
sys_commands = {}

def reply_md(message:str, update: Update, reply_markup = None) -> None:
    message = utils.get_text_safe_to_markdown(message)
    update.message.reply_text(message, reply_markup=reply_markup, parse_mode=PARSE_MODE)

def start(update: Update, context: CallbackContext) -> None:
    user_id = str(update.message.from_user.id)
    chat_id = update.message.chat_id
    user    = us.User(user_id, chat_id)
    logger.info(f'User {user_id} invoked "start"')
    if user.new :
        reply_md(cfg.msg_greeting, update)
        logger.info(f'start: User {user_id} invoked is new')
    else:
        # Recreate the jobs if saved previously
        logger.info(f'start: User {user_id} - recreating jobs')
        if user.ping_job:
            if user_id in us.user_jobs.keys():
                scheduler.cancel_job(us.user_jobs[user_id])
            us.user_jobs[user_id] = scheduler.every(cfg.SCHEDULE_PING).minutes.do(_ping, user_id=user_id, chat_id=chat_id)
        if user.listener:
            if user_id in us.listeners.keys():
                scheduler.cancel_job(us.listeners[user_id])
            us.listeners[user_id] = scheduler.every(cfg.SCHEDULE_LISTEN).minutes.do(_listen, user_id=user_id, chat_id=chat_id)
        if user.has_schedule:
            _gather_schedules()
            _notification_schedules()
        reply_md(cfg.msg_comeback, update, reply_markup=main_menu_markup)
    bos.get_blackout_schedule()
    bos.set_notifications()

def settings(update: Update, context: CallbackContext) -> None:
    user_id = str(update.message.from_user.id)
    logger.info(f'User {user_id} invoked "settings"')
    if user_id not in us.user_settings.keys():
        reply_md(cfg.msg_error, update)
        logger.warning(f'settings: User {user_id} unknown')
        return
    if utils.get_system() == 'windows':
        link = cfg.LOCAL_URL + user_id
    else: link = cfg.LISTENER_URL + user_id
    link = f"Для налаштування слухача робіть виклики на {link}"
    update.message.reply_text(verbiages.get_settings(user_id) + "\n" + link, 
                              reply_markup=settings_menu_markup)

def main_menu(update: Update, context: CallbackContext) -> None:
    reply_md(cfg.msg_mainmnu, update, reply_markup=main_menu_markup)

def set_ip(update: Update, context: CallbackContext) -> None:
    user_id = str(update.message.from_user.id)
    chat_id = update.message.chat_id
    logger.info(f'User {user_id} invoked "set_ip"')
    if user_id not in us.user_settings.keys():
        reply_md(cfg.msg_error, update)
        logger.warning(f'set_ip: User {user_id} unknown')
        return
    user = us.User(user_id, chat_id)
    user.toggle_awaiting_ip()
    user.save()
    update.message.reply_text(cfg.msg_setip)

def set_label(update: Update, context: CallbackContext) -> None:
    user_id = str(update.message.from_user.id)
    chat_id = update.message.chat_id
    logger.info(f'User {user_id} invoked "set_label"')
    if user_id not in us.user_settings.keys():
        reply_md(cfg.msg_error, update)
        logger.warning(f'User {user_id} unknown')
        return
    user = us.User(user_id, chat_id)
    user.toggle_awaiting_label()
    user.save()
    update.message.reply_text(cfg.msg_setlabel)

def set_channel(update: Update, context: CallbackContext) -> None:
    user_id = str(update.message.from_user.id)
    chat_id = update.message.chat_id
    logger.info(f'User {user_id} invoked "set_channel"')
    if user_id not in us.user_settings.keys():
        reply_md(cfg.msg_error, update)
        logger.warning(f'User {user_id} unknown')
        return
    user = us.User(user_id, chat_id)
    user.toggle_awaiting_channel()
    user.save()
    update.message.reply_text(cfg.msg_setchannel)

def yasno_schedule(update: Update, context: CallbackContext) -> None:
    user_id = str(update.message.from_user.id)
    chat_id = update.message.chat_id
    logger.info(f'User {user_id} invoked "yasno_schedule"')
    if user_id not in us.user_settings.keys():
        reply_md(cfg.msg_error, update)
        logger.warning(f'User {user_id} unknown')
        return
    user = us.User(user_id, chat_id)
    msg = f'{cfg.msg_setcity}\n{verbiages.get_key_list(bos.bo_cities)}'
    msg += cfg.msg_setcitybottom
    user.toggle_awaiting_city()
    user.save()
    update.message.reply_text(msg)

def get_tom_schedule(update: Update, context: CallbackContext) -> None:
    user_id = str(update.message.from_user.id)
    chat_id = update.message.chat_id
    logger.info(f'User {user_id} invoked "get_tom_schedule"')
    if user_id not in us.user_settings.keys():
        reply_md(cfg.msg_error, update)
        logger.warning(f'User {user_id} unknown')
        return
    user = us.User(user_id, chat_id)
    msg = verbiages.get_notificatiom_tomorrow_schedule(bos.get_windows_for_tomorrow(user))
    reply_md(msg, update)


def reminder(update: Update, context: CallbackContext) -> None:
    user_id = str(update.message.from_user.id)
    chat_id = update.message.chat_id
    logger.info(f'User {user_id} invoked "reminder"')
    if user_id not in us.user_settings.keys():
        reply_md(cfg.msg_error, update)
        logger.warning(f'User {user_id} unknown')
        return
    user = us.User(user_id, chat_id)
    if not user.to_remind and not user.has_schedule:
        reply_md(cfg.msg_reminder_no_schedule, update)
    elif not user.to_remind and user.has_schedule:
        user.to_remind = True
        reply_md(cfg.msg_reminder_turnon, update)
    elif user.to_remind and user.has_schedule:
        user.to_remind = False
        reply_md(cfg.msg_reminder_off, update)
    _notification_schedules()
    user.save()

def handle_input(update: Update, context: CallbackContext) -> None:
    global sys_commands
    try:
        user_id = str(update.message.from_user.id)
        chat_id = update.message.chat_id
    except Exception as e:
        logger.error(f'Error processing handle_input: {traceback.format_exc()}')
        return
    logger.info(f'User {user_id} entered "{update.message.text}"')
    if user_id not in us.user_settings.keys():
        reply_md(cfg.msg_error, update)
        logger.info(f'User {user_id} - "{cfg.msg_error}"')
        return
    user = us.User(user_id, chat_id)
    if user.awaiting_ip:
        user.toggle_nowait()
        if update.message.text[:20] == '-' and user.ip_address:
            update.message.reply_text('ІР адресу видалено')
            logger.info(f'User {user_id} deleted IP')
            user.ip_address = None
            user.ping_job = None
            if user.user_id in us.user_jobs.keys():
                scheduler.cancel_job(us.user_jobs[user.user_id])
            user.save()
            return 
        elif update.message.text[:20] == '-' and not user.ip_address:
            update.message.reply_text('Скасовано')
            user.save()
            return
        else:
            user.ip_address = update.message.text[:20]
        if not user.label or user.label == '':
            user.toggle_awaiting_label()
            logger.info(f'User {user_id} specified {user.ip_address} as IP')
            update.message.reply_text(f'Вказано IP адресу {user.ip_address}. Тепер вкажіть, будь-ласка, назву:')
        else:
            logger.info(f'User {user_id} specified {user.ip_address} as IP')
            reply_md(f'Вказано IP адресу {user.ip_address}', update)
    elif user.awaiting_label:
        user.toggle_nowait()
        if update.message.text[:255] == '-' and user.label:
            update.message.reply_text('Назву видалено')
            logger.info(f'User {user_id} deleted label')
            user.label = None
            user.save()
            return 
        elif update.message.text[:255] == '-' and not user.label:
            update.message.reply_text('Скасовано')
            user.save()
            return
        else:
            user.label = update.message.text[:255]
            logger.info(f'User {user_id} specified label "{user.label}"')
            update.message.reply_text(f'Назву оновлено на {user.label}. Тепер можна активізувати моніторинг (пінг)')
    elif user.awaiting_channel:
         user.toggle_nowait()
         if update.message.text[:255] == '-' and user.channel_id:
            update.message.reply_text('Канал видалено')
            logger.info(f'User {user_id} deleted channel')
            user.channel_id = None
            user.save()
            return 
         elif update.message.text[:255] == '-' and not user.channel_id:
            update.message.reply_text('Скасовано')
            user.save()
            return
         elif ' ' in update.message.text:
            update.message.reply_text('Некоректний ввод')
            user.save()
            return
         else:
            channel_id = update.message.text[:255]
            if channel_id.startswith('https://t.me/'): channel_id = channel_id.replace('https://t.me/', '')
            if not channel_id.startswith('@') and not channel_id[1:].isnumeric(): channel_id = '@' + channel_id
            user.channel_id = channel_id
            logger.info(f'User {user_id} specified channel "{user.channel_id}"')
            update.message.reply_text(f'Налаштовано публікацію в канал {channel_id}')
    elif user.awaiting_city:
        user.toggle_nowait()
        if update.message.text[:255] == '-':
            update.message.reply_text('Скасовано')
            user.city         = None
            user.group        = None
            user.has_schedule = False
        else:
            user.city = None
            entered = str(update.message.text[:255])
            for city in bos.bo_cities.keys():
                if entered == city:
                    user.city = entered
            if not user.city: 
                update.message.reply_text('Некоректний ввод')
                user.save()
                return            
            user.toggle_awaiting_group()
            logger.info(f'User {user_id} specified city "{user.city}"')
            update.message.reply_text(f'Вказано {user.city}. {cfg.msg_setgroup}')
    elif user.awaiting_group:
        user.toggle_nowait()
        if update.message.text[:1] == '-':
            update.message.reply_text('Скасовано')
            user.city         = None
            user.group        = None
            user.has_schedule = False
        else:
            user.group = None
            entered = str(update.message.text[:1])
            for group in bos.bo_groups.keys():
                if entered == str(group):
                    user.group = group
            if not user.group: 
                update.message.reply_text('Некоректний ввод')
                user.save()
                return            
            user.has_schedule = True
            logger.info(f'User {user_id} specified group "{user.group}"')
            update.message.reply_text(f'Вказано {user.city}: Група {user.group}')
            _gather_schedules()
    elif utils.get_key_safe(utils.get_key_safe(sys_commands, user.chat_id, {}),'ask_get_user', False) and str(user.chat_id) == bot_secrets.ADMIN_ID:
            user = us.User(update.message.text, update.message.text)
            bot.send_message(chat_id=chat_id, text=verbiages.get_full_info(user))
            sys_commands[chat_id]['ask_get_user'] = False
    elif utils.get_key_safe(utils.get_key_safe(sys_commands, user.chat_id, {}),'ask_set_user_param', False):
            cmd = json.loads(update.message.text)
            user_in = str(utils.get_key_safe(cmd, 'user', user.chat_id))
            if not str(user.chat_id) == bot_secrets.ADMIN_ID and user_in != user.chat_id:
                update.message.reply_text('Некоректний ввод')
            param_in = str(utils.get_key_safe(cmd, 'param', None))
            if not param_in:
                update.message.reply_text('Некоректний ввод')
            try:
                if param_in == 'last_ts' or param_in == 'last_heared_ts' or param_in == 'next_notification_ts' or param_in == 'next_outage_ts'or param_in == 'tom_notification_ts'or param_in == 'tom_schedule_ts':
                    value_in = datetime.strptime(utils.get_key_safe(cmd, 'value', None), '%Y-%m-%d %H:%M:%S')
                else:
                    value_in = utils.get_key_safe(cmd, 'value', None)
                if not value_in:
                    update.message.reply_text('Некоректний ввод')
                user = us.User(user_in, user_in)
                code = f"user.{param_in} = '{value_in}'"
                exec(code)
            except Exception as e:
                logger.error(f'User {user_id} tried to perform "{code}" and got {e}')
            sys_commands[chat_id]['ask_set_user_param'] = False
            logger.info(f'User {user_id} specified param {param_in} for {user.user_id} as "{value_in}"')
            user.save()
            bot.send_message(chat_id=chat_id, text=verbiages.get_full_info(user))  
    else: return
    user.save()
    #update.message.reply_text(verbiages.get_settings(user_id), reply_markup=settings_menu_markup)

def _start_ping(user: us.User) -> None:
    logger.info(f'User {user.user_id} started pinging IP')
    # Stop any existing job before starting a new one
    if user.user_id in us.user_jobs.keys():
        scheduler.cancel_job(us.user_jobs[user.user_id])
    # Schedule the ping job every min
    us.user_jobs[user.user_id] = scheduler.every(cfg.SCHEDULE_PING).minutes.do(_ping, user_id=user.user_id, chat_id=user.chat_id)
    user.ping_job = 'scheduled'
    user.save()
    # Initial ping immediately
    _ping(user.user_id, user.chat_id)

def _stop_ping(user: us.User) -> None:
    logger.info(f'User {user.user_id} stopped pinging IP')
    if user.user_id in us.user_jobs.keys():
        scheduler.cancel_job(us.user_jobs[user.user_id])
    user.ping_job = None
    user.save()

def ping(update: Update, context: CallbackContext) -> None:
    user_id = str(update.message.from_user.id)
    chat_id = update.message.chat_id
    if user_id not in us.user_settings.keys():
        reply_md(cfg.msg_error, update)
        return
    user = us.User(user_id, chat_id)
    if not user.ping_job == 'scheduled':
        # If need to turn on
        if not user.ip_address and not user.endpoint:
            reply_md(cfg.msg_noip, update)
            return
        _start_ping(user)
        msg = f'Тепер бот перевірятиме доступність {user.label} і повідомлятиме про зміну статусу'
    else:
        # If need to turn off
        if user_id in us.user_jobs.keys():
            msg = cfg.msg_stopped
        else:
            msg = cfg.msg_notset
        _stop_ping(user)
    update.message.reply_text(msg + "\n" + verbiages.get_settings(user_id))

def _start_listen(user: us.User):
    logger.info(f'User {user.user_id} started listener')
    # Stop any existing job before starting a new one
    if user.user_id in us.listeners.keys():
        scheduler.cancel_job(us.listeners[user.user_id])
    # Schedule the listen job every 5 min
    us.listeners[user.user_id] = scheduler.every(cfg.SCHEDULE_LISTEN).minutes.do(_listen, user_id=user.user_id, chat_id=user.chat_id)
    user.listener = True
    user.save()
    # Initial check immediately
    _listen(user.user_id, user.chat_id)

def _stop_listen(user: us.User):
    logger.info(f'User {user.user_id} stopped listener')
    if user.user_id in us.listeners.keys():
        scheduler.cancel_job(us.listeners[user.user_id])
    user.listener = False
    user.save()

def listen(update: Update, context: CallbackContext) -> None:
    user_id = str(update.message.from_user.id)
    chat_id = update.message.chat_id
    if user_id not in us.user_settings.keys():
        reply_md(cfg.msg_error, update)
        return
    user = us.User(user_id, chat_id)
    if not user.listener:
        # If need to turn on
        _start_listen(user)
        msg = cfg.msg_listeneron
        msg += f'Тепер бот слухатиме {user.label} і повідомлятиме про зміну статусу, якщо повідомлення припиняться більше, ніж на 5 хв.\n'
    else:
        # If need to turn off
        _stop_listen(user)
        msg = cfg.msg_listeneroff
    update.message.reply_text(msg + verbiages.get_settings(user_id))

def go(update: Update, context: CallbackContext) -> None:
    user_id = str(update.message.from_user.id)
    chat_id = update.message.chat_id
    if user_id not in us.user_settings.keys():
        reply_md(cfg.msg_error, update)
        return
    user = us.User(user_id, chat_id)
    if not user.ping_job == 'scheduled':
        reply_md(cfg.msg_ippingondetailed, update)
        ping(update, context)

def stop(update: Update, context: CallbackContext) -> None:
    user_id = str(update.message.from_user.id)
    chat_id = update.message.chat_id
    logger.info(f'User {user_id} stopped both ping and listener')
    if user_id not in us.user_settings.keys():
        reply_md(cfg.msg_error, update)
        return
    user = us.User(user_id, chat_id)
    if user.ping_job == 'scheduled':
        ping(update, context)
    if user.listener:
        listen(update, context)

def post_to_bot(update: Update, context: CallbackContext) -> None:
    user_id = str(update.message.from_user.id)
    chat_id = update.message.chat_id
    if user_id not in us.user_settings.keys():
        reply_md(cfg.msg_error, update)
        return
    user = us.User(user_id, chat_id)
    if not user.to_bot:
        #Turn on:
        user.to_bot = True
        msg = cfg.msg_postbot
    else:
        #Turn off:
        user.to_bot = False
        msg = cfg.msg_nopostbot
    user.save()
    update.message.reply_text(msg + "\n" + verbiages.get_settings(user_id), reply_markup=settings_menu_markup)

def post_to_channel(update: Update, context: CallbackContext) -> None:
    user_id = str(update.message.from_user.id)
    chat_id = update.message.chat_id
    if user_id not in us.user_settings.keys():
        reply_md(cfg.msg_error, update)
        return
    user = us.User(user_id, chat_id)
    if not user.to_channel:
        if user.channel_id: 
            # turn on
            user.to_channel = True
            msg = cfg.msg_postchannel
        else:
            user.to_channel = False
            msg = cfg.msg_nochannel
    else:
        # turn off
        user.to_channel = False
        msg = cfg.msg_nopostchannel
    user.save()
    update.message.reply_text(msg + "\n" + verbiages.get_settings(user_id), reply_markup=settings_menu_markup)

def _ping(user_id, chat_id):
    if user_id not in us.user_settings.keys():
        return
    user = us.User(user_id, chat_id)
    if not user.ip_address and not user.endpoint:
        user.ping_job = None
        user.save()
        if user.user_id in us.user_jobs.keys():
            scheduler.cancel_job(us.user_jobs[user.user_id])
    try:
        result = actions._ping_ip(user, False)
        msg    = utils.get_text_safe_to_markdown(result.message)
        if msg and user.to_bot: 
            try:
                bot.send_message(chat_id=user.chat_id, text=msg, parse_mode=PARSE_MODE)
            except Exception as e:
                logger.error(f'Forbidden: bot is not a member of the channel chat, {user_id} tried to send to {user.chat_id}')
        if msg and user.to_channel and user.channel_id:
            if str(user.channel_id).startswith('-') and str(user.channel_id)[1:].isnumeric():
                logger.info(f'Sending to private channel: User {user.user_id} to channel {user.channel_id}, msg: "{msg}"')
                channel_id:int = int(user.channel_id)
            else: 
                channel_id = user.channel_id
            try:
                bot.send_message(chat_id = channel_id, text=msg, parse_mode=PARSE_MODE)
            except Exception as e:
                logger.error(f'Forbidden: bot is not a member of the channel chat, {user_id} tried to send to {user.channel_id}')
        user.save_state()
    except Exception as e:
        logger.error(f"Exception in _ping({user_id}, {chat_id}): {traceback.format_exc()}")
        bot.send_message(chat_id=bot_secrets.ADMIN_ID, text=f"Exception in _ping\({user_id}, {chat_id}\): {e}", parse_mode=PARSE_MODE)
        return 

def ping_now(update: Update, context: CallbackContext) -> None:
    user_id = str(update.message.from_user.id)
    chat_id = update.message.chat_id
    if user_id not in us.user_settings.keys():
        reply_md(cfg.msg_error, update)
        return
    user = us.User(user_id, chat_id)
    if not user.ip_address and not user.listener and not user.endpoint:
        reply_md(cfg.msg_noip, update)
        return
    if user.ip_address or user.endpoint:
        result = actions._ping_ip(user, True)
        msg    = utils.get_text_safe_to_markdown(result.message)
    else:
        if not user.last_heared_ts: user.last_heared_ts = user.last_ts
        delta   = datetime.now() - max(user.last_heared_ts, user.last_ts)
        seconds = 86400*delta.days + delta.seconds
        if seconds >= 300 and user.last_state == cfg.ALIVE:
            status = cfg.OFF
        elif seconds < 300 and user.last_state == cfg.ALIVE:
            # still enabled
            status = cfg.ALIVE
        elif seconds < 300 and user.last_state == cfg.OFF:
            # already turned off
            status = cfg.OFF
        else:    
            # still turned off
            status = user.last_state
        msg = actions.get_state_msg(user, status, True)
        msg = utils.get_text_safe_to_markdown(msg)
        result = utils.PingResult(False, msg)
    if result.message: 
        bot.send_message(chat_id=user.chat_id, text=msg, parse_mode=PARSE_MODE)
    if msg and result.changed and user.channel_id:
        bot.send_message(chat_id=user.channel_id, text=msg, parse_mode=PARSE_MODE)

def _heard(user_id: str) -> None:
    msg = None
    if user_id not in us.user_settings.keys():
        return
    user = us.User(user_id, us.user_settings[user_id]['chat_id'])
    if user.listener:
        msg  = actions.get_state_msg(user, cfg.ALIVE, False)
        msg  = utils.get_text_safe_to_markdown(msg)
        if user.last_state != cfg.ALIVE:
            user.last_state = cfg.ALIVE
            user.last_ts    = datetime.now()
        user.last_heared_ts = datetime.now()
        user.save_state()
        if msg and user.to_bot: 
            bot.send_message(chat_id=user.chat_id, text=msg, parse_mode=PARSE_MODE)
        if msg and user.to_channel and user.channel_id:
            bot.send_message(chat_id=user.channel_id, text=msg, parse_mode=PARSE_MODE)

def _listen(user_id, chat_id):
    try:
        if user_id not in us.user_settings.keys():
            return
        user = us.User(user_id, chat_id)
        if not user.listener: 
            # was turned off somehow
            return
        # Do not spam if never worked
        if not user.last_state or not user.last_ts or not user.last_heared_ts: 
            return
        delta   = datetime.now() - max(user.last_heared_ts, user.last_ts)
        seconds = 86400*delta.days + delta.seconds
        # If >300 sec (5 mins) and was turned on - consider blackout
        if seconds >= 300 and user.last_state == cfg.ALIVE:
            status = cfg.OFF
        elif seconds < 300 and user.last_state == cfg.ALIVE:
            # still enabled
            status = cfg.ALIVE
        elif seconds < 300 and user.last_state == cfg.OFF:
            # already turned off
            status = cfg.OFF
        else:    
            # still turned off
            status = user.last_state
        if status==user.last_state: changed = False
        else: changed = True
        if changed: 
            msg = actions.get_state_msg(user, status, False)
            msg = utils.get_text_safe_to_markdown(msg)
            user.last_ts    = max(user.last_heared_ts, user.last_ts)
            user.last_state = status
            logger.info(f'Heared: User {user.user_id} - status: {status}, changed:{changed}')
        user.save_state()
        if changed and msg and user.to_bot: 
            try:
                bot.send_message(chat_id=user.chat_id, text=msg, parse_mode=PARSE_MODE)
            except Exception as e:
                print(f'Forbidden: bot is not a member of the channel chat, {user_id} tried to send to {user.chat_id}')
                logger.error(f'Forbidden: bot is not a member of the channel chat, {user_id} tried to send to {user.chat_id}')
        if changed and msg and user.to_channel and user.channel_id:
            try:
                bot.send_message(chat_id=user.channel_id, text=msg, parse_mode=PARSE_MODE)
            except Exception as e:
                print(f'Forbidden: bot is not a member of the channel chat, {user_id} tried to send to {user.channel_id}')
                logger.error(f'Forbidden: bot is not a member of the channel chat, {user_id} tried to send to {user.channel_id}')
    except Exception as e:
        logger.error(f"Exception in _listen({user_id}, {chat_id}): {traceback.format_exc()}")
        bot.send_message(chat_id=bot_secrets.ADMIN_ID, text=f"Exception in _listen({user_id}, {chat_id}): {e}", parse_mode=PARSE_MODE)
        return 

def _send_notifications():
    #print("Start send notifications job")
    #logger.info('Start send notifications job')
    try:
        # here all timestamp are in Kyiv TZ
        use_tz  = pytz.timezone(cfg.TZ)
        now_ts0 = datetime.now(use_tz)
        # make tz-naive
        now_ts = datetime.strptime((now_ts0.strftime('%Y-%m-%d %H:%M:%S')), '%Y-%m-%d %H:%M:%S')
        for user_id in us.user_settings.keys():
            chat_id = us.user_settings[user_id]['chat_id']
            user    = us.User(user_id, chat_id)
            if user.has_schedule and user.to_remind and user.next_notification_ts and user.next_outage_ts:
                if user.next_notification_ts < now_ts and user.next_outage_ts > now_ts and user.last_state == cfg.ALIVE:
                    # will send
                    msg = utils.get_text_safe_to_markdown(verbiages.get_notification_message_long(bos.get_next_outage_window(user)))
                    if msg and user.to_bot: 
                        try:
                            bot.send_message(chat_id=user.chat_id, text=msg, parse_mode=PARSE_MODE)
                        except Exception as e:
                            print(f'Forbidden: bot {user_id} tried to send to {user.chat_id}, exception: {traceback.format_exc()}')
                            logger.error(f'Forbidden: bot {user_id} tried to send to {user.chat_id}, exception: {traceback.format_exc()}')
                    if msg and user.to_channel and user.channel_id:
                        try:
                            bot.send_message(chat_id=user.channel_id, text=msg, parse_mode=PARSE_MODE)
                        except Exception as e:
                            print(f'Forbidden: bot is not a member of the channel chat, {user_id} tried to send to {user.channel_id}, exception: {traceback.format_exc()}')
                            logger.error(f'Forbidden: bot is not a member of the channel chat, {user_id} tried to send to {user.channel_id}, exception: {traceback.format_exc()}')
                    # update next_notification_ts so we'll not send again
                    user.next_notification_ts = user.next_outage_ts
                    user.save_state()
                elif user.next_notification_ts < now_ts and user.next_outage_ts > now_ts and user.last_state != cfg.ALIVE:
                    # already off
                    user.next_notification_ts = None
                    user.next_outage_ts       = None
                    user.save_state()
                elif user.next_outage_ts < now_ts:
                    # outdated
                    user.next_notification_ts = None
                    user.next_outage_ts       = None
                    user.save_state()
            if user.has_schedule and user.to_remind and user.tom_notification_ts and user.tom_schedule_ts:
                if user.tom_notification_ts < now_ts and user.tom_schedule_ts > now_ts:
                    # will send
                    msg = verbiages.get_notificatiom_tomorrow_schedule(bos.get_windows_for_tomorrow(user))
                    if msg and user.to_bot: 
                        try:
                            bot.send_message(chat_id=user.chat_id, text=msg, parse_mode=PARSE_MODE)
                        except Exception as e:
                            print(f'Forbidden: bot is not a member of the channel chat, {user_id} tried to send to {user.chat_id}')
                            logger.error(f'Forbidden: bot is not a member of the channel chat, {user_id} tried to send to {user.chat_id}')
                    if msg and user.to_channel and user.channel_id:
                        try:
                            bot.send_message(chat_id=user.channel_id, text=msg, parse_mode=PARSE_MODE)
                        except Exception as e:
                            print(f'Forbidden: bot is not a member of the channel chat, {user_id} tried to send to {user.channel_id}')
                            logger.error(f'Forbidden: bot is not a member of the channel chat, {user_id} tried to send to {user.channel_id}')
                    # update next_notification_ts so we'll not send again
                    user.tom_notification_ts = user.tom_schedule_ts
                    user.save_state()
                elif user.tom_schedule_ts < now_ts:
                    # outdated
                    user.tom_notification_ts = None
                    user.tom_schedule_ts     = None
                    user.save_state()
    except Exception as e:
        print(f"Exception in _send_notifications(): {traceback.format_exc()}")
        logger.error(f"Exception in _send_notifications(): {traceback.format_exc()}")
        return bot.send_message(chat_id=bot_secrets.ADMIN_ID, text=f"Exception in _send_notifications: {e}") 

def _gather_schedules():
    # Stop any existing job before starting a new one
    if 'yasno' in bos.shedulers.keys():
        scheduler.cancel_job(bos.shedulers['yasno'])
    # Schedule gathering job every 60 min
    bos.shedulers['yasno'] = scheduler.every(cfg.SCHEDULE_GATHER_SCHEDULE).minutes.do(bos.get_blackout_schedule)

def _notification_schedules():
    # Stop any existing job before starting a new one
    if 'set_notification' in bos.shedulers.keys():
        scheduler.cancel_job(bos.shedulers['set_notification'])
    # Schedule set_notification job every 30 min
    bos.shedulers['set_notification'] = scheduler.every(cfg.SCHEDULE_SET_NOTIFICATION).minutes.do(bos.set_notifications)
    if 'send_notification' in bos.shedulers.keys():
        scheduler.cancel_job(bos.shedulers['send_notification'])
    # Schedule send_notification job every min
    bos.shedulers['send_notification'] = scheduler.every(cfg.SCHEDULE_SEND_NOTIFICATION).minutes.do(_send_notifications)


def schedule_pings():
    while True:
        scheduler.run_pending()
        time.sleep(1)

def get_scheduled_jobs(update: Update, context: CallbackContext) -> None:
    chat_id = update.message.chat_id
    if str(chat_id) == bot_secrets.ADMIN_ID:
        jobs = scheduler.get_jobs()
        for job in range(len(jobs)):
            bot.send_message(chat_id=chat_id, text=str(jobs[job]))

def get_users(update: Update, context: CallbackContext) -> None:
    chat_id = update.message.chat_id
    if str(chat_id) == bot_secrets.ADMIN_ID:
        for user_id in us.user_settings.keys():
            user = us.User(user_id, us.user_settings[user_id]['chat_id'])
            bot.send_message(chat_id=chat_id, text=verbiages.get_full_info(user))

def get_user(update: Update, context: CallbackContext) -> None:
    global sys_commands
    chat_id = update.message.chat_id
    if str(chat_id) == bot_secrets.ADMIN_ID:
        sys_commands[chat_id] = {}
        sys_commands[chat_id]['ask_get_user'] = True
        update.message.reply_text('Введіть ІД користувача:')

def get_user_params(update: Update, context: CallbackContext) -> None:
    update.message.reply_text('Список параметрів:\nip_address(str)\nlistener(bool)\nlabel(str)\nchannel_id(str)\nto_bot(bool)\nto_channel(bool)\nhas_schedule(bool)\ncity(str)\ngroup(str)\nto_remind(bool)\nendpoint(str)\nheaders(json)\nlast_state(str:["alive"|"not reachable"])\nlast_ts(datetime UTC)\nlast_heared_ts(datetime UTC)\nnext_notification_ts(datetime Kyiv)\nnext_outage_ts(datetime Kyiv)\ntom_notification_ts(datetime Kyiv)\ntom_schedule_ts(datetime Kyiv)')

def set_user_param(update: Update, context: CallbackContext) -> None:
    global sys_commands
    chat_id = update.message.chat_id
    if str(chat_id) == bot_secrets.ADMIN_ID:
        sys_commands[chat_id] = {}
        sys_commands[chat_id]['ask_set_user_param'] = True
        update.message.reply_text('Введіть команду:')

# Up jobs if were saved
for user_id in us.user_settings.keys():
    chat_id = us.user_settings[user_id]['chat_id']
    user = us.User(user_id, chat_id)
    try:
        if user.ping_job:
            if user_id in us.user_jobs.keys():
                scheduler.cancel_job(us.user_jobs[user_id])
            us.user_jobs[user_id] = scheduler.every(cfg.SCHEDULE_PING).minutes.do(_ping, user_id=user_id, chat_id=chat_id)
        if user.listener:
            if user_id in us.listeners.keys():
                scheduler.cancel_job(us.listeners[user_id])
            us.listeners[user_id] = scheduler.every(cfg.SCHEDULE_LISTEN).minutes.do(_listen, user_id=user_id, chat_id=chat_id)
    except Exception as e:
        continue
_gather_schedules()
_notification_schedules()
bos.get_blackout_schedule()
bos.set_notifications()

# Register command handlers
dispatcher.add_handler(CommandHandler("start", start))
dispatcher.add_handler(CommandHandler("settings", settings))
dispatcher.add_handler(CommandHandler("mainmenu", main_menu))
dispatcher.add_handler(CommandHandler("go", go))
dispatcher.add_handler(CommandHandler("stop", stop))
dispatcher.add_handler(CommandHandler("check", ping_now))
dispatcher.add_handler(CommandHandler("ping", ping))
dispatcher.add_handler(CommandHandler("listen", listen))
dispatcher.add_handler(CommandHandler("setip", set_ip))
dispatcher.add_handler(CommandHandler("setlabel", set_label))
dispatcher.add_handler(CommandHandler("setchannel", set_channel))
dispatcher.add_handler(CommandHandler("yasnoschedule", yasno_schedule))
dispatcher.add_handler(CommandHandler("reminder", reminder))
dispatcher.add_handler(CommandHandler("posttobot", post_to_bot))
dispatcher.add_handler(CommandHandler("posttochannel", post_to_channel))
dispatcher.add_handler(CommandHandler("gettomschedule", get_tom_schedule))
dispatcher.add_handler(CommandHandler("getscheduledjobs", get_scheduled_jobs))
dispatcher.add_handler(CommandHandler("getusers", get_users))
dispatcher.add_handler(CommandHandler("getuser", get_user))
dispatcher.add_handler(CommandHandler("setuserparam", set_user_param))
dispatcher.add_handler(CommandHandler("getuserparams", get_user_params))

dispatcher.add_handler(MessageHandler(Filters.regex('^Старт моніторингу$'), lambda update, context: go(update, context)))
dispatcher.add_handler(MessageHandler(Filters.regex('^Отримати статус негайно$'), ping_now))
dispatcher.add_handler(MessageHandler(Filters.regex('^Налаштування$'), settings))
dispatcher.add_handler(MessageHandler(Filters.regex('^Головне меню$'), main_menu))
dispatcher.add_handler(MessageHandler(Filters.regex('^Зупинка моніторингу$'), stop))
dispatcher.add_handler(MessageHandler(Filters.regex('^Вказати IP$'), set_ip))
dispatcher.add_handler(MessageHandler(Filters.regex('^Вказати назву$'), set_label))
dispatcher.add_handler(MessageHandler(Filters.regex('^Вказати канал$'), set_channel))
dispatcher.add_handler(MessageHandler(Filters.regex('^Графік$'), yasno_schedule))
dispatcher.add_handler(MessageHandler(Filters.regex('^Нагадати$'), reminder))
dispatcher.add_handler(MessageHandler(Filters.regex('^-> в канал \(так/ні\)$'), lambda update, context: post_to_channel(update, context)))
dispatcher.add_handler(MessageHandler(Filters.regex('^-> в бот \(так/ні\)$'), lambda update, context: post_to_bot(update, context)))
dispatcher.add_handler(MessageHandler(Filters.regex('^Пінгувати \(так/ні\)$'), lambda update, context: ping(update, context)))
dispatcher.add_handler(MessageHandler(Filters.regex('^Слухати \(так/ні\)$'), lambda update, context: listen(update, context)))
dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_input))

# Start the scheduler thread
scheduler_thread = threading.Thread(target=schedule_pings)
scheduler_thread.start()

# Flask endpoint to send message
@app.route('/send', methods=['GET'])
def send():
    sender = request.args.get('chat_id')
    #caller_ip = request.remote_addr
    if not sender:
        return jsonify({"error": "chat_id is required"}), 400
    try:
        _heard(sender)
        return jsonify({"status": "Message sent successfully"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
if __name__ == '__main__':
    # Start the Telegram bot
    updater.start_polling()
    #updater.idle()

    # Run the Flask app
    app.run(host='0.0.0.0', port=5000)    