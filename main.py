import config as cfg
from config import BOT_TOKEN
import user_settings as us
import os
import subprocess
from telegram.ext import Updater, CommandHandler, CallbackContext, Dispatcher, MessageHandler, Filters
from telegram import Update, Bot, ReplyKeyboardMarkup, KeyboardButton
import schedule
import time
import threading
#from queue import Queue
from telegram.utils.request import Request
from datetime import date, datetime, timedelta
import fcntl
from flask import Flask, request, jsonify

# Initialize Flask app
app = Flask(__name__)

# Define the main menu keyboard
main_menu_keyboard = [[KeyboardButton('Отримати статус негайно')], 
                      [KeyboardButton('Старт моніторингу'),
                       KeyboardButton('Зупинка моніторингу')],
                       [KeyboardButton('Налаштування')]]

# Define the settings menu
settings_menu_keyboard = [[KeyboardButton('Вказати IP адресу'), 
                          KeyboardButton('Вказати назву'), 
                          KeyboardButton('Вказати канал')], 
                          [KeyboardButton('Публікувати всюди'), 
                          KeyboardButton('Публікувати тільки в бот'), 
                          KeyboardButton('Публікувати тільки в канал')],
                          [KeyboardButton('Головне меню')]]

main_menu_markup     = ReplyKeyboardMarkup(main_menu_keyboard, resize_keyboard=True)
settings_menu_markup = ReplyKeyboardMarkup(settings_menu_keyboard, resize_keyboard=True)

def check_ip(ip: str) -> bool:
    cmd = "ping -c 1 " + ip
    status = subprocess.getstatusoutput(cmd)
    return status[0]==0

def get_string_no_electrisity(delta_sec: int) -> str:
    hours    = int(delta_sec/3600)
    minutes  = int((delta_sec - 3600*hours)/60)
    hour_str = ''
    min_str  = ''
    if hours != 0: hour_str = f"{hours} год."
    if minutes != 0: min_str = f"{minutes} хв."
    if hours == 0 and minutes < 1:
        return " менше хвилини"
    elif hours == 0 and minutes > 0:
        return min_str
    elif hours > 0 and minutes == 0:
        return hour_str
    else: return hour_str + " " + min_str

def start(update: Update, context: CallbackContext) -> None:
    user_id = str(update.message.from_user.id)
    chat_id = update.message.chat_id
    if user_id not in us.user_settings.keys():
        us.init_user(user_id)
        us.save_user_settings()
    else:
        # Recreate the job if it was saved previously
        if us.user_settings[user_id]['ping_job']:
            us.user_jobs[user_id] = schedule.every(1).minutes.do(ping_ip, user_id=user_id, chat_id=chat_id)

    update.message.reply_text(cfg.msg_greeting, reply_markup=main_menu_markup)

def settings(update: Update, context: CallbackContext) -> None:
    user_id = str(update.message.from_user.id)
    if user_id not in us.user_settings.keys():
        us.init_user(user_id)
    user = us.user_settings[user_id]
    msg = cfg.msg_settings + '\n'
    if user['ip_address']: msg += "IP адреса: " + user['ip_address'] + f" ({user['label']}) \n" 
    else: msg += "IP адреса не вказана \n"
    if user['channel_id']: msg += "Канал: " + user['channel_id'] + "\n" 
    if user['to_bot']: msg += "Публікація в бот ввімкнена\n"
    else: msg += "Публікація в бот вимкнена\n"
    if user['to_channel']: msg += "Публікація в канал ввімкнена\n"
    else: msg += "Публікація в канал вимкнена\n"
    update.message.reply_text(msg, reply_markup=settings_menu_markup)

def main_menu(update: Update, context: CallbackContext) -> None:
    update.message.reply_text(cfg.msg_mainmnu, reply_markup=main_menu_markup)

