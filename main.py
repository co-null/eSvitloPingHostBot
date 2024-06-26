import bot_secrets, config as cfg, user_settings as us, utils, verbiages, actions, blackout_schedule as bos
from telegram.ext import Updater, CommandHandler, CallbackContext, MessageHandler, Filters
from telegram import Update, Bot, ReplyKeyboardMarkup, KeyboardButton, constants
from telegram.utils.request import Request as TRequest
import logging
import schedule
import time
import threading
from datetime import datetime
from flask import Flask, request, jsonify
import pytz

# Create a logger
logger = logging.getLogger('mylogger')
logger.setLevel(logging.DEBUG)

# Create a file handler
fh = logging.FileHandler('errors.log')
fh.setLevel(logging.DEBUG)

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

def reply_md(message:str, update: Update, reply_markup = None) -> None:
    message = utils.get_text_safe_to_markdown(message)
    update.message.reply_text(message, reply_markup=reply_markup, parse_mode=PARSE_MODE)

def start(update: Update, context: CallbackContext) -> None:
    user_id = str(update.message.from_user.id)
    chat_id = update.message.chat_id
    user    = us.User(user_id, chat_id)
    if user.new :
        reply_md(cfg.msg_greeting, update)
    else:
        # Recreate the jobs if saved previously
        if user.ping_job:
            us.user_jobs[user_id] = schedule.every(cfg.SCHEDULE_PING).minutes.do(_ping, user_id=user_id, chat_id=chat_id)
        if user.listener:
            us.listeners[user_id] = schedule.every(cfg.SCHEDULE_LISTEN).minutes.do(_listen, user_id=user_id, chat_id=chat_id)
        if user.has_schedule:
            _gather_schedules()
            _notification_schedules()
        reply_md(cfg.msg_comeback, update, reply_markup=main_menu_markup)
    bos.get_blackout_schedule()
    bos.set_notifications()

def settings(update: Update, context: CallbackContext) -> None:
    user_id = str(update.message.from_user.id)
    if user_id not in us.user_settings.keys():
        reply_md(cfg.msg_error, update)
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
    if user_id not in us.user_settings.keys():
        reply_md(cfg.msg_error, update)
        return
    user = us.User(user_id, chat_id)
    user.toggle_awaiting_ip()
    user.save()
    update.message.reply_text(cfg.msg_setip)

def set_label(update: Update, context: CallbackContext) -> None:
    user_id = str(update.message.from_user.id)
    chat_id = update.message.chat_id
    if user_id not in us.user_settings.keys():
        reply_md(cfg.msg_error, update)
        return
    user = us.User(user_id, chat_id)
    user.toggle_awaiting_label()
    user.save()
    update.message.reply_text(cfg.msg_setlabel)

def set_channel(update: Update, context: CallbackContext) -> None:
    user_id = str(update.message.from_user.id)
    chat_id = update.message.chat_id
    if user_id not in us.user_settings.keys():
        reply_md(cfg.msg_error, update)
        return
    user = us.User(user_id, chat_id)
    user.toggle_awaiting_channel()
    user.save()
    update.message.reply_text(cfg.msg_setchannel)

def yasno_schedule(update: Update, context: CallbackContext) -> None:
    user_id = str(update.message.from_user.id)
    chat_id = update.message.chat_id
    if user_id not in us.user_settings.keys():
        reply_md(cfg.msg_error, update)
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
    if user_id not in us.user_settings.keys():
        reply_md(cfg.msg_error, update)
        return
    user = us.User(user_id, chat_id)
    msg = verbiages.get_notificatiom_tomorrow_schedule(bos.get_windows_for_tomorrow(user))
    reply_md(msg, update)


