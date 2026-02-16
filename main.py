import bot_secrets, config as cfg, common.utils as utils, verbiages
from user_settings import user_jobs, listeners
from actions import _ping, _listen, _heard, ping_now
from structure.user import *
from structure.spot import *
from db.database import SessionMain
#import blackout_schedule as bos
from telegram.ext import Updater, CommandHandler, CallbackContext, MessageHandler, Filters, CallbackQueryHandler
from telegram import Update, Bot, ReplyKeyboardRemove, InlineKeyboardButton, InlineKeyboardMarkup, constants
from telegram.utils.request import Request as TRequest
import schedule, time, threading, pytz, json
from common.safe_schedule import SafeScheduler, scheduler
from common.logger import init_logger
from common.utils import reply_md, edit_md, _sender, get_text_safe_to_markdown, get_key_safe
import menu.settings as settings, menu.tools as tools, menu.help as help
from datetime import datetime
from flask import Flask, request, jsonify


# Create a logger
logger = init_logger('eSvitlo-main', './logs/esvitlo.log')

PARSE_MODE = constants.PARSEMODE_MARKDOWN_V2
# Initialize Flask app
app = Flask(__name__)

# Telegram bot initialization
bot_request = TRequest(con_pool_size=8, connect_timeout=300)
bot         = Bot(token=bot_secrets.BOT_TOKEN, request=bot_request)
updater     = Updater(bot=bot, use_context=True)
dispatcher  = updater.dispatcher


def start(update: Update, context: CallbackContext) -> None:
    user_id = str(update.message.from_user.id)
    user    = Userdb(int(user_id))
    if user.new :
        spot = Spot(user.user_id, str(user.user_id))
        reply_md(cfg.msg_greeting, update, bot)
        user.new = False
    else:
        # Recreate the jobs if saved previously
        session = SessionMain()
        spots = session.query(models.Spot).filter_by(user_id=user.user_id, is_active=1).order_by(models.Spot.chat_id).all()
        for spot in spots:
            if spot.ping_job:
                if spot.chat_id in user_jobs.keys():
                    scheduler.cancel_job(user_jobs[spot.chat_id])
                if spot.ip_address and not spot.endpoint:
                    user_jobs[spot.chat_id] = scheduler.every(cfg.SCHEDULE_PING).\
                        minutes.do(_ping, user_id=spot.user_id, chat_id=spot.chat_id, bot=bot)
                elif spot.endpoint:
                    user_jobs[spot.chat_id] = scheduler.every(2*int(cfg.SCHEDULE_PING)).\
                        minutes.do(_ping, user_id=spot.user_id, chat_id=spot.chat_id, bot=bot)
            if spot.listener:
                if spot.chat_id in listeners.keys():
                    scheduler.cancel_job(listeners[spot.chat_id])
                listeners[spot.chat_id] = scheduler.every(cfg.SCHEDULE_LISTEN).minutes.\
                    do(_listen, user_id=spot.user_id, chat_id=spot.chat_id, bot=bot)
            #TODO Blackout shedule
            # if user.has_schedule:
            #     _gather_schedules()
            #     _notification_schedules()
        reply_md(cfg.msg_comeback, update, bot, reply_markup=ReplyKeyboardRemove())
        #TODO Blackout shedule
        #bos.get_blackout_schedule()
        #bos.set_notifications()
    main_menu(update, context) 


def main_menu(update: Update, context: CallbackContext) -> None:
    user_id = update.effective_chat.id
    user    = Userdb(int(user_id)).get()
    # Create inline buttons
    button_set = []
    spots = session.query(models.Spot).filter_by(user_id=user.user_id, is_active=1).order_by(models.Spot.chat_id).all()
    for spot_m in spots:
        spot = Spot(spot_m.user_id, spot_m.chat_id).get()          
        callback_data = json.dumps({'cmd':'ping', 'uid':spot.user_id, 'cid':spot.chat_id})
        button_set.append([InlineKeyboardButton('Запит по ' + spot.name, 
                                                callback_data=callback_data)])
    button_set.append([InlineKeyboardButton('⚙️', 
                                            callback_data=json.dumps({'cmd':'settings', 'uid':user_id})),
                       InlineKeyboardButton('❓', 
                                            callback_data=json.dumps({'cmd':'help', 'uid':user_id})),
                        InlineKeyboardButton('🛠', 
                                            callback_data=json.dumps({'cmd':'tools', 'uid':user_id}))])
    # Send message with buttons
    reply_markup = InlineKeyboardMarkup(button_set)
    reply_md(cfg.msg_mainmnu, update, bot, reply_markup=reply_markup)

