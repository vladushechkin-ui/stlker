import asyncio
import logging
from telethon import TelegramClient, events

# Настройка логирования (чтобы видеть ошибки)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

API_ID = 34933719
API_HASH = '19fec1ce8a25b608afa68875633715f4'
BOT_TOKEN = '8252577084:AAF6exibor5RKeCL-ob3WRS9in7DVOpbwBY'

async def main():
    bot = await TelegramClient('bot', API_ID, API_HASH).start(bot_token=BOT_TOKEN)
    logger.info("Бот успешно запущен!")
    
    @bot.on(events.NewMessage(pattern='/start'))
    async def handler(event):
        await event.reply('✅ Бот работает на Render!')
        logger.info(f"Получена команда /start от {event.sender_id}")
    
    await bot.run_until_disconnected()

if __name__ == '__main__':
    asyncio.run(main())
