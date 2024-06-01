import bot_secrets
import config as cfg
import user_settings as us
import utils
import verbiages
import actions
import blackout_schedule as bos
from telegram.ext import Updater, CommandHandler, CallbackContext, MessageHandler, Filters
from telegram import Update, Bot, ReplyKeyboardMarkup, KeyboardButton, constants
from telegram.utils.request import Request as TRequest
import schedule
import time
import threading
from datetime import datetime
from flask import Flask, request, jsonify
#import logging
#logger = logging.getLogger(__name__)
#logging.basicConfig(format='%(asctime)s %(levelname)s:%(message)s', filename=cfg.LOG_FILE, encoding='utf-8', level=logging.ERROR)

PARSE_MODE = constants.PARSEMODE_MARKDOWN_V2
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
                           KeyboardButton('Слухати (так/ні)'),
                           KeyboardButton('Графік')],
                          [KeyboardButton('Головне меню')]]

main_menu_markup     = ReplyKeyboardMarkup(main_menu_keyboard, resize_keyboard=True)
settings_menu_markup = ReplyKeyboardMarkup(settings_menu_keyboard, resize_keyboard=True)

def reply_md(message:str, update: Update, reply_markup = None) -> None:
    message = utils.get_text_safe_to_markdown(message)
    #print(f'Message {message}')
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
            us.user_jobs[user_id] = schedule.every(cfg.SHEDULE_PING).minutes.do(_ping, user_id=user_id, chat_id=chat_id)
        if user.listener:
            us.listeners[user_id] = schedule.every(cfg.SHEDULE_LISTEN).minutes.do(_listen, user_id=user_id, chat_id=chat_id)
        reply_md(cfg.msg_comeback, update, reply_markup=main_menu_markup)
    bos.get_blackout_schedule()

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
    user.awaiting_ip      = True
    user.awaiting_label   = False
    user.awaiting_channel = False
    user.awaiting_city    = False
    user.awaiting_group   = False
    user.save()
    reply_md(cfg.msg_setip, update, reply_markup=settings_menu_markup)

def set_label(update: Update, context: CallbackContext) -> None:
    user_id = str(update.message.from_user.id)
    chat_id = update.message.chat_id
    if user_id not in us.user_settings.keys():
        reply_md(cfg.msg_error, update)
    user = us.User(user_id, chat_id)
    user.awaiting_ip      = False
    user.awaiting_label   = True
    user.awaiting_channel = False
    user.awaiting_city    = False
    user.awaiting_group   = False
    user.save()
    reply_md(cfg.msg_setlabel, update, reply_markup=settings_menu_markup)

def set_channel(update: Update, context: CallbackContext) -> None:
    user_id = str(update.message.from_user.id)
    chat_id = update.message.chat_id
    if user_id not in us.user_settings.keys():
        reply_md(cfg.msg_error, update)
    user = us.User(user_id, chat_id)
    user.awaiting_ip      = False
    user.awaiting_label   = False
    user.awaiting_channel = True
    user.save()
    reply_md(cfg.msg_setchannel, update, reply_markup=settings_menu_markup)

def yasno_schedule(update: Update, context: CallbackContext) -> None:
    user_id = str(update.message.from_user.id)
    chat_id = update.message.chat_id
    if user_id not in us.user_settings.keys():
        reply_md(cfg.msg_error, update)
        return
    user = us.User(user_id, chat_id)
    msg = f'{cfg.msg_setcity}\n{verbiages.get_key_list(bos.bo_cities)}'
    msg += cfg.msg_setcitybottom
    user.awaiting_ip      = False
    user.awaiting_label   = False
    user.awaiting_channel = False
    user.awaiting_city    = True
    user.awaiting_group   = False
    user.save()
    update.message.reply_text(msg)

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
        user.ip_address       = update.message.text[:15]
        user.awaiting_ip      = False
        user.awaiting_channel = False
        if not user.label or user.label == '':
            user.awaiting_label = True
            update.message.reply_text(f'Вказано IP адресу {user.ip_address}. Тепер вкажіть, будь-ласка, назву:')
        else:
            reply_md(f'Вказано IP адресу {user.ip_address}', update)
    elif user.awaiting_label:
        user.label = update.message.text[:255]
        user.awaiting_ip      = False
        user.awaiting_label   = False
        user.awaiting_channel = False
        update.message.reply_text(f'Назву оновлено на {user.label}. Тепер можна активізувати моніторинг (пінг)')
    elif user.awaiting_channel:
        channel_id = update.message.text[:255]
        if channel_id.startswith('https://t.me/'): channel_id.replace('https://t.me/', '')
        if not channel_id.startswith('@'): channel_id = '@' + channel_id
        user.channel_id = channel_id
        user.awaiting_channel = False
        user.awaiting_ip      = False
        user.awaiting_label   = False
        update.message.reply_text(f'Налаштовано публікацію в канал {channel_id}')
    elif user.awaiting_city:
        if update.message.text[:255] == '-':
            update.message.reply_text('Скасовано')
            user.city          = None
            user.group         = None
            user.has_schedule  = False
            user.awaiting_city = False
        else:
            user.city = None
            entered = str(update.message.text[:255])
            for city in bos.bo_cities.keys():
                if entered == city:
                    user.city = entered
            if not user.city: 
                update.message.reply_text('Некоректний ввод')
                user.awaiting_city = False
                user.save()
                return            
            user.awaiting_city    = False
            user.awaiting_group   = True
            update.message.reply_text(f'Вказано {user.city}. {cfg.msg_setgroup}')
    elif user.awaiting_group:
        if update.message.text[:1] == '-':
            update.message.reply_text('Скасовано')
            user.city           = None
            user.group          = None
            user.has_schedule   = False
            user.awaiting_group = False
        else:
            user.group = None
            entered = str(update.message.text[:1])
            for group in bos.bo_groups.keys():
                if entered == str(group):
                    user.group = group
            if not user.group: 
                update.message.reply_text('Некоректний ввод')
                user.awaiting_group = False
                user.save()
                return            
            user.awaiting_city  = False
            user.awaiting_group = False
            user.has_schedule   = True
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
    us.user_jobs[user.user_id] = schedule.every(cfg.SHEDULE_PING).minutes.do(_ping, user_id=user.user_id, chat_id=user.chat_id)
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
    us.listeners[user.user_id] = schedule.every(cfg.SHEDULE_LISTEN).minutes.do(_listen, user_id=user.user_id, chat_id=user.chat_id)
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
        msg = f'Тепер бот слухатиме {user.label} і повідомлятиме про зміну статусу, якщо повідомлення припиняться більше, ніж на 5 хв.'
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

