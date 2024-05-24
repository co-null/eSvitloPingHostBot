import config as cfg
import platform
import subprocess
from datetime import datetime
import pytz
import time

use_tz = pytz.timezone(cfg.TZ)

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
        for i in range(1, 4):
            time.sleep(1)
            status = subprocess.getstatusoutput(cmd)
            if status[0]==0: return True
    if not status[0] == 0:
        time.sleep(5)
        for i in range(1, 4):
            time.sleep(1)
            status = subprocess.getstatusoutput(cmd)
            if status[0]==0: return True
    return status[0]==0

def get_ip_status(ip: str) -> str:
    return cfg.ALIVE if check_ip(ip) else cfg.OFF

def get_text_safe_to_markdown(text: str)-> str:
    return text.replace('.', '\.').replace('!', '\!').replace('=', '\=').replace('(', '\(').replace(')', '\)')

def get_key_safe(dictionary, key, default):
    if key not in dictionary.keys(): return default
    else: return dictionary[key]