def reminder(update: Update, context: CallbackContext) -> None:
    user_id = str(update.message.from_user.id)
    chat_id = update.message.chat_id
    if user_id not in us.user_settings.keys():
        reply_md(cfg.msg_error, update)
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
    try:
        user_id = str(update.message.from_user.id)
        chat_id = update.message.chat_id
    except Exception as e:
        return
    
    if user_id not in us.user_settings.keys():
        reply_md(cfg.msg_error, update)
        return
    user = us.User(user_id, chat_id)
    if user.awaiting_ip:
        user.toggle_nowait()
        if update.message.text[:15] == '-' and user.ip_address:
            update.message.reply_text('ІР адресу видалено')
            user.ip_address = None
            user.save()
            return 
        elif update.message.text[:15] == '-' and not user.ip_address:
            update.message.reply_text('Скасовано')
            user.save()
            return
        else:
            user.ip_address = update.message.text[:15]
        if not user.label or user.label == '':
            user.toggle_awaiting_label()
            update.message.reply_text(f'Вказано IP адресу {user.ip_address}. Тепер вкажіть, будь-ласка, назву:')
        else:
            reply_md(f'Вказано IP адресу {user.ip_address}', update)
    elif user.awaiting_label:
        user.toggle_nowait()
        if update.message.text[:255] == '-' and user.label:
            update.message.reply_text('Назву видалено')
            user.label = None
            user.save()
            return 
        elif update.message.text[:255] == '-' and not user.label:
            update.message.reply_text('Скасовано')
            user.save()
            return
        else:
            user.label = update.message.text[:255]
            update.message.reply_text(f'Назву оновлено на {user.label}. Тепер можна активізувати моніторинг (пінг)')
    elif user.awaiting_channel:
         user.toggle_nowait()
         if update.message.text[:255] == '-' and user.channel_id:
            update.message.reply_text('Канал видалено')
            user.channel_id = None
            user.save()
            return 
         elif update.message.text[:255] == '-' and not user.channel_id:
            update.message.reply_text('Скасовано')
            user.save()
            return
         else:
            channel_id = update.message.text[:255]
            if channel_id.startswith('https://t.me/'): channel_id = channel_id.replace('https://t.me/', '')
            if not channel_id.startswith('@'): channel_id = '@' + channel_id
            user.channel_id = channel_id
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
            update.message.reply_text(f'Вказано {user.city}: Група {user.group}')
            _gather_schedules()
    else: return
    user.save()
    #update.message.reply_text(verbiages.get_settings(user_id), reply_markup=settings_menu_markup)

def _start_ping(user: us.User) -> None:
    # Stop any existing job before starting a new one
    if user.user_id in us.user_jobs.keys():
        schedule.cancel_job(us.user_jobs[user.user_id])
    # Schedule the ping job every min
    us.user_jobs[user.user_id] = schedule.every(cfg.SCHEDULE_PING).minutes.do(_ping, user_id=user.user_id, chat_id=user.chat_id)
    user.ping_job = 'scheduled'
    user.save()
    # Initial ping immediately
    _ping(user.user_id, user.chat_id)

def _stop_ping(user: us.User) -> None:
    if user.user_id in us.user_jobs.keys():
        schedule.cancel_job(us.user_jobs[user.user_id])
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
        if not user.ip_address:
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
    # Stop any existing job before starting a new one
    if user.user_id in us.listeners.keys():
        schedule.cancel_job(us.listeners[user.user_id])
    # Schedule the listen job every 5 min
    us.listeners[user.user_id] = schedule.every(cfg.SCHEDULE_LISTEN).minutes.do(_listen, user_id=user.user_id, chat_id=user.chat_id)
    user.listener = True
    user.save()
    # Initial check immediately
    _listen(user.user_id, user.chat_id)

def _stop_listen(user: us.User):
    if user.user_id in us.listeners.keys():
        schedule.cancel_job(us.listeners[user.user_id])
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
    user   = us.User(user_id, chat_id)
    try:
        result = actions._ping_ip(user, False)
        msg    = utils.get_text_safe_to_markdown(result.message)
        if msg and user.to_bot: 
            try:
                bot.send_message(chat_id=user.chat_id, text=msg, parse_mode=PARSE_MODE)
            except Exception as e:
                #logger.error(f'Forbidden: bot is not a member of the channel chat, {user_id} tried to send to {user.chat_id}')
                print(f'Forbidden: bot is not a member of the channel chat, {user_id} tried to send to {user.chat_id}')
        if msg and user.to_channel and user.channel_id:
            try:
                bot.send_message(chat_id=user.channel_id, text=msg, parse_mode=PARSE_MODE)
            except Exception as e:
                #logger.error(f'Forbidden: bot is not a member of the channel chat, {user_id} tried to send to {user.channel_id}')
                print(f'Forbidden: bot is not a member of the channel chat, {user_id} tried to send to {user.channel_id}')
        user.save_state()
    except Exception as e:
        print(f"Exception in _ping\({user_id}, {chat_id}\): {e}")
        return bot.send_message(chat_id=bot_secrets.ADMIN_ID, text=f"Exception in _ping\({user_id}, {chat_id}\): {e}", parse_mode=PARSE_MODE)

def ping_now(update: Update, context: CallbackContext) -> None:
    user_id = str(update.message.from_user.id)
    chat_id = update.message.chat_id
    if user_id not in us.user_settings.keys():
        reply_md(cfg.msg_error, update)
        return
    user = us.User(user_id, chat_id)
    if not user.ip_address and not user.listener:
        reply_md(cfg.msg_noip, update)
        return
    if user.ip_address:
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
        user.save_state()
        if changed and msg and user.to_bot: 
            try:
                bot.send_message(chat_id=user.chat_id, text=msg, parse_mode=PARSE_MODE)
            except Exception as e:
                #logger.error(f'Forbidden: bot is not a member of the channel chat, {user_id} tried to send to {user.chat_id}')
                print(f'Forbidden: bot is not a member of the channel chat, {user_id} tried to send to {user.chat_id}')
        if changed and msg and user.to_channel and user.channel_id:
            try:
                bot.send_message(chat_id=user.channel_id, text=msg, parse_mode=PARSE_MODE)
            except Exception as e:
                #logger.error(f'Forbidden: bot is not a member of the channel chat, {user_id} tried to send to {user.channel_id}')
                print(f'Forbidden: bot is not a member of the channel chat, {user_id} tried to send to {user.channel_id}')
    except Exception as e:
        print(f"Exception in _listen({user_id}, {chat_id}): {e}")
        return bot.send_message(chat_id=bot_secrets.ADMIN_ID, text=f"Exception in _listen({user_id}, {chat_id}): {e}", parse_mode=PARSE_MODE)

