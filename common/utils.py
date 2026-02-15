import config as cfg
import platform, subprocess, time, socket, ast
import requests as urlr
from telegram import Update, Bot, constants
from common.logger import init_logger
from structure.spot import Spot

# Create a logger
logger = init_logger('eSvitlo-utils', './logs/esvitlo.log')

# Constants
PARSE_MODE = constants.PARSEMODE_MARKDOWN_V2

class PingResult:
    def __init__(self, changed: bool, message: str):
        self.changed = changed
        self.message = message

def get_system() -> str:
    return (str(platform.system())).lower()

def check_ip(ip: str) -> bool:
    if get_system() == 'windows':
        cmd = "ping -n 1 " + ip
    else: cmd = "ping -c 1 " + ip
    status = subprocess.getstatusoutput(cmd)
    if not status[0] == 0:
        for i in range(1, 2):
            time.sleep(1)
            status = subprocess.getstatusoutput(cmd)
            if status[0]==0: return True
    return status[0]==0

def get_ip_status(ip: str) -> str:
    return cfg.ALIVE if check_ip(ip) else cfg.OFF

def get_text_safe_to_markdown(text: str)-> str:
    return text.replace('.', '\.').replace('!', '\!').replace('=', '\=').replace('(', '\(')\
        .replace(')', '\)').replace('-', '\-').replace('{', '\{').replace('}', '\}')\
            .replace('_', '\_').replace('+', '\+').replace('<', '\<').replace('>', '\>')

def get_key_safe(dictionary, key, default):
    if key not in dictionary.keys(): return default
    else: return dictionary[key]

def check_custom_api1(endpoint: str, headers, api_details) -> bool:
    response = urlr.get(endpoint, headers=ast.literal_eval((headers)))
    data = response.json()
    data = get_key_safe(get_key_safe(data, 'data', {}), 'thingList', {})
    try:
        check = str(([x['itemData']['online'] for x in data if x['itemData']['deviceid'] == api_details])[0]) == 'True'
        return cfg.ALIVE if check else cfg.OFF
    except Exception as e:
        logger.warning(f'API call error: {data}')
        return cfg.OFF 

def check_port(host, port, timeout=2):
    sck = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sck.settimeout(timeout)
    try:
        sck.connect((host, int(port)))
        sck.shutdown(socket.SHUT_RDWR)
        return cfg.ALIVE
    except:
        return cfg.OFF
    finally:
        sck.close()

def reply_md(message:str, update: Update, bot:Bot, reply_markup = None) -> None:
    chat_id = update.effective_chat.id
    message = get_text_safe_to_markdown(message)
    bot.send_message(chat_id, text=message, reply_markup=reply_markup, parse_mode=PARSE_MODE)

def edit_md(message:str, update: Update, reply_markup = None) -> None:
    query = update.callback_query
    query.answer()
    message = get_text_safe_to_markdown(message)
    query.edit_message_text(text=message, reply_markup=reply_markup, parse_mode=PARSE_MODE)

def _sender(spot: Spot, msg: str, bot:Bot, invoker: str = '_sender', force_to_bot:bool = False) -> None:
    if not msg or msg == '': return
    header = get_text_safe_to_markdown(f'*{spot.name}*\n' if not spot.is_multipost else '')
    if spot.to_bot or force_to_bot:
        try:
            bot.send_message(chat_id=spot.user_id, text=header + msg, parse_mode=PARSE_MODE)
        except Exception as e:
                logger.error(f'Error in _sender(): {invoker} invoked {spot.user_id} to send to bot, exception: {str(e)}')
    if spot.to_channel and spot.channel_id and not force_to_bot:
        try:
            bot.send_message(chat_id=spot.treated_channel_id, 
                             message_thread_id=spot.thread_id, 
                             text=msg, 
                             parse_mode=PARSE_MODE)
        except Exception as e:
                logger.error(f'Error in _sender(): {invoker} invoked {spot.user_id} to send to channel {spot.channel_id}, exception: {str(e)}')