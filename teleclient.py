from telethon import TelegramClient, events, sync, utils
import tele_secrets
import config as cfg, user_settings as us

client = TelegramClient('bot_session', tele_secrets.api_id, tele_secrets.api_hash)

@client.on(events.NewMessage(chats = [cfg.DTEK_CHANNEL_ID]))
async def newMessageListener(event):
    msg = event.message
    #print("Event Occured")
    if 'відключен' in event.raw_text.lower():
        for user_id in us.user_settings.keys():
            if us.user_settings[user_id]['to_channel'] and us.user_settings[user_id]['channel_id']:
                await client.forward_messages(entity=us.user_settings[user_id]['channel_id'], messages=msg)

with client:
    client.run_until_disconnected()