def set_ip(update: Update, context: CallbackContext) -> None:
    user_id = str(update.message.from_user.id)
    if user_id not in us.user_settings.keys():
        us.init_user(user_id)
    us.user_settings[user_id]['awaiting_ip']    = True
    us.user_settings[user_id]['awaiting_label'] = False
    us.save_user_settings()
    update.message.reply_text(cfg.msg_setip, reply_markup=settings_menu_markup)

def set_label(update: Update, context: CallbackContext) -> None:
    user_id = str(update.message.from_user.id)
    if user_id not in us.user_settings.keys():
        us.init_user(user_id)
    us.user_settings[user_id]['awaiting_ip']    = False
    us.user_settings[user_id]['awaiting_label'] = True
    us.save_user_settings()
    update.message.reply_text(cfg.msg_setlabel, reply_markup=settings_menu_markup)

def set_channel(update: Update, context: CallbackContext) -> None:
    user_id = str(update.message.from_user.id)
    if user_id not in us.user_settings.keys():
        us.init_user(user_id)
    us.user_settings[user_id]['awaiting_channel'] = True
    us.save_user_settings()
    update.message.reply_text(cfg.msg_setchannel, reply_markup=settings_menu_markup)

def handle_input(update: Update, context: CallbackContext) -> None:
    user_id = str(update.message.from_user.id)
    if user_id not in us.user_settings.keys():
        us.init_user(user_id)
    if us.user_settings[user_id]['awaiting_ip']:
        us.user_settings[user_id]['ip_address'] = update.message.text
        us.user_settings[user_id]['awaiting_ip']    = False
        us.user_settings[user_id]['awaiting_label'] = True
        update.message.reply_text(
            f'Вказано IP адресу {update.message.text}. Тепер вкажіть, будь-ласка, назву:',
            reply_markup=settings_menu_markup
        )
    elif us.user_settings[user_id]['awaiting_label']:
        us.user_settings[user_id]['label'] = update.message.text
        us.user_settings[user_id]['awaiting_ip']    = False
        us.user_settings[user_id]['awaiting_label'] = False
        update.message.reply_text(
            f'Назву оновлено на {update.message.text}. Тепер можна активізувати моніторинг',
            reply_markup=main_menu_markup
        )
    elif us.user_settings[user_id]['awaiting_channel']:
        channel_id = update.message.text
        if channel_id.startswith('https://t.me/'): channel_id.replace('channel_id', '')
        if not channel_id.startswith('@'): channel_id = '@' + channel_id
        us.user_settings[user_id]['channel_id'] = update.message.text
        us.user_settings[user_id]['awaiting_channel'] = False
        update.message.reply_text(
            f'Налаштовано публікацію в канал {update.message.text}',
            reply_markup=settings_menu_markup
        )
    us.save_user_settings()

def ping(update: Update, context: CallbackContext) -> None:
    user_id = str(update.message.from_user.id)
    chat_id = update.message.chat_id
    if user_id not in us.user_settings.keys():
        us.init_user(user_id)

    if not us.user_settings[user_id]['ip_address']:
        update.message.reply_text(cfg.msg_noip, reply_markup=settings_menu_markup)
        return

    # Stop any existing job before starting a new one
    if user_id in us.user_jobs.keys():
        schedule.cancel_job(us.user_jobs[user_id])

    # Initial ping immediately
    ping_ip(user_id, chat_id)

    # Schedule the ping job every 30 sec
    us.user_jobs[user_id] = schedule.every(1).minutes.do(ping_ip, user_id=user_id, chat_id=chat_id)
    us.user_settings[user_id]['ping_job'] = 'scheduled'
    
    us.save_user_settings()
    label = us.user_settings[user_id]['label']

    update.message.reply_text(
        f'Тепер бот перевірятиме доступність {label} кожну хвилину і повідомлятиме про зміну статусу',
        reply_markup=main_menu_markup
    )

