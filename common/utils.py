import config as cfg
import platform, subprocess, time, socket, ast
import requests as urlr
import urllib.parse, random
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

class InvertorStatus:
    def __init__(self, status: str, battery: float):
        self.status  = status
        self.battery = battery

def get_system() -> str:
    return (str(platform.system())).lower()

def check_ip(ip) -> bool:
    for _ in range(4):
        try:
            result = subprocess.run(
                ["ping", "-n" if get_system() == 'windows' else "-c", "1", "-w", "5", ip],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=6  # seconds
            )
            if result.returncode == 0:
                return True
            else:
                logger.info(f"Ping {ip} attempt {_+1} failed: {result.stderr.decode()}")
                time.sleep(3)
        except subprocess.TimeoutExpired:
            logger.info(f"Ping command to {ip} timed out")
    return False

# def check_ip(ip: str) -> bool:
#     if get_system() == 'windows':
#         cmd = "ping -n 1 " + ip
#     else: cmd = "ping -c 1" + ip
#     status = subprocess.getstatusoutput(cmd)
#     if not status[0] == 0:
#         for i in range(1, 2):
#             time.sleep(1)
#             status = subprocess.getstatusoutput(cmd)
#             if status[0]==0: return True
#     return status[0]==0

def get_ip_status(ip: str) -> str:
    return cfg.ALIVE if check_ip(ip) else cfg.OFF

def get_text_safe_to_markdown(text: str)-> str:
    if not text: return ''
    return text.replace('.', '\.').replace('!', '\!').replace('=', '\=').replace('(', '\(')\
        .replace(')', '\)').replace('-', '\-').replace('{', '\{').replace('}', '\}')\
            .replace('_', '\_').replace('+', '\+').replace('<', '\<').replace('>', '\>')

def get_key_safe(dictionary, key, default):
    return default if key not in dictionary.keys() else dictionary[key]

def make_cookiejar_dict(cookies_str):
        cookiejar_dict = {}
        for cookie_string in cookies_str.split(";"):
            # maxsplit=1 because cookie value may have "="
            cookie_key, cookie_value = cookie_string.strip().split("=", maxsplit=1)
            cookiejar_dict[cookie_key] = cookie_value
        return cookiejar_dict

def check_custom_api1(headers, api_details) -> bool:
    ENDPOINT = "https://eu-apia.coolkit.cc/v2/device/thing"
    response = urlr.get(ENDPOINT, headers=ast.literal_eval(headers))
    data = response.json()
    data = get_key_safe(get_key_safe(data, 'data', {}), 'thingList', {})
    try:
        check = str(([x['itemData']['online'] for x in data if x['itemData']['deviceid'] == api_details])[0]) == 'True'
        return cfg.ALIVE if check else cfg.OFF
    except Exception as e:
        logger.warning(f'API call error: {data}')
        return cfg.OFF 
    
def parse_invertor1(request_string:str, spot: Spot) ->None:
    if spot.headers: 
        headers:dict = ast.literal_eval((spot.headers))
    else: headers = {}
    if request_string:
        args_pos =  request_string.find('?')
        if args_pos == -1: raise Exception("Wrong input string")
        args_string = request_string[args_pos+1:]
        args = args_string.split('&')
        for _ in args:
            param = _.split('=')
            headers[param[0]] =  param[1]
        spot.headers = str(headers)
    else:
        raise Exception("Wrong input string")
    
def parse_invertor2(headers_string:str, spot: Spot) ->None:
    if spot.headers: 
        headers:dict = ast.literal_eval((spot.headers))
    else: headers = {}
    if headers_string:
        for line in headers_string.split('\n'):
            if line == '' or line[:4] == 'POST': continue
            if not line.split(':', maxsplit=1)[0].lstrip().rstrip() == 'Cookie': continue
            line_value = line.split(':', maxsplit=1)[1]
            cookies = make_cookiejar_dict(line_value)
            break
        if cookies:
            headers['plantId']   =  cookies['selectedPlantId']
            headers['storageSn'] =  ast.literal_eval(urllib.parse.unquote(cookies['memoryDeviceSn']))[0]['value'][8:]
            headers['jsess']     =  cookies['JSESSIONID']
            headers['token']     =  cookies['assToken']
            spot.headers = str(headers)
    else:
        raise Exception("Wrong input string")

