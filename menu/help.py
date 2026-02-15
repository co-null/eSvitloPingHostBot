from common.logger import init_logger
import config as cfg
from common.utils import reply_md, edit_md, get_text_safe_to_markdown
from telegram import Update, Bot, InlineKeyboardButton, InlineKeyboardMarkup, constants
from telegram.ext import CallbackContext
import json

PARSE_MODE = constants.PARSEMODE_MARKDOWN_V2

logger = init_logger('eSvitlo-help', './logs/esvitlo.log')

def help(update: Update, context: CallbackContext, bot: Bot = None, args: str = None) -> None:
    query = update.callback_query
    chat_id = update.effective_chat.id
    params = json.loads(args)
    user_id = params['uid']
    # Create inline buttons
    button_set = []
    button_set.append([InlineKeyboardButton('Загальні питання', 
                                            callback_data=json.dumps({'cmd':'helpitem', 'id':'1', 'uid':user_id}))])
    button_set.append([InlineKeyboardButton('Головне меню: Запит по <назва точки>', 
                                            callback_data=json.dumps({'cmd':'helpitem', 'id':'2', 'uid':user_id}))])
    button_set.append([InlineKeyboardButton('⚙️ - Налаштування', 
                                            callback_data=json.dumps({'cmd':'helpitem', 'id':'5', 'uid':user_id}))])
    button_set.append([InlineKeyboardButton('⚙️ - Налаштування <назва точки>', 
                                            callback_data=json.dumps({'cmd':'helpitem', 'id':'51', 'uid':user_id}))])
    button_set.append([InlineKeyboardButton('⚙️ - Додати точку', 
                                            callback_data=json.dumps({'cmd':'helpitem', 'id':'52', 'uid':user_id}))])
    button_set.append([InlineKeyboardButton('📡 IP', 
                                            callback_data=json.dumps({'cmd':'helpitem', 'id':'6', 'uid':user_id})),
                       InlineKeyboardButton('🪧 Назва', 
                                            callback_data=json.dumps({'cmd':'helpitem', 'id':'7', 'uid':user_id})),
                       InlineKeyboardButton('📢 Канал', 
                                            callback_data=json.dumps({'cmd':'helpitem', 'id':'8', 'uid':user_id}))])
    button_set.append([InlineKeyboardButton('🔔/🔕 в бот', 
                                            callback_data=json.dumps({'cmd':'helpitem', 'id':'9', 'uid':user_id})),
                       InlineKeyboardButton('🔔/🔕 в канал', 
                                            callback_data=json.dumps({'cmd':'helpitem', 'id':'10', 'uid':user_id}))])
    button_set.append([InlineKeyboardButton('🏓/❌ Пінг', 
                                            callback_data=json.dumps({'cmd':'helpitem', 'id':'11', 'uid':user_id})),
                       InlineKeyboardButton('🩺/❌ Слухати', 
                                            callback_data=json.dumps({'cmd':'helpitem', 'id':'12', 'uid':user_id}))])
    button_set.append([InlineKeyboardButton('🗑 Видалити точку', 
                                            callback_data=json.dumps({'cmd':'helpitem', 'id':'15', 'uid':user_id}))])
    button_set.append([InlineKeyboardButton(cfg.msg_mainmnu, 
                                            callback_data=json.dumps({'cmd':'main_menu', 'uid':user_id}))])
    # Send message with buttons
    reply_markup = InlineKeyboardMarkup(button_set)
    query.edit_message_text(text="Довідка:", reply_markup=reply_markup)

def helpitem(update: Update, context: CallbackContext, bot: Bot, args: str) -> None:
    query = update.callback_query
    params = json.loads(args)
    user_id = params['uid']
    item_id = params['id']
    context.user_data['temporary_callback'] = None
    context.user_data['requestor'] = None
    callback_data=json.dumps({'cmd':'help', 'uid':user_id})
    buttons = [[InlineKeyboardButton('OK', callback_data=callback_data)]]
    reply_markup = InlineKeyboardMarkup(buttons)
    query.edit_message_text(text=get_text_safe_to_markdown(cfg.msg_help[item_id]), 
                            reply_markup=reply_markup, parse_mode=PARSE_MODE)