import bot_secrets
import config as cfg
import user_settings as us
import os
import subprocess
from telegram.ext import Updater, CommandHandler, CallbackContext, Dispatcher, MessageHandler, Filters
from telegram import Update, Bot, ReplyKeyboardMarkup, KeyboardButton
from telegram.utils.request import Request as TRequest
import schedule
import time
import threading
from datetime import date, datetime, timedelta
import fcntl
from flask import Flask, request, jsonify

# Initialize Flask app
app = Flask(__name__)

# Initialize the bot
bot_request = TRequest(con_pool_size=8)
bot         = Bot(token=bot_secrets.BOT_TOKEN, request=bot_request)

# Telegram bot initialization
updater    = Updater(bot=bot, use_context=True)
dispatcher = updater.dispatcher

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
                           KeyboardButton('Слухати (так/ні)')],
                          [KeyboardButton('Головне меню')]]

main_menu_markup     = ReplyKeyboardMarkup(main_menu_keyboard, resize_keyboard=True)
settings_menu_markup = ReplyKeyboardMarkup(settings_menu_keyboard, resize_keyboard=True)

def check_ip(ip: str) -> bool:
    cmd = "ping -c 1 " + ip
    status = subprocess.getstatusoutput(cmd)
    return status[0]==0

def get_string_period(delta_sec: int) -> str:
    hours    = int(delta_sec/3600)
    minutes  = int((delta_sec - 3600*hours)/60)

    if hours > 0 and hours < 48: 
        hour_str = f"{hours} год."
    elif hours >= 48:
        hour_str = "більше 48 год."
    else: hour_str = ''
    if minutes > 0 and hours < 48:
        min_str = f" {minutes} хв."
    else: min_str  = ''
    if hours == 0 and minutes < 1:
        return "менше хвилини"
    elif hours == 0 and minutes > 0:
        return min_str
    else: return hour_str + " " + min_str

def start(update: Update, context: CallbackContext) -> None:
    user_id = str(update.message.from_user.id)
    chat_id = update.message.chat_id
    if user_id not in us.user_settings.keys():
        us.init_user(user_id, chat_id)
        us.save_user_settings()
        update.message.reply_text(cfg.msg_greeting, reply_markup=main_menu_markup)
    else:
        us.reinit_user(user_id, chat_id)
        # Recreate the jobs if saved previously
        if us.user_settings[user_id]['ping_job']:
            us.user_jobs[user_id] = schedule.every(1).minutes.do(_ping, user_id=user_id, chat_id=chat_id)
        if us.user_settings[user_id]['listener']:
            us.listeners[user_id] = schedule.every(5).minutes.do(_listen, user_id=user_id, chat_id=chat_id)
        update.message.reply_text(cfg.msg_comeback, reply_markup=main_menu_markup)

def _settings(user_id: str) -> str:
    user = us.user_settings[user_id]
    msg  = cfg.msg_settings + '\n'
    if user['ip_address']: msg += "IP адреса: " + user['ip_address'] + f" ({user['label']}) \n" 
    else: msg += "IP адреса не вказана \n"
    if user['ping_job']: msg += cfg.msg_ippingon 
    else: msg += cfg.msg_ippingoff
    if user['listener']: msg += cfg.msg_listeneron
    else: msg += cfg.msg_listeneroff 
    if user['channel_id']: msg += "Канал: " + user['channel_id'] + "\n" 
    if user['to_bot']: msg += cfg.msg_boton
    else: msg += cfg.msg_botoff
    if user['to_channel']: msg += cfg.msg_channelon
    else: msg += cfg.msg_channeloff
    return msg

def settings(update: Update, context: CallbackContext) -> None:
    user_id = str(update.message.from_user.id)
    if user_id not in us.user_settings.keys():
        update.message.reply_text(cfg.msg_error)
        return
    update.message.reply_text(_settings(user_id) + "\n" + f"Для налаштування слухача робіть виклики на {cfg.LISTENER_URL}{user_id}", 
                              reply_markup=settings_menu_markup)