def _check_invertor1(spot: Spot) -> InvertorStatus:
    ENDPOINT = "https://web.dessmonitor.com/public/?sign={}&salt={}&token={}&action=webQueryDeviceEnergyFlowEs&source={}&devcode={}&pn={}&devaddr={}&sn={}"
    if not spot.headers: raise Exception("Empty Header")
    headers:dict = ast.literal_eval(spot.headers)
    sign    = headers['sign']
    salt    = headers['salt']
    token   = headers['token']
    source  = headers['source']
    devcode = headers['devcode']
    pn      = headers['pn']
    devaddr = headers['devaddr']#'1'
    sn      = headers['sn']

    response = urlr.get(ENDPOINT.format(sign, salt, token, source, devcode, pn, devaddr, sn), timeout=30)
    data = response.json()
    data = get_key_safe(get_key_safe(data, 'dat', {}), 'bt_status', {})
    try:
        battery_status = str(([x['status'] for x in data if x['par'] == 'bt_battery_capacity'])[0])
        battery_charged = float(([x['val'] for x in data if x['par'] == 'bt_battery_capacity'])[0])
        #logger.info(f"Spot: {spot.chat_id} got state {battery_status} level {battery_charged}")
        if battery_status == '-1': battery_status = cfg.ALIVE
        elif battery_status == '1': battery_status = cfg.OFF
        elif battery_status == '0': battery_status = cfg.OFFLINE
        else: battery_status = cfg.ERR
        return InvertorStatus(battery_status, battery_charged)
    except Exception as e:
        logger.warning(f'check_invertor1(chat_id={spot.chat_id}) error: {str(e)}')
        return InvertorStatus(cfg.ERR, 0.0) 

def _check_invertor2(spot: Spot) -> InvertorStatus:
    ENDPOINT = "https://server.pvbutler.com/panel/storage/getStorageStatusData?plantId={}"
    API_HEADER = {'Content-Type': 'application/x-www-form-urlencoded'}
    PAYLOAD = "plantId={}&storageSn={}"
    COOKIES = "lang=en; JSESSIONID={}; assToken={}"

    if not spot.headers: raise Exception("Empty Header")
    headers:dict = ast.literal_eval(spot.headers)
    plantId = headers['plantId']
    storage = headers['storageSn']
    jsess   = headers['jsess']
    token   = headers['token']

    session = urlr.Session()
    session.cookies = urlr.utils.cookiejar_from_dict(make_cookiejar_dict(COOKIES.format(jsess, token)))

    request = session.post(ENDPOINT.format(plantId), headers=API_HEADER, data=PAYLOAD.format(plantId, storage),timeout=30) 
    response = request.text
    try:
        json_response = ast.literal_eval(response)
    except Exception as e:
        logger.error(f'_check_invertor2(chat_id={spot.chat_id}) broken request, please resubmit spot parameters')
        return InvertorStatus(cfg.ERR, 0.0) 
    logger.info(f"Spot: {spot.chat_id} got json_response {json_response}")
    battery_status = str(json_response['obj']['status'])
    battery_charged = float(json_response['obj']['capacity'])
    #logger.info(f"Spot: {spot.chat_id} got state {battery_status} level {battery_charged}")
    ''' Device status, status (0: Offline, 1: Online, 2: Charging, 3: Discharging, 4: Error, 5: Burning, 6: Solar Charging, 
        7: Grid Charging, 8: Combined Charging (both solar and grid), 9: Combined Charging and Bypass (Grid) Output, 
        10: PV Charging and Bypass (Grid) Output, 11: Grid Charging and Bypass (Grid) Output, 12: Bypass (Grid) Output, 
        13: Solar Charging and Discharging Simultaneously, 14: Grid Charging and Discharging Simultaneously) '''
    if battery_status in ['10', '11', '12']: battery_status = cfg.ALIVE
    elif battery_status in ['-1', '0']: battery_status = cfg.OFFLINE
    else: battery_status = cfg.OFF
    return InvertorStatus(battery_status, battery_charged)

def check_invertor(spot: Spot, function) -> InvertorStatus:
    for _ in range(4):
        result:InvertorStatus = function(spot)
        if not result.status == cfg.ERR: return result
        else: 
            logger.info(f"{function}({spot.chat_id}) attempt {_+1} failed: {result.status}")
            time.sleep(3)
        return result

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