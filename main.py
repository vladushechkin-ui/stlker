# main.py
import asyncio
import logging
import os
import random
from telethon import TelegramClient, events
from telethon.tl.types import PeerChannel

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Конфигурация
API_ID = 34933719
API_HASH = '19fec1ce8a25b608afa68875633715f4'
BOT_TOKEN = '8252577084:AAF6exibor5RKeCL-ob3WRS9in7DVOpbwBY'
SESSION_DIR = 'sessions'

# Создаем папку для сессий
os.makedirs(SESSION_DIR, exist_ok=True)

# Настройки бота
KEYWORDS = ['первый', 'коммент', 'приз', 'конкурс']
COMMENT_LENGTH = (1, 4)  # от 1 до 4 букв
RUSSIAN_LETTERS = 'абвгдеёжзийклмнопрстуфхцчшщъыьэюя'

# Список каналов для мониторинга (замени на свои)
CHANNELS = [
    '@toolsgifts',
    '@FLARS_STARS',
    '@TihiyOmat'
]

async def main():
    # Запускаем клиента (НЕ бота, а пользовательского клиента!)
    # Для автокомментера нужен пользовательский аккаунт, а не бот
    logger.info("Запуск пользовательского клиента...")
    
    # Здесь нужно использовать ТЕЛЕФОН, а не токен бота
    # Например: client = TelegramClient(f'{SESSION_DIR}/user', API_ID, API_HASH)
    # и потом авторизоваться как пользователь
    
    # Но для теста пока оставим бота
    client = TelegramClient(f'{SESSION_DIR}/bot', API_ID, API_HASH)
    await client.start(bot_token=BOT_TOKEN)
    
    logger.info("Клиент запущен!")
    
    @client.on(events.NewMessage)
    async def handler(event):
        try:
            # Проверяем, что это сообщение из канала
            if not isinstance(event.message.peer_id, PeerChannel):
                return
            
            channel_id = event.message.peer_id.channel_id
            post_text = event.message.text or ""
            post_id = event.message.id
            
            logger.info(f"Новый пост в канале {channel_id}: {post_text[:50]}...")
            
            # Проверяем ключевые слова
            for kw in KEYWORDS:
                if kw in post_text.lower():
                    logger.info(f"Найдено ключевое слово: {kw}")
                    
                    # Генерируем комментарий
                    length = random.randint(COMMENT_LENGTH[0], COMMENT_LENGTH[1])
                    comment = ''.join(random.choice(RUSSIAN_LETTERS) for _ in range(length))
                    
                    # Отправляем комментарий
                    await client.send_message(
                        await client.get_entity(channel_id),
                        comment,
                        comment_to=post_id
                    )
                    logger.info(f"Комментарий отправлен: {comment}")
                    break
                    
        except Exception as e:
            logger.error(f"Ошибка: {e}")
    
    @client.on(events.NewMessage(pattern='/start'))
    async def start(event):
        await event.reply('✅ Бот работает на Render!\n\nДля настройки автокомментера нужен пользовательский аккаунт.')
    
    await client.run_until_disconnected()

if __name__ == '__main__':
    asyncio.run(main())