def main_menu(update: Update, context: CallbackContext) -> None:
    update.message.reply_text(cfg.msg_mainmnu, reply_markup=main_menu_markup)

def set_ip(update: Update, context: CallbackContext) -> None:
    user_id = str(update.message.from_user.id)
    if user_id not in us.user_settings.keys():
        update.message.reply_text(cfg.msg_error)
        return
    us.user_settings[user_id]['awaiting_ip']      = True
    us.user_settings[user_id]['awaiting_label']   = False
    us.user_settings[user_id]['awaiting_channel'] = False
    update.message.reply_text(cfg.msg_setip, reply_markup=settings_menu_markup)

def set_label(update: Update, context: CallbackContext) -> None:
    user_id = str(update.message.from_user.id)
    if user_id not in us.user_settings.keys():
        update.message.reply_text(cfg.msg_error)
    us.user_settings[user_id]['awaiting_ip']      = False
    us.user_settings[user_id]['awaiting_label']   = True
    us.user_settings[user_id]['awaiting_channel'] = False
    update.message.reply_text(cfg.msg_setlabel, reply_markup=settings_menu_markup)

def set_channel(update: Update, context: CallbackContext) -> None:
    user_id = str(update.message.from_user.id)
    if user_id not in us.user_settings.keys():
        update.message.reply_text(cfg.msg_error)
    us.user_settings[user_id]['awaiting_ip']      = False
    us.user_settings[user_id]['awaiting_label']   = False
    us.user_settings[user_id]['awaiting_channel'] = True
    update.message.reply_text(cfg.msg_setchannel, reply_markup=settings_menu_markup)

def handle_input(update: Update, context: CallbackContext) -> None:
    try:
        user_id = str(update.message.from_user.id)
    except Exception as e:
        return
    
    if user_id not in us.user_settings.keys():
        update.message.reply_text(cfg.msg_error)
        return
    
    if us.user_settings[user_id]['awaiting_ip']:
        us.user_settings[user_id]['ip_address'] = update.message.text[:15]
        us.user_settings[user_id]['awaiting_ip']      = False
        us.user_settings[user_id]['awaiting_channel'] = False
        if not us.user_settings[user_id]['label'] != '':
            us.user_settings[user_id]['awaiting_label'] = True
            update.message.reply_text(f'Вказано IP адресу {update.message.text}. Тепер вкажіть, будь-ласка, назву:')
        else:
            update.message.reply_text(f'Вказано IP адресу {update.message.text}')

    elif us.user_settings[user_id]['awaiting_label']:
        us.user_settings[user_id]['label'] = update.message.text[:255]
        us.user_settings[user_id]['awaiting_ip']      = False
        us.user_settings[user_id]['awaiting_label']   = False
        us.user_settings[user_id]['awaiting_channel'] = False
        update.message.reply_text(f'Назву оновлено на {update.message.text}. Тепер можна активізувати моніторинг (пінг)')
        
    elif us.user_settings[user_id]['awaiting_channel']:
        channel_id = update.message.text[:255]
        if channel_id.startswith('https://t.me/'): channel_id.replace('https://t.me/', '')
        if not channel_id.startswith('@'): channel_id = '@' + channel_id
        us.user_settings[user_id]['channel_id'] = channel_id
        us.user_settings[user_id]['awaiting_channel'] = False
        us.user_settings[user_id]['awaiting_ip']      = False
        us.user_settings[user_id]['awaiting_label']   = False
        update.message.reply_text(f'Налаштовано публікацію в канал {update.message.text}')
    us.save_user_settings()
    update.message.reply_text(_settings(user_id), reply_markup=settings_menu_markup)