def handle_input(update: Update, context: CallbackContext) -> None:
    try:
        requestor = context.user_data['requestor']
        callback  = context.user_data['temporary_callback']
    except Exception as e:
        requestor = None
    
    if requestor == "ask_set_ip":
        settings.set_ip(update = update, context = context, bot=bot, args = callback)
    elif requestor == "ask_set_label":
        settings.set_label(update = update, context = context, bot=bot, args = callback)
    elif requestor == "ask_set_channel": 
        settings.set_channel(update = update, context = context, bot=bot, args = callback)
    elif requestor == "ask_drop_spot": 
        settings.drop_spot(update = update, context = context, bot=bot, args = callback)
    elif requestor == "ask_get_user": 
        tools.get_user(update = update, context = context, bot=bot, args = callback)
    elif requestor == "ask_broadcast": 
        tools.broadcast(update = update, context = context, bot=bot, args = callback)
    elif requestor == "ask_set_param": 
        tools.set_param(update = update, context = context, bot=bot, args = callback)
    else:
        return

def schedule_pings():
    while True:
        scheduler.run_pending()
        time.sleep(1)

# Up jobs if were saved
session = SessionMain()
spots = session.query(models.Spot).all()
for cur_spot in spots:
    try:
        if cur_spot.ping_job:
            if cur_spot.chat_id in user_jobs.keys():
                scheduler.cancel_job(user_jobs[cur_spot.chat_id])
            if cur_spot.ip_address and not cur_spot.endpoint:
                user_jobs[cur_spot.chat_id] = scheduler.every(cfg.SCHEDULE_PING).\
                    minutes.do(_ping, user_id=cur_spot.user_id, chat_id=cur_spot.chat_id, bot=bot)
            elif cur_spot.endpoint:
                user_jobs[cur_spot.chat_id] = scheduler.every(2*int(cfg.SCHEDULE_PING)).\
                    minutes.do(_ping, user_id=cur_spot.user_id, chat_id=cur_spot.chat_id, bot=bot)
        if cur_spot.listener:
            if cur_spot.chat_id in listeners.keys():
                scheduler.cancel_job(listeners[cur_spot.chat_id])
            listeners[cur_spot.chat_id] = scheduler.every(cfg.SCHEDULE_LISTEN).\
                minutes.do(_listen, user_id=cur_spot.user_id, chat_id=cur_spot.chat_id, bot=bot)
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
        settings.settings_spot(update = update, context = context, args = query.data)
    elif cmd == "add_spot":
        settings.add_spot(update = update, context = context, bot = bot, args = query.data)
    elif cmd == "drop":
        settings.ask_drop_spot(update = update, context = context, bot = bot, args = query.data)
    elif cmd == "sIp":
        settings.ask_set_ip(update = update, context = context, bot = bot, args = query.data)
    elif cmd == "sLabel":
        settings.ask_set_label(update = update, context = context, bot = bot, args = query.data)
    elif cmd == "sChannel":
        settings.ask_set_channel(update = update, context = context, bot = bot, args = query.data)
    elif cmd == "sToBot":
        settings.post_to_bot(update = update, context = context, bot = bot, args = query.data)    
    elif cmd == "sToChannel":
        settings.post_to_channel(update = update, context = context, bot = bot, args = query.data)
    elif cmd == "sPing":
        settings.ping(update = update, context = context, bot = bot, args = query.data)
    elif cmd == "sLsn":
        settings.listen(update = update, context = context, bot = bot, args = query.data)
    elif cmd == "sptTls":
        tools.spot_tools(update = update, context = context, bot = bot, args = query.data)
    elif cmd == "ping":
        ping_now(update = update, context = context, bot=bot, args = query.data)
    elif cmd == "settings":
        settings.settings(update = update, context = context, args = query.data)
    elif cmd == "tools":
        tools.tools(update = update, context = context, args = query.data)
    elif cmd == "gUser":
        tools.ask_get_user(update = update, context = context, bot = bot, args = query.data)
    elif cmd == "gJobs":
        tools.get_scheduled_jobs(update = update, context = context, bot = bot, args = query.data)
    elif cmd == "gUsers":
        tools.get_users(update = update, context = context, bot = bot, args = query.data)
    elif cmd == "brdcst":
        tools.ask_broadcast(update = update, context = context, bot = bot, args = query.data)
    elif cmd == "sPar":
        tools.ask_set_param(update = update, context = context, bot = bot, args = query.data)
    elif cmd == "help":
        help.help(update = update, context = context, bot = bot, args = query.data)
    elif cmd == "helpitem":
        help.helpitem(update = update, context = context, bot = bot, args = query.data)
        

# Register command handlers
dispatcher.add_handler(CommandHandler("start", start))
dispatcher.add_handler(CommandHandler("settings", settings.settings))
dispatcher.add_handler(CommandHandler("tools", tools.tools))
dispatcher.add_handler(CommandHandler("mainmenu", main_menu))
dispatcher.add_handler(CommandHandler("help", help.help))
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
        _heard(sender, spot, bot)
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
        _ping(sender, spot, bot, cfg.ALIVE)
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
        _ping(sender, spot, bot, cfg.OFF)
        return jsonify({"status": "OK", "time": ts}), 200
    except Exception as e:
        return jsonify({"error": 'Unexpected error'}), 500
    
if __name__ == '__main__':
    # Start the Telegram bot
    updater.start_polling()
    #updater.idle()

    # Run the Flask app
    app.run(host='0.0.0.0', port=5000)    