def stop(update: Update, context: CallbackContext) -> None:
    user_id = str(update.message.from_user.id)
    if user_id not in us.user_settings.keys():
        us.init_user(user_id)
    if user_id in us.user_jobs.keys():
        schedule.cancel_job(us.user_jobs[user_id])
        us.user_settings[user_id]['ping_job'] = None
        update.message.reply_text(cfg.msg_stopped, reply_markup=main_menu_markup)
    else:
        update.message.reply_text(cfg.msg_notset, reply_markup=main_menu_markup)
    us.save_user_settings()

def post_all(update: Update, context: CallbackContext) -> None:
    user_id = str(update.message.from_user.id)
    if user_id not in us.user_settings.keys():
        us.init_user(user_id)
    us.user_settings[user_id]['to_bot']     = True
    us.user_settings[user_id]['to_channel'] = False
    msg = cfg.msg_postbot
    if us.user_settings[user_id]['channel_id']:
        us.user_settings[user_id]['to_channel'] = True
        msg += '\n' + cfg.msg_postchannel
    us.save_user_settings()
    update.message.reply_text(msg, reply_markup=main_menu_markup)

def post_to_bot(update: Update, context: CallbackContext) -> None:
    user_id = str(update.message.from_user.id)
    if user_id not in us.user_settings.keys():
        us.init_user(user_id)
    us.user_settings[user_id]['to_bot']     = True
    us.user_settings[user_id]['to_channel'] = False
    msg = cfg.msg_postbot
    if us.user_settings[user_id]['channel_id']:
        msg += '\n' + cfg.msg_nopostchannel
    us.save_user_settings()
    update.message.reply_text(msg, reply_markup=settings_menu_markup)

def post_to_channel(update: Update, context: CallbackContext) -> None:
    user_id = str(update.message.from_user.id)
    if user_id not in us.user_settings.keys():
        us.init_user(user_id)
    us.user_settings[user_id]['to_bot'] = False
    if us.user_settings[user_id]['channel_id']: 
        # turn on
        us.user_settings[user_id]['to_channel'] = True
        msg = cfg.msg_postchannel
        msg += '\n' + cfg.msg_nopostbot
    else:
        us.user_settings[user_id]['to_channel'] = False
        msg = cfg.msg_nochannel
    us.save_user_settings()
    update.message.reply_text(msg, reply_markup=settings_menu_markup)

def ping_ip(user_id, chat_id):
    if user_id not in us.user_settings.keys():
        us.init_user(user_id)
    ip_address = us.user_settings[user_id]['ip_address']
    label      = us.user_settings[user_id]['label']
    channel_id = us.user_settings[user_id]['channel_id']
    to_bot     = us.user_settings[user_id]['to_bot']
    to_channel = us.user_settings[user_id]['to_channel']
    last_state = us.user_settings[user_id]['last_state']
    if us.user_settings[user_id]['last_ts']:
        last_ts = datetime.strptime(us.user_settings[user_id]['last_ts'], '%Y-%m-%d %H:%M:%S')
    else: last_ts = None
    msg = None
    if ip_address:
        status = 'alive' if check_ip(ip_address) else 'not reachable'
        # if last_state is not set
        if not last_state:
            last_state = status
            last_ts = datetime.now()
            us.user_settings[user_id]['last_state'] = status
            us.user_settings[user_id]['last_ts']    = last_ts.strftime('%Y-%m-%d %H:%M:%S')
            msg = f"{label} тепер моніториться на наявність електрохарчування"
        # turned on
        elif last_state != status and last_state == 'not reachable':
            delta = datetime.now() - last_ts
            msg = f"Електрика в {label} з'явилася! Світла не було " + get_string_no_electrisity(delta.seconds)
            last_state = status
            last_ts = datetime.now()
            us.user_settings[user_id]['last_state'] = status
            us.user_settings[user_id]['last_ts']    = last_ts.strftime('%Y-%m-%d %H:%M:%S')
        elif last_state != status and last_state == 'alive':
            us.user_settings[user_id]['last_state'] = status
            us.user_settings[user_id]['last_ts']    = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            msg = f"Електрику в {label} вимкнули :("
        elif cfg.isPostOK == 'T' and status == 'alive':
            msg = cfg.msg_alive
        us.save_user_settings()
        if msg and to_bot: 
            bot.send_message(chat_id=chat_id, text=msg)
        if msg and to_channel and channel_id:
            bot.send_message(chat_id=channel_id, text=msg)

