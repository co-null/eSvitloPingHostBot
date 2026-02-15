from common.logger import init_logger
import config as cfg, verbiages
from common.utils import reply_md, edit_md, get_system, get_text_safe_to_markdown
from common.safe_schedule import SafeScheduler, scheduler
from user_settings import user_jobs, listeners
from actions import _ping, _listen
import json
from telegram.ext import CallbackContext
from telegram import Update, Bot, InlineKeyboardButton, InlineKeyboardMarkup
from structure.user import *
from structure.spot import *

logger = init_logger('eSvitlo-settings', './logs/esvitlo.log')

def get_link(user_id, spot_no, chat_id) -> str:
    link = ''
    if get_system() == 'windows':
        link_base = cfg.LOCAL_URL + str(user_id)
    else: link_base = cfg.LISTENER_URL + str(user_id)
    if spot_no == 1: 
        link = f"*Для налаштування слухача для точки {spot_no} робіть виклики* на {link_base}"
    elif spot_no == 0: 
        link = f"*Для налаштування слухача для точки робіть виклики* на {link_base}"
    elif spot_no == -1: 
        link += f"*Для налаштування слухача для точки робіть виклики* на {link_base}&spot_id={chat_id}"
    else:
        link += '\n'
        link += f"*Для налаштування слухача для точки {spot_no} робіть виклики* на {link_base}&spot_id={chat_id}"
    return link

def settings(update: Update, context: CallbackContext, args:str = None) -> None:
    user_id = update.effective_chat.id
    user    = Userdb(int(user_id)).get()
    if not user:
        reply_md(cfg.msg_error, update, bot)
        logger.warning(f'settings: User {user_id} unknown')
        return
    button_set = []
    session = SessionMain()
    i = 0
    link = ''
    spots = session.query(models.Spot).filter_by(user_id=user.user_id, is_active=1).order_by(models.Spot.chat_id).all()
    for spot_m in spots:
        spot = Spot(spot_m.user_id, spot_m.chat_id).get()
        i += 1
        callback_data = json.dumps({'cmd':'ed_spot', 'uid':spot.user_id, 'cid':spot.chat_id})
        button_set.append([InlineKeyboardButton(f'Редагувати {spot.name}', callback_data=callback_data)])
        link += get_link(user_id, i, spot.chat_id)
    session.close()
    # Create inline buttons
    button_set.append([InlineKeyboardButton("Додати точку", 
                                            callback_data=json.dumps({'cmd':'add_spot', 'uid':user.user_id}))])
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
    if str(spot_id).find('_') == -1:
        link = get_link(user_id, 0, spot.chat_id)
    else:
        link = get_link(user_id, -1, spot.chat_id)
    # Create inline buttons
    on = '🔔'
    off = '🔕'
    ping = '🏓'
    hear = '🩺'
    stop = '❌'
    button_set = []
    button_set.append([InlineKeyboardButton('📡 IP', 
                                            callback_data=json.dumps({'cmd':'sIp', 'uid':spot.user_id, 'cid':spot.chat_id})),
                       InlineKeyboardButton('🪧 Назва', 
                                            callback_data=json.dumps({'cmd':'sLabel', 'uid':spot.user_id, 'cid':spot.chat_id})),
                       InlineKeyboardButton('📢 Канал', 
                                            callback_data=json.dumps({'cmd':'sChannel', 'uid':spot.user_id, 'cid':spot.chat_id}))])
    button_set.append([InlineKeyboardButton(f'{on if spot.to_bot else off} в бот', 
                                            callback_data=json.dumps({'cmd':'sToBot', 'uid':spot.user_id, 'cid':spot.chat_id})),
                       InlineKeyboardButton(f'{on if spot.to_channel else off} в канал', 
                                            callback_data=json.dumps({'cmd':'sToChannel', 'uid':spot.user_id, 'cid':spot.chat_id}))])
    button_set.append([InlineKeyboardButton(f"{ping if spot.ping_job =='scheduled' else stop} Пінг", 
                                            callback_data=json.dumps({'cmd':'sPing', 'uid':spot.user_id, 'cid':spot.chat_id})),
                       InlineKeyboardButton(f"{hear if spot.listener else stop} Слухати", 
                                            callback_data=json.dumps({'cmd':'sLsn', 'uid':spot.user_id, 'cid':spot.chat_id}))])
    button_set.append([InlineKeyboardButton('⚙️🔙', 
                                            callback_data=json.dumps({'cmd':'settings', 'uid':user_id})),
                       InlineKeyboardButton("🛠", 
                                            callback_data=json.dumps({'cmd':'sptTls', 'uid':spot.user_id, 'cid':spot.chat_id})),
                       InlineKeyboardButton('🗑', 
                                            callback_data=json.dumps({'cmd':'drop', 'uid':spot.user_id, 'cid':spot.chat_id}))])
    button_set.append([InlineKeyboardButton(cfg.msg_mainmnu, 
                                            callback_data=json.dumps({'cmd':'main_menu', 'uid':spot.user_id}))])
    # Send message with buttons
    reply_markup = InlineKeyboardMarkup(button_set)
    edit_md(verbiages._get_settings(spot) + "\n" + link, update, reply_markup=reply_markup)


