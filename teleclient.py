from telethon import TelegramClient, events, sync, utils
import tele_secrets
import config as cfg
import bot_secrets

client = TelegramClient('session_name', tele_secrets.api_id, tele_secrets.api_hash)

@client.on(events.NewMessage(chats = [cfg.DTEK_CHANNEL_ID]))
async def handler(event):
    #print("Event Occured")
    if 'відключен' in event.raw_text.lower():
        await client.forward_messages(bot_secrets.ADMIN_ID, event.message)

client.start()
client.run_until_disconnected()