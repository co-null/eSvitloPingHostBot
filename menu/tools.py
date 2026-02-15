from common.logger import init_logger
from common.utils import reply_md, edit_md, get_text_safe_to_markdown
from actions import _ping
from bot_secrets import ADMIN_ID
from db.database import SessionMain
from structure.user import *
from structure.spot import *
import config as cfg, verbiages
from telegram import Update, Bot, InlineKeyboardButton, InlineKeyboardMarkup, constants
from telegram.ext import CallbackContext
from common.safe_schedule import SafeScheduler, scheduler
import json

PARSE_MODE = constants.PARSEMODE_MARKDOWN_V2

logger = init_logger('eSvitlo-tools', './logs/esvitlo.log')

def tools(update: Update, context: CallbackContext, args: str) -> None:
    params = json.loads(args)
    user_id = params['uid']
    # Create inline buttons
    button_set = []
    button_set.append([InlineKeyboardButton('Дані про користувача', 
                                            callback_data=json.dumps({'cmd':'gUser', 'uid':user_id}))])
    if str(user_id) == ADMIN_ID:
        button_set.append([InlineKeyboardButton('Список створених джобів', 
                                                callback_data=json.dumps({'cmd':'gJobs', 'uid':user_id}))])
        button_set.append([InlineKeyboardButton('Список користувачів', 
                                                callback_data=json.dumps({'cmd':'gUsers', 'uid':user_id}))])
        button_set.append([InlineKeyboardButton('Масова розсилка', 
                                                callback_data=json.dumps({'cmd':'brdcst', 'uid':user_id}))])
    button_set.append([InlineKeyboardButton(cfg.msg_mainmnu, 
                                            callback_data=json.dumps({'cmd':'main_menu', 'uid':user_id}))])
    # Send message with buttons
    reply_markup = InlineKeyboardMarkup(button_set)
    edit_md(cfg.msg_tools, update, reply_markup=reply_markup)

def spot_tools(update: Update, context: CallbackContext, bot:Bot, args: str) -> None:
    params = json.loads(args)
    user_id = params['uid']
    spot_id = params['cid']
    # Create inline buttons
    button_set = []
    
    button_set.append([InlineKeyboardButton('Переписати дату і час останього статусу', 
                                            callback_data=json.dumps({'cmd':'sPar', 'cid':spot_id, 'p':'ts'}))])
    button_set.append([InlineKeyboardButton('Встановити в "Є світло"', 
                                            callback_data=json.dumps({'cmd':'sPar', 'cid':spot_id, 'p':'on'}))])
    button_set.append([InlineKeyboardButton('Встановити в "Світло відсутнє"', 
                                            callback_data=json.dumps({'cmd':'sPar', 'cid':spot_id, 'p':'off'}))])
    button_set.append([InlineKeyboardButton('Назад до точки', 
                                            callback_data=json.dumps({'cmd':'ed_spot', 'uid':user_id, 'cid':spot_id}))])
    button_set.append([InlineKeyboardButton(cfg.msg_mainmnu, 
                                            callback_data=json.dumps({'cmd':'main_menu', 'uid':user_id}))])
    # Send message with buttons
    reply_markup = InlineKeyboardMarkup(button_set)
    edit_md(cfg.msg_tools, update, reply_markup=reply_markup)

def ask_get_user(update: Update, context: CallbackContext, bot: Bot, args: str) -> None:
    query = update.callback_query
    params = json.loads(args)
    user_id = params['uid']
    context.user_data['temporary_callback'] = args
    context.user_data['requestor'] = 'ask_get_user'
    if str(user_id) == ADMIN_ID:
        query.edit_message_text(text='Введіть ІД користувача:')
    else:
        _get_user(update, context, bot, int(user_id))

def _get_user(update: Update, context: CallbackContext, bot: Bot, user_id: int) -> None:
    context.user_data['temporary_callback'] = None
    context.user_data['requestor'] = None
    callback_data=json.dumps({'cmd':'tools', 'uid':user_id})
    buttons = [[InlineKeyboardButton('🆗', callback_data=callback_data)]]
    reply_markup = InlineKeyboardMarkup(buttons)
    session = SessionMain()
    msg = ''
    i = 0
    spots = session.query(models.Spot).filter_by(user_id=user_id, is_active=1).order_by(models.Spot.chat_id).all()
    for spot_m in spots:
        i += 1
        spot = Spot(spot_m.user_id, spot_m.chat_id).get()
        msg += verbiages.get_full_info(spot)
        if not i == 1: msg += '\n' 
    session.close()
    reply_md(msg, update, bot, reply_markup)

def get_user(update: Update, context: CallbackContext, bot: Bot, args: str) -> None:
    params = json.loads(args)
    user_id = params['uid']
    callback_data=json.dumps({'cmd':'tools', 'uid':user_id})
    buttons = [[InlineKeyboardButton('🆗', callback_data=callback_data)]]
    reply_markup = InlineKeyboardMarkup(buttons)
    entered = update.message.text[:11]
    try:
        user_id = int(entered)
    except Exception as e:
        reply_md(cfg.msg_badinput + '\n' + cfg.msg_proceed, 
                 update, bot, reply_markup)
        return
    _get_user(update, context, bot, user_id)