def _start_ping(user_id: str, chat_id: str) -> None:
    # Stop any existing job before starting a new one
    if user_id in us.user_jobs.keys():
        schedule.cancel_job(us.user_jobs[user_id])
    # Schedule the ping job every min
    us.user_jobs[user_id] = schedule.every(1).minutes.do(_ping, user_id=user_id, chat_id=chat_id)
    us.user_settings[user_id]['ping_job'] = 'scheduled'
    # Initial ping immediately
    _ping(user_id, chat_id)

def _stop_ping(user_id: str) -> None:
    if user_id in us.user_jobs.keys():
        schedule.cancel_job(us.user_jobs[user_id])
    us.user_settings[user_id]['ping_job'] = None

def ping(update: Update, context: CallbackContext) -> None:
    user_id = str(update.message.from_user.id)
    chat_id = update.message.chat_id
    if user_id not in us.user_settings.keys():
        update.message.reply_text(cfg.msg_error)
        return
    if not us.user_settings[user_id]['ping_job'] == 'scheduled':
        # If need to turn on
        if not us.user_settings[user_id]['ip_address']:
            update.message.reply_text(cfg.msg_noip)
            return
        _start_ping(user_id, chat_id)
        label = us.user_settings[user_id]['label']
        msg = f'Тепер бот перевірятиме доступність {label} і повідомлятиме про зміну статусу'
    else:
        # If need to turn off
        if user_id in us.user_jobs.keys():
            msg = cfg.msg_stopped
        else:
            msg = cfg.msg_notset
        _stop_ping(user_id)
    us.save_user_settings()
    update.message.reply_text(msg + "\n" + _settings(user_id))

def _start_listen(user_id: str, chat_id: str):
    # Stop any existing job before starting a new one
    if user_id in us.listeners.keys():
        schedule.cancel_job(us.listeners[user_id])
    # Schedule the listen job every 5 min
    us.listeners[user_id] = schedule.every(5).minutes.do(_listen, user_id=user_id, chat_id=chat_id)
    us.user_settings[user_id]['listener'] = True
    # Initial check immediately
    _listen(user_id, chat_id)

def _stop_listen(user_id: str):
    if user_id in us.listeners.keys():
        schedule.cancel_job(us.listeners[user_id])
    us.user_settings[user_id]['listener'] = False

def listen(update: Update, context: CallbackContext) -> None:
    user_id = str(update.message.from_user.id)
    chat_id = update.message.chat_id
    if user_id not in us.user_settings.keys():
        update.message.reply_text(cfg.msg_error)
        return
    if not us.user_settings[user_id]['listener']:
        # If need to turn on
        _start_listen(user_id, chat_id)
        label = us.user_settings[user_id]['label']
        msg = f'Тепер бот слухатиме {label} і повідомлятиме про зміну статусу, якщо повідомлення припиняться більше, ніж на 5 хв.'
    else:
        # If need to turn off
        _stop_listen(user_id)
        msg = cfg.msg_listeneroff
    us.save_user_settings()
    update.message.reply_text(msg + "\n" + _settings(user_id))

def go(update: Update, context: CallbackContext) -> None:
    user_id = str(update.message.from_user.id)
    if user_id not in us.user_settings.keys():
        update.message.reply_text(cfg.msg_error)
        return
    if not us.user_settings[user_id]['ping_job'] == 'scheduled':
        update.message.reply_text(cfg.msg_ippingondetailed)
        ping(update, context)

    #if not us.user_settings[user_id]['listener']:
    #    listen(update, context)

def stop(update: Update, context: CallbackContext) -> None:
    user_id = str(update.message.from_user.id)
    if user_id not in us.user_settings.keys():
        update.message.reply_text(cfg.msg_error)
        return
    if us.user_settings[user_id]['ping_job'] == 'scheduled':
        ping(update, context)

    if us.user_settings[user_id]['listener']:
        listen(update, context)

