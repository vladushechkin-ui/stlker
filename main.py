#!/usr/bin/env python3
import asyncio
import os
import logging
from aiohttp import web
from telethon import TelegramClient, events

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

API_ID = 34933719
API_HASH = '19fec1ce8a25b608afa68875633715f4'
BOT_TOKEN = '8252577084:AAF6exibor5RKeCL-ob3WRS9in7DVOpbwBY'
PORT = int(os.environ.get('PORT', 10000))

# Создаем клиента правильно
bot = None

async def init_bot():
    """Инициализация бота внутри async функции"""
    global bot
    bot = await TelegramClient('bot_session', API_ID, API_HASH).start(bot_token=BOT_TOKEN)
    
    @bot.on(events.NewMessage(pattern='/start'))
    async def start(event):
        logger.info(f"Получена команда /start от {event.sender_id}")
        await event.reply("✅ Бот работает на Render! (Исправленная версия)")
    
    logger.info("✅ Бот запущен и слушает команды")
    return bot

async def handle_health(request):
    return web.Response(text="Bot is alive!")

async def main():
    # Запускаем веб-сервер
    app = web.Application()
    app.router.add_get('/', handle_health)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, '0.0.0.0', PORT).start()
    logger.info(f"✅ Веб-сервер запущен на порту {PORT}")

    # Инициализируем бота
    bot = await init_bot()
    
    # Держим программу запущенной
    await bot.run_until_disconnected()

if __name__ == '__main__':
    asyncio.run(main())