def ping_now(update: Update, context: CallbackContext) -> None:
    user_id = str(update.message.from_user.id)
    chat_id = update.message.chat_id
    if user_id not in us.user_settings.keys():
        us.init_user(user_id)
    if not us.user_settings[user_id]['ip_address']:
        update.message.reply_text(cfg.msg_noip, reply_markup=main_menu_markup)
        return
    ping_ip(user_id, chat_id)
    if us.user_settings[user_id]['last_state'] == 'alive':
        update.message.reply_text(cfg.msg_alive, reply_markup=main_menu_markup)
    else:
        update.message.reply_text(cfg.msg_blackout, reply_markup=main_menu_markup)

def schedule_pings():
    while True:
        schedule.run_pending()
        time.sleep(1)

def main():
    global bot
    pid_file = 'bot.pid'
    fp = open(pid_file, 'w')
    try:
        fcntl.lockf(fp, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except IOError:
        # another instance is running
        os.sys.exit(1)

    request = Request(con_pool_size=8)
    bot = Bot(token=BOT_TOKEN, request=request)

    updater = Updater(bot=bot, use_context=True)
    dispatcher = updater.dispatcher

    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CommandHandler("settings", settings))
    dispatcher.add_handler(CommandHandler("mainmenu", main_menu))
    dispatcher.add_handler(CommandHandler("ping", ping))
    dispatcher.add_handler(CommandHandler("check", ping_now))
    dispatcher.add_handler(CommandHandler("stop", stop))
    dispatcher.add_handler(CommandHandler("setip", set_ip))
    dispatcher.add_handler(CommandHandler("setlabel", set_label))
    dispatcher.add_handler(CommandHandler("setchannel", set_channel))
    dispatcher.add_handler(CommandHandler("postall", post_all))
    dispatcher.add_handler(CommandHandler("posttobot", post_to_bot))
    dispatcher.add_handler(CommandHandler("posttochannel", post_to_channel))

    dispatcher.add_handler(MessageHandler(Filters.regex('^Старт моніторингу$'), ping))
    dispatcher.add_handler(MessageHandler(Filters.regex('^Отримати статус негайно$'), ping_now))
    dispatcher.add_handler(MessageHandler(Filters.regex('^Налаштування$'), settings))
    dispatcher.add_handler(MessageHandler(Filters.regex('^Головне меню$'), main_menu))
    dispatcher.add_handler(MessageHandler(Filters.regex('^Зупинка моніторингу$'), stop))
    dispatcher.add_handler(MessageHandler(Filters.regex('^Вказати IP адресу$'), set_ip))
    dispatcher.add_handler(MessageHandler(Filters.regex('^Вказати назву$'), set_label))
    dispatcher.add_handler(MessageHandler(Filters.regex('^Вказати канал$'), set_channel))
    dispatcher.add_handler(MessageHandler(Filters.regex('^Публікувати тільки в канал$'), post_to_channel))
    dispatcher.add_handler(MessageHandler(Filters.regex('^Публікувати тільки в бот$'), post_to_bot))
    dispatcher.add_handler(MessageHandler(Filters.regex('^Публікувати всюди$'), post_all))
    dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_input))

    # Start the scheduler thread
    scheduler_thread = threading.Thread(target=schedule_pings)
    scheduler_thread.start()

    updater.start_polling()
    updater.idle()

@app.route('/send_message', methods=['POST'])
def send_message():
    data    = request.json
    sender = data.get('chat_id')

    try:
        caller_ip = request.remote_addr
        full_message = f"Sent from IP: {caller_ip}"
        bot.send_message(chat_id=sender, text=full_message)
        return jsonify({"status": "Message sent successfully"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
if __name__ == '__main__':
    main()
    app.run(host='0.0.0.0', port=5000)
    