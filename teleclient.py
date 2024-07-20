from telethon import TelegramClient, events, sync, utils
import tele_secrets
import config as cfg, user_settings as us
from datetime import datetime 
import pytz, time

use_tz = pytz.timezone(cfg.TZ)

monitor = TelegramClient('monitor_session', tele_secrets.api_id, tele_secrets.api_hash)
client = TelegramClient('bot_session', tele_secrets.api_id, tele_secrets.api_hash)

monitor.start()

@monitor.on(events.NewMessage(chats = [cfg.DTEK_CHANNEL_ID, '@eSvitloPingHostSource']))
async def newMessageListener(event):
    dt = datetime.now(use_tz)
    msg = event.message
    print(f"{dt} Monitor Event Occured")
    if 'відключен' in event.raw_text.lower():
        await monitor.forward_messages(entity='@eSvitloPingHostBotBuffer', messages=msg)

##client.start()

@client.on(events.NewMessage(chats = ['@eSvitloPingHostBotBuffer']))
async def newMessageSender(event):
    dt = datetime.now(use_tz)
    msg = event.message
    print(f"{dt} Client Event Occured")
    for user_id in us.user_settings.keys():
        try:
            if us.user_settings[user_id]['to_channel'] and us.user_settings[user_id]['channel_id']:
                print(f"{dt} Send to {us.user_settings[user_id]['channel_id']}")
                if str(us.user_settings[user_id]['channel_id']).startswith('-') and str(us.user_settings[user_id]['channel_id'][1:]).isnumeric():
                    await client.forward_messages(entity=int(us.user_settings[user_id]['channel_id']), messages=msg)
                    time.sleep(1)
                else: 
                    await client.forward_messages(entity=us.user_settings[user_id]['channel_id'], messages=msg)
                    time.sleep(1)
        except Exception as e:
            print(f"Error Occured\n{e.with_traceback()}")
    #ensure that messages are sent before deleting
    time.sleep(15)
    await client.delete_messages(entity='t.me/eSvitloPingHostBotBuffer', message_ids=[msg.id])

with client:
    client.run_until_disconnected()

with monitor:
    monitor.run_until_disconnected()