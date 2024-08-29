from telethon import TelegramClient, events, sync, utils
import tele_secrets
import config as cfg, user_settings as us
from datetime import datetime 
import logging, traceback
from logging.handlers import TimedRotatingFileHandler
import pytz, time

# Create a logger
logger = logging.getLogger('teleclient')
logger.setLevel(logging.DEBUG)

# Create a file handler
fh = TimedRotatingFileHandler('./logs/teleclient.log', encoding='utf-8', when="D", interval=1, backupCount=30)
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

use_tz = pytz.timezone(cfg.TZ)

monitor = TelegramClient('monitor_session', tele_secrets.api_id, tele_secrets.api_hash)
client  = TelegramClient('bot_session', tele_secrets.api_id, tele_secrets.api_hash)

monitor.start()

@monitor.on(events.NewMessage(chats = [cfg.DTEK_CHANNEL_ID, '@eSvitloPingHostSource']))
async def newMessageListener(event):
    dt = datetime.now(use_tz)
    msg = event.message
    logger.info(f"{dt} Monitor Event Occured")
    if 'відключен' in event.raw_text.lower():
        await monitor.forward_messages(entity='@eSvitloPingHostBotBuffer', messages=msg)

##client.start()

@client.on(events.NewMessage(chats = ['@eSvitloPingHostBotBuffer']))
async def newMessageSender(event):
    msg = event.message
    logger.info("Client Event Occured")
    users = dict(us.user_settings)
    for user_id in users.keys():
        logger.info(f"Check for broadcast {user_id}")
        try:
            if us.user_settings[user_id]['to_channel'] and us.user_settings[user_id]['channel_id']:
                logger.info(f"{datetime.now(use_tz)} Send to {us.user_settings[user_id]['channel_id']}")
                if str(us.user_settings[user_id]['channel_id']).startswith('-') and str(us.user_settings[user_id]['channel_id'])[1:].isnumeric():
                    await client.forward_messages(entity=int(us.user_settings[user_id]['channel_id']), messages=msg)
                    #time.sleep(1)
                else: 
                    await client.forward_messages(entity=us.user_settings[user_id]['channel_id'], messages=msg)
                    #time.sleep(1)
            else:
                logger.info(f"Nowhere to sent for {user_id}")
        except Exception as e:
            logger.error(f"Error occured while sending\n{traceback.format_exc()}")
            continue
    #ensure that messages are sent before deleting
    logger.info("All users are checked, waiting to purge the buffer")
    time.sleep(15)
    logger.info("Purge the buffer")
    try:
        await client.delete_messages(entity='t.me/eSvitloPingHostBotBuffer', message_ids=[msg.id])
    except Exception as e:
            logger.error(f"Error while deleting\n{traceback.format_exc()}")

with client:
    client.run_until_disconnected()

with monitor:
    monitor.run_until_disconnected()