def _send_notifications():
    #print("Start send notifications job")
    try:
        # here all timestamp are in Kyiv TZ
        use_tz = pytz.timezone(cfg.TZ)
        now_ts0 = datetime.now(use_tz)
        # make tz-naive
        now_ts = datetime.strptime((now_ts0.strftime('%Y-%m-%d %H:%M:%S')), '%Y-%m-%d %H:%M:%S')
        for user_id in us.user_settings.keys():
            chat_id = us.user_settings[user_id]['chat_id']
            user    = us.User(user_id, chat_id)
            if user.has_schedule and user.to_remind and user.next_notification_ts and user.next_outage_ts:
                if user.next_notification_ts < now_ts and user.next_outage_ts > now_ts and user.last_state == cfg.ALIVE:
                    # will send
                    msg = verbiages.get_notification_message_long(bos.get_next_outage_window(user))
                    if msg and user.to_bot: 
                        try:
                            bot.send_message(chat_id=user.chat_id, text=msg, parse_mode=PARSE_MODE)
                        except Exception as e:
                            print(f'Forbidden: bot is not a member of the channel chat, {user_id} tried to send to {user.chat_id}')
                    if msg and user.to_channel and user.channel_id:
                        try:
                            bot.send_message(chat_id=user.channel_id, text=msg, parse_mode=PARSE_MODE)
                        except Exception as e:
                            print(f'Forbidden: bot is not a member of the channel chat, {user_id} tried to send to {user.channel_id}')
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
                    if msg and user.to_channel and user.channel_id:
                        try:
                            bot.send_message(chat_id=user.channel_id, text=msg, parse_mode=PARSE_MODE)
                        except Exception as e:
                            print(f'Forbidden: bot is not a member of the channel chat, {user_id} tried to send to {user.channel_id}')
                    # update next_notification_ts so we'll not send again
                    user.tom_notification_ts = user.tom_schedule_ts
                    user.save_state()
                elif user.tom_schedule_ts < now_ts:
                    # outdated
                    user.tom_notification_ts = None
                    user.tom_schedule_ts     = None
                    user.save_state()
    except Exception as e:
        print(f"Exception in _send_notifications(): {e}")
        return bot.send_message(chat_id=bot_secrets.ADMIN_ID, text=f"Exception in _send_notifications: {e}", parse_mode=PARSE_MODE) 

def _gather_schedules():
    # Stop any existing job before starting a new one
    if 'yasno' in bos.shedulers.keys():
        schedule.cancel_job(bos.shedulers['yasno'])
    # Schedule gathering job every 60 min
    bos.shedulers['yasno'] = schedule.every(cfg.SCHEDULE_GATHER_SCHEDULE).minutes.do(bos.get_blackout_schedule)

def _notification_schedules():
    # Stop any existing job before starting a new one
    if 'set_notification' in bos.shedulers.keys():
        schedule.cancel_job(bos.shedulers['set_notification'])
    # Schedule set_notification job every 30 min
    bos.shedulers['set_notification'] = schedule.every(cfg.SCHEDULE_SET_NOTIFICATION).minutes.do(bos.set_notifications)
    if 'send_notification' in bos.shedulers.keys():
        schedule.cancel_job(bos.shedulers['send_notification'])
    # Schedule send_notification job every min
    bos.shedulers['send_notification'] = schedule.every(cfg.SCHEDULE_SEND_NOTIFICATION).minutes.do(_send_notifications)

def schedule_pings():
    while True:
        schedule.run_pending()
        time.sleep(1)

# Up jobs if were saved
for user_id in us.user_settings.keys():
    chat_id = us.user_settings[user_id]['chat_id']
    user = us.User(user_id, chat_id)
    try:
        if user.ping_job:
            if user_id in us.user_jobs.keys():
                schedule.cancel_job(us.user_jobs[user_id])
            us.user_jobs[user_id] = schedule.every(cfg.SCHEDULE_PING).minutes.do(_ping, user_id=user_id, chat_id=chat_id)
        if user.listener:
            if user_id in us.listeners.keys():
                schedule.cancel_job(us.listeners[user_id])
            us.listeners[user_id] = schedule.every(cfg.SCHEDULE_LISTEN).minutes.do(_listen, user_id=user_id, chat_id=chat_id)
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