def ask_set_ip(update: Update, context: CallbackContext, bot: Bot, args: str) -> None:
    query = update.callback_query
    context.user_data['temporary_callback'] = args
    context.user_data['requestor'] = 'ask_set_ip'
    # Send message
    query.edit_message_text(text=cfg.msg_setip)

def set_ip(update: Update, context: CallbackContext, bot: Bot, args: str) -> None:
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
    buttons = [[InlineKeyboardButton('🆗', callback_data=callback_data)]]
    reply_markup = InlineKeyboardMarkup(buttons)
    if entered == '-' and spot.ip_address:
        spot.ip_address = None
        spot.ping_job   = None
        reply_md('ІР адресу видалено', update, bot, reply_markup=reply_markup)
        if spot.chat_id in user_jobs.keys():
            scheduler.cancel_job(user_jobs[spot.chat_id])
        return
    elif entered == '-' and not spot.ip_address:
        reply_md('Скасовано', update, bot)
        return
    else:
        spot.ip_address = entered
    spot.refresh()
    if not spot.label or spot.label == '':
        query.edit_message_text(text=f'Вказано IP адресу {spot.ip_address}.', 
                                reply_markup=reply_markup)
        ask_set_label(update = update, context = context, args = args)
    else:
        reply_md(f'Вказано IP адресу {spot.ip_address}', 
                 update, bot, reply_markup=reply_markup)

def ask_set_label(update: Update, context: CallbackContext, bot: Bot, args: str) -> None:
    query = update.callback_query
    context.user_data['temporary_callback'] = args
    context.user_data['requestor'] = 'ask_set_label'
    # Send message
    query.edit_message_text(text=cfg.msg_setlabel)

def set_label(update: Update, context: CallbackContext, bot: Bot, args: str) -> None:
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
    buttons = [[InlineKeyboardButton('🆗', callback_data=callback_data)]]
    reply_markup = InlineKeyboardMarkup(buttons)
    if entered == '-' and spot.label:
        spot.label = None
        reply_md('Назву видалено', update, bot, reply_markup=reply_markup)
    elif entered == '-' and not spot.label:
        reply_md('Скасовано', update, bot, reply_markup=reply_markup)
    else:
        spot.label = entered
        spot.refresh()
        reply_md(f'Назву оновлено на {spot.label}. Тепер можна активізувати моніторинг', 
                 update, bot, reply_markup=reply_markup)

def ask_set_channel(update: Update, context: CallbackContext, bot: Bot, args: str) -> None:
    query = update.callback_query
    context.user_data['temporary_callback'] = args
    context.user_data['requestor'] = 'ask_set_channel'
    # Send message
    query.edit_message_text(text=cfg.msg_setchannel)

def set_channel(update: Update, context: CallbackContext, bot: Bot, args: str) -> None:
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
    buttons = [[InlineKeyboardButton('🆗', callback_data=callback_data)]]
    reply_markup = InlineKeyboardMarkup(buttons)

    if entered == '-' and spot.channel_id:
        spot.channel_id = None
        reply_md('Канал видалено', update, bot, reply_markup=reply_markup)
    elif entered == '-' and not spot.channel_id:
        reply_md('Скасовано', update, bot, reply_markup=reply_markup)
    elif ' ' in entered:
        reply_md(cfg.msg_badinput + '\n' + cfg.msg_proceed, 
                 update, bot, reply_markup=reply_markup)
    else:
        spot.channel_id = entered
        spot.refresh()
        reply_md(f'Налаштовано публікацію в канал {spot.channel_id}', 
                 update, bot, reply_markup=reply_markup)