def get_scheduled_jobs(update: Update, context: CallbackContext, bot: Bot, args: str) -> None:
    chat_id = update.effective_chat.id
    if str(chat_id) == ADMIN_ID:
        jobs = scheduler.get_jobs()
        for job in range(len(jobs)):
            bot.send_message(chat_id, text=str(jobs[job]))

def get_users(update: Update, context: CallbackContext, bot: Bot, args: str) -> None:
    chat_id = update.effective_chat.id
    if str(chat_id) == ADMIN_ID:
        session = SessionMain()
        spots = session.query(models.Spot).filter_by(is_active=1).order_by(models.Spot.user_id, models.Spot.chat_id).all()
        for spot_m in spots:
            spot = Spot(spot_m.user_id, spot_m.chat_id)
            bot.send_message(chat_id, text=verbiages.get_full_info(spot))
        session.close()

def ask_broadcast(update: Update, context: CallbackContext, bot: Bot, args: str) -> None:
    query = update.callback_query
    chat_id = update.effective_chat.id
    params = json.loads(args)
    user_id = params['uid']
    callback_data=json.dumps({'cmd':'tools', 'uid':user_id})
    buttons = [[InlineKeyboardButton('🆗', callback_data=callback_data)]]
    reply_markup = InlineKeyboardMarkup(buttons)
    if str(chat_id) == ADMIN_ID:
        context.user_data['temporary_callback'] = args
        context.user_data['requestor'] = 'ask_broadcast'
        query.edit_message_text(text='Введіть повідомлення для розсилки:')
    else:
        query.edit_message_text(text=cfg.msg_badinput + '\n' + cfg.msg_proceed, 
                                reply_markup=reply_markup)

def broadcast(update: Update, context: CallbackContext, bot: Bot, args: str) -> None:
    context.user_data['temporary_callback'] = None
    context.user_data['requestor'] = None
    entered = get_text_safe_to_markdown(update.message.text)
    session = SessionMain()
    users = session.query(models.User).filter_by(is_active=1).all()
    for user in users:
        try:
            bot.send_message(chat_id=int(user.user_id), text=entered, parse_mode=PARSE_MODE)
        except Exception as e:
            logger.error(f'Error in broadcast(): sending to the {user.user_id}, exception: {str(e)}')
    session.close()

def ask_set_param(update: Update, context: CallbackContext, bot: Bot, args: str) -> None:
    query = update.callback_query
    params = json.loads(args)
    spot_id = params['cid']
    par_id  = params['p']
    spot = Spot(0,spot_id).get()
    context.user_data['temporary_callback'] = args
    context.user_data['requestor'] = 'ask_set_param'
    callback_data=json.dumps({'cmd':'sptTls', 'uid':spot.user_id, 'cid':spot.chat_id})
    buttons = [[InlineKeyboardButton('🆗', callback_data=callback_data)]]
    reply_markup = InlineKeyboardMarkup(buttons)
    if par_id == 'ts':
        reply_md(f"Введіть дату і час у форматі РРРР-ММ-ДД ГГ:ХХ:СС, наприклад {datetime.now(pytz.timezone(cfg.TZ)).strftime('%Y-%m-%d %H:%M:%S')}", update, bot)
    elif par_id == 'on':
        _ping(spot.user_id, spot.chat_id, bot, cfg.ALIVE)
        query.edit_message_text(text="Виконано", reply_markup=reply_markup)
    elif par_id == 'off':
        _ping(spot.user_id, spot.chat_id, bot, cfg.OFF)
        query.edit_message_text(text="Виконано", reply_markup=reply_markup)


def set_param(update: Update, context: CallbackContext, bot: Bot, args: str) -> None:
    context.user_data['temporary_callback'] = args
    entered = update.message.text[:20]
    params = json.loads(args)
    spot_id = params['cid']
    spot    = Spot(0, spot_id).get()
    context.user_data['temporary_callback'] = None
    context.user_data['requestor'] = None
    callback_data=json.dumps({'cmd':'sptTls', 'uid':spot.user_id, 'cid':spot.chat_id})
    buttons = [[InlineKeyboardButton('🆗', callback_data=callback_data)]]
    reply_markup = InlineKeyboardMarkup(buttons)
    ts = None
    if entered == '-':
        reply_md('Скасовано', update, bot, reply_markup=reply_markup)
    else:
        try:
            ts = datetime.strptime(entered, '%Y-%m-%d %H:%M:%S')
        except Exception as e:
            reply_md(cfg.msg_badinput + '\n' + cfg.msg_proceed, 
                     update, bot, reply_markup=reply_markup)
            return
        if ts > datetime.now(pytz.timezone(cfg.TZ)).replace(tzinfo=None):
            reply_md(cfg.msg_badinput + '\n' + cfg.msg_proceed, 
                     update, bot, reply_markup=reply_markup)
            return
        spot.last_ts = ts
        spot.refresh()
        reply_md(f"Дату і час останньої зміни статусу {spot.name} оновлено на {spot.last_ts.strftime('%Y-%m-%d %H:%M:%S')}", 
                 update, bot, reply_markup=reply_markup)