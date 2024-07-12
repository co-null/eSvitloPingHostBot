import config as cfg
import utils
import verbiages
import user_settings as us
import blackout_schedule as bos
from datetime import datetime
import pytz

use_tz = pytz.timezone(cfg.TZ)

def _ping_ip(user: us.User, immediately: bool = False) -> utils.PingResult:
    if user.ip_address and user.ping_job == 'scheduled':
        status = utils.get_ip_status(user.ip_address)
        if user.last_state and status==user.last_state: changed = False
        else: changed = True
        if changed or immediately:
            msg = get_state_msg(user, status, immediately)
        else: msg = ""
        if changed:
            user.last_state = status
            user.last_ts    = datetime.now()
            user.save_state()
        return utils.PingResult(changed, msg)
    elif not user.ip_address and user.endpoint and user.ping_job == 'scheduled':
        status = utils.check_custom_api1(user.endpoint, user.headers)
        if user.last_state and status==user.last_state: changed = False
        else: changed = True
        if changed or immediately:
            msg = get_state_msg(user, status, immediately)
        else: msg = ""
        if changed:
            user.last_state = status
            user.last_ts    = datetime.now()
            user.save_state()
        return utils.PingResult(changed, msg)
    else: utils.PingResult(False, " ")

def get_state_msg(user: us.User, status: str, immediately: bool = False) -> str:
    now_ts_short = datetime.now(use_tz).strftime('%H:%M')
    msg = ""
    add = ""
    windows = None
    if user.has_schedule: 
        try:
            windows = bos.get_windows_analysis(bos.bo_cities[user.city], bos.bo_groups[user.group])
            add = "\n" + verbiages.get_outage_message(status, windows)
        except Exception as e:
            print(f'Exception in get_state_msg: {e}, status={status}, windows={windows}')
    # if last_state is not set
    if not user.last_state:
        if user.label and user.label != '':
            msg += f"{user.label} тепер моніториться на наявність електрохарчування\n"
        else:
            msg += "Моніториться на наявність електрохарчування\n"
    # turned on
    if user.last_state and user.last_state != status and user.last_state == cfg.OFF:
        delta = datetime.now() - user.last_ts
        msg += f"💡*{now_ts_short}* Юху! Світло повернулося!\n" + "⏱ Було відсутнє *" + verbiages.get_string_period(delta) + "*"
        msg += add
    # turned off
    elif user.last_state and user.last_state != status and user.last_state == cfg.ALIVE:
        delta = datetime.now() - user.last_ts
        msg += f"🔦*{now_ts_short}* Йой… Халепа, знову без світла 😒\n" + "⏱ Було наявне *" + verbiages.get_string_period(delta) + "*"
        msg += add
    # same
    elif cfg.isPostOK == 'T' or immediately:
        delta = datetime.now() - user.last_ts
        if status == cfg.ALIVE:
            msg += cfg.msg_alive
            msg += "\n" + "⏱ Світло є вже *" + verbiages.get_string_period(delta) + "*"
            msg += add
        else:
            msg += cfg.msg_blackout
            msg += "\n" + "⏱ Світла немає вже *" + verbiages.get_string_period(delta) + "*"
            msg += add
    return msg