def add_spot(update: Update, context: CallbackContext, bot: Bot, args: str) -> None:
    params  = json.loads(args)
    user_id = params['uid']
    user    = Userdb(int(user_id))
    session = SessionMain()
    num_spots = session.query(models.Spot).filter_by(user_id=user.user_id, is_active=1).count()
    if num_spots >= int(cfg.MAX_SPOTS):
        edit_md(cfg.msg_addforbidden, update)
        return
    # Send message
    spot    = Spot(user_id, str(user_id) + '_' + str(user.num_spots + 1))
    spot.label = 'Нова'
    spot.refresh()
    callback_data = json.dumps({'cmd':'ed_spot', 'uid':spot.user_id, 'cid':spot.chat_id})
    buttons = [[InlineKeyboardButton('🆗', callback_data=callback_data)]]
    reply_markup = InlineKeyboardMarkup(buttons)
    edit_md(cfg.msg_spotadded, update, reply_markup=reply_markup)
    #ask_set_label(update, context, callback_data, bot, args)

def ask_drop_spot(update: Update, context: CallbackContext, bot: Bot, args: str) -> None:
    query = update.callback_query
    params = json.loads(args)
    user_id = params['uid']
    spot_id = params['cid']
    spot    = Spot(user_id, spot_id).get()
    context.user_data['temporary_callback'] = args
    context.user_data['requestor'] = 'ask_drop_spot'
    callback_data=json.dumps({'cmd':'settings', 'uid':spot.user_id})
    buttons = [[InlineKeyboardButton('🆗', callback_data=callback_data)]]
    reply_markup = InlineKeyboardMarkup(buttons)
    session = SessionMain()
    num_spots = session.query(models.Spot).filter_by(user_id=user_id, is_active=1).count()
    if num_spots < 2:
        query.edit_message_text(text={cfg.msg_dropforbidden}, reply_markup=reply_markup)
        return
    # Send message
    query.edit_message_text(text=f"{cfg.msg_dropspot1} {spot.name} {cfg.msg_dropspot2}")

def drop_spot(update: Update, context: CallbackContext, bot: Bot, args: str) -> None:
    query = update.callback_query
    context.user_data['temporary_callback'] = args
    entered = update.message.text[:10]
    params = json.loads(args)
    user_id = params['uid']
    spot_id = params['cid']
    spot    = Spot(user_id, spot_id).get()
    context.user_data['temporary_callback'] = None
    context.user_data['requestor'] = None
    callback_data=json.dumps({'cmd':'settings', 'uid':spot.user_id})
    buttons = [[InlineKeyboardButton('🆗', callback_data=callback_data)]]
    reply_markup = InlineKeyboardMarkup(buttons)

    if 'delete' == entered:
        spot.is_active = False
        spot.to_bot = False
        spot.to_channel = False
        spot.ping_job = None
        if spot.chat_id in user_jobs.keys():
            scheduler.cancel_job(user_jobs[spot.chat_id])
            del user_jobs[spot.chat_id]
        spot.refresh()
        reply_md(f'Видалено точку {spot.name}', 
                 update, bot, reply_markup=reply_markup)
    else:
        reply_md('Скасовано', update, bot, reply_markup=reply_markup)

def post_to_bot(update: Update, context: CallbackContext, bot: Bot, args: str) -> None:
    params = json.loads(args)
    user_id = params['uid']
    spot_id = params['cid']
    spot    = Spot(user_id, spot_id).get()
    context.user_data['temporary_callback'] = None
    context.user_data['requestor'] = None
    callback_data=json.dumps({'cmd':'ed_spot', 'uid':spot.user_id, 'cid':spot.chat_id})
    buttons = [[InlineKeyboardButton('🆗', callback_data=callback_data)]]
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
    edit_md(msg, update, reply_markup=reply_markup)

def post_to_channel(update: Update, context: CallbackContext, bot: Bot, args: str) -> None:
    params = json.loads(args)
    user_id = params['uid']
    spot_id = params['cid']
    spot    = Spot(user_id, spot_id).get()
    context.user_data['temporary_callback'] = None
    context.user_data['requestor'] = None
    callback_data=json.dumps({'cmd':'ed_spot', 'uid':spot.user_id, 'cid':spot.chat_id})
    buttons = [[InlineKeyboardButton('🆗', callback_data=callback_data)]]
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
    edit_md(msg, update, reply_markup=reply_markup)