def post_to_bot(update: Update, context: CallbackContext) -> None:
    user_id = str(update.message.from_user.id)
    if user_id not in us.user_settings.keys():
        update.message.reply_text(cfg.msg_error)
        return
    if not us.user_settings[user_id]['to_bot']:
        #Turn on:
        us.user_settings[user_id]['to_bot'] = True
        msg = cfg.msg_postbot
    else:
        #Turn off:
        us.user_settings[user_id]['to_bot'] = False
        msg = cfg.msg_nopostbot
    us.save_user_settings()
    update.message.reply_text(msg + "\n" + _settings(user_id), reply_markup=settings_menu_markup)

def post_to_channel(update: Update, context: CallbackContext) -> None:
    user_id = str(update.message.from_user.id)
    if user_id not in us.user_settings.keys():
        update.message.reply_text(cfg.msg_error)
        return
    if not us.user_settings[user_id]['to_channel']:
        if us.user_settings[user_id]['channel_id']: 
            # turn on
            us.user_settings[user_id]['to_channel'] = True
            msg = cfg.msg_postchannel
        else:
            us.user_settings[user_id]['to_channel'] = False
            msg = cfg.msg_nochannel
    else:
        # turn off
        us.user_settings[user_id]['to_channel'] = False
        msg = cfg.msg_nopostchannel
    us.save_user_settings()
    update.message.reply_text(msg + "\n" + _settings(user_id), reply_markup=settings_menu_markup)

def _state_msg(user_id: str, status: str, last_state: str, last_ts: datetime, immediately: bool = False) -> str:
    label = us.user_settings[user_id]['label']
    now_ts_short = datetime.now().strftime('%H:%M')
    msg = ""
    if last_state:
        if datetime.now().day == last_ts.day: 
            day_label = last_ts.strftime('%H:%M')
        else: 
            day_label = last_ts.strftime('%d.%m.%Y %H:%M')
    else: day_label = now_ts_short
    # if last_state is not set
    if not last_state:
        last_state = status
        last_ts    = datetime.now()
        us.user_states[user_id]['last_state'] = status
        us.user_states[user_id]['last_ts']    = last_ts.strftime('%Y-%m-%d %H:%M:%S')
        if label and label != '':
            msg = f"{label} тепер моніториться на наявність електрохарчування"
        else:
            msg = "Моніториться на наявність електрохарчування"
    # turned on
    elif last_state != status and last_state == cfg.OFF:
        delta = datetime.now() - last_ts
        msg = f"Електрика в {label} з'явилася о {now_ts_short}!\n" + "Світла не було " + get_string_period(delta.seconds) + f", з {day_label}"
        last_state = status
        last_ts    = datetime.now()
        us.user_states[user_id]['last_state'] = status
        us.user_states[user_id]['last_ts']    = last_ts.strftime('%Y-%m-%d %H:%M:%S')
    # turned off
    elif last_state != status and last_state == cfg.ALIVE:
        delta = datetime.now() - last_ts
        msg = f"Електрику в {label} вимкнули о {now_ts_short} :(\n" + "Світло було " + get_string_period(delta.seconds) + f", з {day_label}"
        last_state = status
        last_ts    = datetime.now()
        us.user_states[user_id]['last_state'] = status
        us.user_states[user_id]['last_ts']    = last_ts.strftime('%Y-%m-%d %H:%M:%S')
    # same
    elif cfg.isPostOK == 'T' or immediately:
        delta = datetime.now() - last_ts
        msg = cfg.msg_alive
        if status == cfg.ALIVE:
            msg = msg + "\n" + "Світло є вже " + get_string_period(delta.seconds) + f", з {day_label}"
        else:
            msg = msg + "\n" + "Світла немає вже " + get_string_period(delta.seconds) + f", з {day_label}"
    us.save_user_states()
    return msg