def ping_now(update: Update, context: CallbackContext) -> None:
    user_id = str(update.message.from_user.id)
    chat_id = update.message.chat_id
    if user_id not in us.user_settings.keys():
        reply_md(cfg.msg_error, update)
        return
    user = us.User(user_id, chat_id)
    if not user.ip_address:
        reply_md(cfg.msg_noip, update)
        return
    result = actions._ping_ip(user, True)
    msg    = utils.get_text_safe_to_markdown(result.message)
    if result.message: 
        reply_md(result.message, update, reply_markup=main_menu_markup)
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
            user.last_state     = cfg.ALIVE
            user.last_ts        = datetime.now()
        user.last_heared_ts = datetime.now()
        user.save_state()
        if msg and user.to_bot: 
            bot.send_message(chat_id=user.chat_id, text=msg, parse_mode=PARSE_MODE)
        if msg and user.to_channel and user.channel_id:
            bot.send_message(chat_id=user.channel_id, text=msg, parse_mode=PARSE_MODE)

def _listen(user_id, chat_id):
    if user_id not in us.user_settings.keys():
        return
    user = us.User(user_id, chat_id)
    if not user.listener: 
        # was turned off somehow
        return
    # Do not spam if never worked
    if not user.last_state or not user.last_ts or not user.last_heared_ts: 
        return
    delta = datetime.now() - (user.last_heared_ts, user.last_ts)
    # If >300 sec (5 mins) and was turned on - consider blackout
    seconds = 86400*delta.days + delta.seconds
    if seconds > 300 and user.last_state == cfg.ALIVE:
        status = cfg.OFF
    elif user.last_state == cfg.ALIVE:
        # still enabled
        status = cfg.ALIVE
    elif seconds <= 300 and user.last_state == cfg.OFF:
        # turned on, maybe missed
        status = cfg.ALIVE
    else:    
        # still turned off
        status = cfg.OFF
    if status==user.last_state: changed = False
    else: changed = True
    if changed: 
        user.last_ts = max(user.last_heared_ts, user.last_ts)
        msg = actions.get_state_msg(user, status, False)
        msg = utils.get_text_safe_to_markdown(msg)
        user.last_state = status
    user.save_state()
    if changed and msg and user.to_bot: 
        bot.send_message(chat_id=chat_id, text=msg, parse_mode=PARSE_MODE)
    if changed and msg and user.to_channel and user.channel_id:
        bot.send_message(chat_id=user.channel_id, text=msg, parse_mode=PARSE_MODE)

def _gather_schedules():
    # Stop any existing job before starting a new one
    if 'yasno' in bos.blackout_schedule.keys():
        schedule.cancel_job(bos.blackout_schedule['yasno'])
    # Schedule gathering job every 60 min
    bos.blackout_schedule['yasno'] = schedule.every(60).minutes.do(bos.get_blackout_schedule)

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
            us.user_jobs[user_id] = schedule.every(cfg.SHEDULE_PING).minutes.do(_ping, user_id=user_id, chat_id=chat_id)
        if user.listener:
            if user_id in us.listeners.keys():
                schedule.cancel_job(us.listeners[user_id])
            us.listeners[user_id] = schedule.every(cfg.SHEDULE_LISTEN).minutes.do(_listen, user_id=user_id, chat_id=chat_id)
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
dispatcher.add_handler(CommandHandler("yasnoschedule", yasno_schedule))
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
dispatcher.add_handler(MessageHandler(Filters.regex('^Графік$'), yasno_schedule))
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
    