import config as cfg
import utils
import verbiages
import user_settings as us
from datetime import datetime
import pytz

use_tz = pytz.timezone(cfg.TZ)

def _ping_ip(user: us.User, immediately: bool = False) -> utils.PingResult:
    if user.ip_address:
        status = utils.get_ip_status(user.ip_address)
        if user.last_state and status==user.last_state: changed = False
        else: changed = True
        msg = get_state_msg(user, status, immediately)
        if changed:
            user.last_state = status
            user.last_ts    = datetime.now()
            user.save_state()
        return utils.PingResult(changed, msg)
    else: return

def get_state_msg(user: us.User, status: str, immediately: bool = False) -> str:
    now_ts_short = datetime.now(use_tz).strftime('%H:%M')
    msg = ""
    # if last_state is not set
    if not user.last_state:
        if user.label and user.label != '':
            msg += f"{user.label} тепер моніториться на наявність електрохарчування\n"
        else:
            msg += "Моніториться на наявність електрохарчування\n"
    # turned on
    if user.last_state and user.last_state != status and user.last_state == cfg.OFF:
        delta = datetime.now() - user.last_ts
        msg += f"💡*{now_ts_short}* Юху! Світло з нами!\n" + "Було відсутнє " + verbiages.get_string_period(delta.seconds)
    # turned off
    elif user.last_state and user.last_state != status and user.last_state == cfg.ALIVE:
        delta = datetime.now() - user.last_ts
        msg += f"🔦*{now_ts_short}* Йой… От халепа 😒\n" + "Було наявне " + verbiages.get_string_period(delta.seconds)
    # same
    elif cfg.isPostOK == 'T' or immediately:
        delta = datetime.now() - user.last_ts
        if status == cfg.ALIVE:
            msg += cfg.msg_alive
            msg += "\n" + "Світло є вже " + verbiages.get_string_period(delta.seconds)
        else:
            msg += cfg.msg_blackout
            msg += "\n" + "Світла немає вже " + verbiages.get_string_period(delta.seconds)
    return msg