def _ping_ip(user_id: str, immediately: bool = False) -> str:
    if user_id not in us.user_settings.keys():
        return
    if user_id not in us.user_states.keys():
        us.init_states(user_id)

    ip_address = us.user_settings[user_id]['ip_address']
    last_state = us.user_states[user_id]['last_state']
    if us.user_states[user_id]['last_ts']:
        last_ts = datetime.strptime(us.user_states[user_id]['last_ts'], '%Y-%m-%d %H:%M:%S')
    else: last_ts = None
    if ip_address:
        status = cfg.ALIVE if check_ip(ip_address) else cfg.OFF
        return _state_msg(user_id, status, last_state, last_ts, immediately)
    else: return

def _ping(user_id, chat_id):
    if user_id not in us.user_settings.keys():
        return
    if user_id not in us.user_states.keys():
        us.init_states(user_id)

    channel_id = us.user_settings[user_id]['channel_id']
    to_bot     = us.user_settings[user_id]['to_bot']
    to_channel = us.user_settings[user_id]['to_channel']

    msg = _ping_ip(user_id, False)
    if msg and to_bot: 
        bot.send_message(chat_id=chat_id, text=msg)
    if msg and to_channel and channel_id:
        bot.send_message(chat_id=channel_id, text=msg)

def ping_now(update: Update, context: CallbackContext) -> None:
    user_id = str(update.message.from_user.id)
    chat_id = update.message.chat_id
    if user_id not in us.user_settings.keys():
        update.message.reply_text(cfg.msg_error)
        return
    if not us.user_settings[user_id]['ip_address']:
        update.message.reply_text(cfg.msg_noip)
        return
    msg = _ping_ip(user_id, True)
    update.message.reply_text(msg, reply_markup=main_menu_markup)

