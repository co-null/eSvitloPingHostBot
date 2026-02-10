import utils, config as cfg
from verbiages import get_state_msg
from structure.spot import Spot
from datetime import datetime
import pytz, logging
from logging.handlers import TimedRotatingFileHandler

# Create a logger
logger = logging.getLogger('eSvitlo-actions')
logger.setLevel(logging.DEBUG)

# Create a file handler
fh = TimedRotatingFileHandler('./logs/esvitlo.log', encoding='utf-8', when="D", interval=1, backupCount=30)
fh.setLevel(logging.INFO)

# Create a console handler
ch = logging.StreamHandler()
ch.setLevel(logging.ERROR)

# Create a formatter
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
fh.setFormatter(formatter)
ch.setFormatter(formatter)

# Add handlers to the logger
logger.addHandler(fh)
logger.addHandler(ch)


def _ping_ip(spot: Spot, immediately: bool = False, force_state:str = None) -> utils.PingResult:
    if force_state:
        status = force_state
        if spot.last_state and status==spot.last_state: changed = False
        else: changed = True
        msg = get_state_msg(spot, status, True)
        if changed: spot.new_state(status)
        if status == cfg.ALIVE: spot.last_heared_ts = datetime.now(pytz.timezone(cfg.TZ))
        return utils.PingResult(changed, msg)
    elif spot.ip_address:
        port_pos =  spot.ip_address.find(':')
        if port_pos == -1:
            status = utils.get_ip_status(spot.ip_address)
            if spot.last_state and status==spot.last_state: changed = False
            else: changed = True
            if changed or immediately:
                msg = get_state_msg(spot, status, immediately)
            else: msg = ""
            if changed: spot.new_state(status)
            if status == cfg.ALIVE: spot.last_heared_ts = datetime.now(pytz.timezone(cfg.TZ))  
            return utils.PingResult(changed, msg)
        else:
            host = spot.ip_address[:port_pos]
            port = spot.ip_address[port_pos+1:]
            status = utils.check_port(host, port)
            if spot.last_state and status==spot.last_state: changed = False
            else: changed = True
            if changed or immediately:
                logger.info(f'Pinging: User {spot.user_id} - status: {status}, changed:{changed}')
                msg = get_state_msg(spot, status, immediately)
            else: msg = ""
            if changed: spot.new_state(status)
            if status == cfg.ALIVE: spot.last_heared_ts = datetime.now(pytz.timezone(cfg.TZ))  
            return utils.PingResult(changed, msg)
    elif not spot.ip_address and spot.endpoint:
        status = utils.check_custom_api1(spot.endpoint, spot.headers, spot.api_details)
        if spot.last_state and status==spot.last_state: changed = False
        else: changed = True
        if changed or immediately:
            logger.info(f'API call: User {spot.user_id} - status: {status}, changed:{changed}')
            msg = get_state_msg(spot, status, immediately)
        else: msg = ""
        if changed: spot.new_state(status)
        if status == cfg.ALIVE: spot.last_heared_ts = datetime.now(pytz.timezone(cfg.TZ))  
        return utils.PingResult(changed, msg)
    else: utils.PingResult(False, "")