def _start_ping(spot: Spot, bot: Bot) -> None:
    # Stop any existing job before starting a new one
    if spot.chat_id in user_jobs.keys():
        scheduler.cancel_job(user_jobs[spot.chat_id])
    # Schedule the ping job every min
    if spot.ip_address and not spot.endpoint:
        user_jobs[spot.chat_id] = scheduler.every(cfg.SCHEDULE_PING).\
            minutes.do(_ping, user_id=spot.user_id, chat_id=spot.chat_id, bot=bot)
    elif spot.endpoint:
        user_jobs[spot.chat_id] = scheduler.every(2*int(cfg.SCHEDULE_PING)).\
            minutes.do(_ping, user_id=spot.user_id, chat_id=spot.chat_id, bot=bot)
    spot.ping_job = 'scheduled'
    spot.refresh()
    # Initial ping immediately
    _ping(spot.user_id, spot.chat_id, bot)

def _stop_ping(spot: Spot) -> None:
    if spot.chat_id in user_jobs.keys():
        scheduler.cancel_job(user_jobs[spot.chat_id])
        del user_jobs[spot.chat_id]
    spot.ping_job = None

def ping(update: Update, context: CallbackContext, bot:Bot, args:str = '{}') -> None:
    params = json.loads(args)
    user_id = params['uid']
    spot_id = params['cid']
    spot    = Spot(user_id, spot_id).get()
    context.user_data['temporary_callback'] = None
    context.user_data['requestor'] = None
    callback_data=json.dumps({'cmd':'ed_spot', 'uid':spot.user_id, 'cid':spot.chat_id})
    buttons = [[InlineKeyboardButton('🆗', callback_data=callback_data)]]
    reply_markup = InlineKeyboardMarkup(buttons)
    if not spot.ping_job == 'scheduled':
        # If need to turn on
        if not spot.ip_address and not spot.endpoint:
            edit_md(cfg.msg_noip, update, reply_markup=reply_markup)
            return
        _start_ping(spot, bot)
        msg = f'Тепер бот перевірятиме доступність {spot.label} і повідомлятиме про зміну статусу'
    else:
        # If need to turn off
        if spot.chat_id in user_jobs.keys():
            msg = cfg.msg_stopped
        else:
            msg = cfg.msg_notset
        _stop_ping(spot)
    spot.refresh()
    edit_md(msg, update, reply_markup=reply_markup)

def _start_listen(spot: Spot, bot: Bot):
    # Stop any existing job before starting a new one
    if spot.chat_id in listeners.keys():
        scheduler.cancel_job(listeners[spot.chat_id])
    # Schedule the listen job every min
    listeners[spot.chat_id] = scheduler.every(cfg.SCHEDULE_LISTEN).minutes\
        .do(_listen, user_id=spot.user_id, chat_id=spot.chat_id, bot=bot)
    spot.listener = True
    # Initial check immediately
    _listen(spot.user_id, spot.chat_id, bot)

def _stop_listen(spot: Spot):
    if spot.chat_id in listeners.keys():
        scheduler.cancel_job(listeners[spot.chat_id])
        del listeners[spot.chat_id]
    spot.listener = False

def listen(update: Update, context: CallbackContext, bot:Bot, args: str = '{}') -> None:
    params = json.loads(args)
    user_id = params['uid']
    spot_id = params['cid']
    spot    = Spot(user_id, spot_id).get()
    context.user_data['temporary_callback'] = None
    context.user_data['requestor'] = None
    callback_data=json.dumps({'cmd':'ed_spot', 'uid':spot.user_id, 'cid':spot.chat_id})
    buttons = [[InlineKeyboardButton('🆗', callback_data=callback_data)]]
    reply_markup = InlineKeyboardMarkup(buttons)
    if not spot.listener:
        # If need to turn on
        _start_listen(spot, bot)
        msg = cfg.msg_listeneron
        msg += f'Тепер бот слухатиме {spot.name} і повідомлятиме про зміну статусу, якщо повідомлення припиняться більше, ніж на 3 хв.\n'
    else:
        # If need to turn off
        _stop_listen(spot)
        msg = cfg.msg_listeneroff
    spot.refresh()
    edit_md(msg, update, reply_markup=reply_markup)


def get_user_params(update: Update, context: CallbackContext) -> None:
    update.message.reply_text(cfg.msg_listparams)

def set_user_param(update: Update, context: CallbackContext) -> None:
    global sys_commands
    chat_id = update.effective_chat.id
    sys_commands[chat_id] = {}
    sys_commands[chat_id]['ask_set_user_param'] = True
    update.message.reply_text('Введіть команду:')