def _heard(user_id: str) -> None:
    msg = None
    if user_id not in us.user_settings.keys():
        return
    try:
        last_state = us.user_states[user_id]['last_state']
        if us.user_states[user_id]['last_ts']:
            last_ts = datetime.strptime(us.user_states[user_id]['last_ts'], '%Y-%m-%d %H:%M:%S')
        else: last_ts = None
        if us.user_states[user_id]['last_heared_ts']:
            last_heared_ts = datetime.strptime(us.user_states[user_id]['last_heared_ts'], '%Y-%m-%d %H:%M:%S')
        else: last_heared_ts = None
    except Exception as e:
        us.reinit_states(user_id)
        last_state = us.user_states[user_id]['last_state']
        if us.user_states[user_id]['last_ts']:
            last_ts = datetime.strptime(us.user_states[user_id]['last_ts'], '%Y-%m-%d %H:%M:%S')
        else: last_ts = None
        if us.user_states[user_id]['last_heared_ts']:
            last_heared_ts = datetime.strptime(us.user_states[user_id]['last_heared_ts'], '%Y-%m-%d %H:%M:%S')
        else: last_heared_ts = None
    label = us.user_settings[user_id]['label']
    if label and label != '': label = 'в ' + label
    channel_id = us.user_settings[user_id]['channel_id']
    to_bot     = us.user_settings[user_id]['to_bot']
    to_channel = us.user_settings[user_id]['to_channel']
    chat_id    = us.user_settings[user_id]['chat_id']
    # if last_state is not set
    if not last_state:
        status = cfg.ALIVE
    # turned on
    elif last_state == cfg.OFF:
        status = cfg.ALIVE
    msg = _state_msg(user_id, status, last_state, last_ts, False)
    us.user_states[user_id]['last_heared_ts'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    us.save_user_states()
    if msg and to_bot: 
        bot.send_message(chat_id=chat_id, text=msg)
    if msg and to_channel and channel_id:
        bot.send_message(chat_id=channel_id, text=msg)

def _listen(user_id, chat_id):
    if user_id not in us.user_settings.keys():
        return
    if user_id not in us.user_states.keys():
        us.init_states(user_id)
    if not us.user_settings[user_id]['listener']: 
        # was turned off somehow
        return
    try:
        last_state = us.user_states[user_id]['last_state']
        if us.user_states[user_id]['last_ts']:
            last_ts = datetime.strptime(us.user_states[user_id]['last_ts'], '%Y-%m-%d %H:%M:%S')
        else: last_ts = None
        if us.user_states[user_id]['last_heared_ts']:
            last_heared_ts = datetime.strptime(us.user_states[user_id]['last_heared_ts'], '%Y-%m-%d %H:%M:%S')
        else: last_heared_ts = None
    except Exception as e:
        us.reinit_states(user_id)
        last_state = us.user_states[user_id]['last_state']
        if us.user_states[user_id]['last_ts']:
            last_ts = datetime.strptime(us.user_states[user_id]['last_ts'], '%Y-%m-%d %H:%M:%S')
        else: last_ts = None
        if us.user_states[user_id]['last_heared_ts']:
            last_heared_ts = datetime.strptime(us.user_states[user_id]['last_heared_ts'], '%Y-%m-%d %H:%M:%S')
        else: last_heared_ts = None

    # Do not spam if newer worked
    if not last_state or not last_ts or not last_heared_ts: 
        return
    delta = datetime.now() - last_heared_ts
    # If >300 sec (5 mins) and was turned on - consider blackout
    if delta.seconds > 300 and last_state == cfg.ALIVE:
        status = cfg.OFF
    elif last_state == cfg.ALIVE:
        # still enabled
        status = cfg.ALIVE
    elif delta.seconds <= 300 and last_state == cfg.OFF:
        # turned on, maybe missed
        status = cfg.ALIVE
    else:    
        # still turned off
        status = cfg.OFF
    msg = _state_msg(user_id, status, last_state, last_ts, False)
    channel_id = us.user_settings[user_id]['channel_id']
    to_bot     = us.user_settings[user_id]['to_bot']
    to_channel = us.user_settings[user_id]['to_channel']

    if msg and to_bot: 
        bot.send_message(chat_id=chat_id, text=msg)
    if msg and to_channel and channel_id:
        bot.send_message(chat_id=channel_id, text=msg)

def schedule_pings():
    while True:
        schedule.run_pending()
        time.sleep(1)

pid_file = 'bot.pid'
fp = open(pid_file, 'w')
try:
    fcntl.lockf(fp, fcntl.LOCK_EX | fcntl.LOCK_NB)
except IOError:
    # another instance is running
    os.sys.exit(1)

# Up jobs if were saved
for user_id in us.user_settings.keys():
    try:
        if us.user_settings[user_id]['ping_job']:
            if user_id in us.user_jobs.keys():
                schedule.cancel_job(us.user_jobs[user_id])
            us.user_jobs[user_id] = schedule.every(1).minutes.do(_ping, user_id=user_id, chat_id=us.user_settings[user_id]['chat_id'])
        if us.user_settings[user_id]['listener']:
            if user_id in us.listeners.keys():
                schedule.cancel_job(us.listeners[user_id])
            us.listeners[user_id] = schedule.every(5).minutes.do(_listen, user_id=user_id, chat_id=us.user_settings[user_id]['chat_id'])
    except Exception as e:
        continue

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
dispatcher.add_handler(CommandHandler("posttobot", post_to_bot))
dispatcher.add_handler(CommandHandler("posttochannel", post_to_channel))

dispatcher.add_handler(MessageHandler(Filters.regex('^Старт моніторингу$'), lambda update, context: go(update, context)))
dispatcher.add_handler(MessageHandler(Filters.regex('^Отримати статус негайно$'), ping_now))
dispatcher.add_handler(MessageHandler(Filters.regex('^Налаштування$'), settings))
dispatcher.add_handler(MessageHandler(Filters.regex('^Головне меню$'), main_menu))
dispatcher.add_handler(MessageHandler(Filters.regex('^Зупинка моніторингу$'), stop))
dispatcher.add_handler(MessageHandler(Filters.regex('^Вказати IP$'), set_ip))
dispatcher.add_handler(MessageHandler(Filters.regex('^Вказати назву$'), set_label))
dispatcher.add_handler(MessageHandler(Filters.regex('^Вказати канал$'), set_channel))
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
    