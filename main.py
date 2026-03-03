#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
TELEGRAM AUTO COMMENTER - ПОЛНАЯ ВЕРСИЯ ДЛЯ RENDER
Управление через бота, все настройки сохраняются
"""

import asyncio
import logging
import os
import json
import random
import time
from datetime import datetime
from collections import defaultdict
from telethon import TelegramClient, events, Button
from telethon.tl.types import PeerChannel
from telethon.errors import SessionPasswordNeededError, FloodWaitError
from telethon.tl.functions.channels import JoinChannelRequest
from telethon.tl.functions.messages import ImportChatInviteRequest, CheckChatInviteRequest

# ========== НАСТРОЙКИ ==========
API_ID = 34933719
API_HASH = '19fec1ce8a25b608afa68875633715f4'
BOT_TOKEN = '8252577084:AAF6exibor5RKeCL-ob3WRS9in7DVOpbwBY'
SESSION_DIR = 'sessions'
CONFIG_FILE = 'config.json'
CHANNELS_FILE = 'channels.json'
# ================================

# Создаем папки
os.makedirs(SESSION_DIR, exist_ok=True)

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

RUSSIAN_LETTERS = 'абвгдеёжзийклмнопрстуфхцчшщъыьэюя'

# ========== КЛАСС ДЛЯ РАБОТЫ С КАНАЛАМИ ==========
class ChannelManager:
    def __init__(self):
        self.channels = []
        self.channel_ids = []
        self.channel_names = {}
        self.invite_links = {}
        self.load_channels()
    
    def load_channels(self):
        """Загружает каналы из файла"""
        if os.path.exists(CHANNELS_FILE):
            try:
                with open(CHANNELS_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                self.channels = data.get('channels', [])
                self.channel_ids = data.get('channel_ids', [])
                self.channel_names = data.get('channel_names', {})
                self.invite_links = data.get('invite_links', {})
                logger.info(f"✅ Загружено {len(self.channels)} каналов")
            except Exception as e:
                logger.error(f"❌ Ошибка загрузки каналов: {e}")
                self._init_default()
        else:
            self._init_default()
    
    def _init_default(self):
        """Инициализация с каналами по умолчанию"""
        self.channels = [
            "@toolsgifts",
            "@FLARS_STARS",
            "@TihiyOmat",
            "@kartavayauaby",
            "@nftafrom",
            "@egortooosqq",
            "@starsovshop",
            "@lekstars",
            "@stars_kitti",
            "@tonznatok"
        ]
        self.save_channels()
    
    def save_channels(self):
        """Сохраняет каналы в файл"""
        try:
            data = {
                'channels': self.channels,
                'channel_ids': self.channel_ids,
                'channel_names': self.channel_names,
                'invite_links': self.invite_links
            }
            with open(CHANNELS_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.info("✅ Каналы сохранены")
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения каналов: {e}")
    
    def add_channel(self, name, channel_id=None, invite_link=None):
        """Добавляет канал"""
        if name not in self.channels:
            self.channels.append(name)
            if channel_id:
                self.channel_ids.append(channel_id)
                self.channel_names[str(channel_id)] = name
            if invite_link:
                self.invite_links[name] = invite_link
            self.save_channels()
            return True
        return False
    
    def remove_channel(self, name):
        """Удаляет канал"""
        if name in self.channels:
            self.channels.remove(name)
            # Очищаем связанные данные
            for cid, cname in list(self.channel_names.items()):
                if cname == name:
                    if int(cid) in self.channel_ids:
                        self.channel_ids.remove(int(cid))
                    del self.channel_names[cid]
            if name in self.invite_links:
                del self.invite_links[name]
            self.save_channels()
            return True
        return False

# ========== КЛАСС ДЛЯ НАСТРОЕК ==========
class SettingsManager:
    def __init__(self):
        self.keywords = ['первый', 'коммент', 'приз', 'конкурс', 'gift', 'розыгрыш', 'раздача']
        self.comment_length = (1, 4)
        self.delay_between = (2, 5)
        self.comment_mode = 'random'
        self.stats = {'comments': 0, 'by_account': {}, 'by_channel': {}}
        self.load_settings()
    
    def load_settings(self):
        """Загружает настройки из файла"""
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                self.keywords = data.get('keywords', self.keywords)
                self.comment_length = tuple(data.get('comment_length', self.comment_length))
                self.delay_between = tuple(data.get('delay_between', self.delay_between))
                self.comment_mode = data.get('comment_mode', self.comment_mode)
                self.stats = data.get('stats', self.stats)
                logger.info("✅ Настройки загружены")
            except Exception as e:
                logger.error(f"❌ Ошибка загрузки настроек: {e}")
    
    def save_settings(self):
        """Сохраняет настройки в файл"""
        try:
            data = {
                'keywords': self.keywords,
                'comment_length': list(self.comment_length),
                'delay_between': list(self.delay_between),
                'comment_mode': self.comment_mode,
                'stats': self.stats
            }
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.info("✅ Настройки сохранены")
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения настроек: {e}")
    
    def add_comment(self, account, channel):
        """Добавляет статистику комментария"""
        self.stats['comments'] += 1
        self.stats['by_account'][account] = self.stats['by_account'].get(account, 0) + 1
        self.stats['by_channel'][channel] = self.stats['by_channel'].get(channel, 0) + 1
        self.save_settings()

# ========== ОСНОВНОЙ КЛАСС БОТА ==========
class AutoCommenterBot:
    def __init__(self):
        self.user_clients = {}  # {phone: client}
        self.bot_client = None
        self.channels = ChannelManager()
        self.settings = SettingsManager()
        self.monitoring = False
        self.last_post_ids = {}
        self.handler = None
        self.waiting_for = {}  # Ожидание ввода от пользователей
        
    async def start(self):
        """Запускает всех клиентов"""
        logger.info("🚀 Запуск бота...")
        
        # Запускаем бота-управлятора
        await self.start_bot()
        
        # Загружаем пользовательские сессии
        await self.load_user_sessions()
        
        # Запускаем мониторинг если есть аккаунты и каналы
        if self.user_clients and self.channels.channels:
            await self.start_monitoring()
        
        logger.info("✅ Бот готов к работе!")
    
    async def start_bot(self):
        """Запускает бота-управлятора"""
        try:
            self.bot_client = TelegramClient(f'{SESSION_DIR}/manager', API_ID, API_HASH)
            await self.bot_client.start(bot_token=BOT_TOKEN)
            logger.info("✅ Бот-управлятор запущен")
            
            # Регистрируем обработчики
            @self.bot_client.on(events.NewMessage)
            async def message_handler(event):
                await self.handle_message(event)
            
            @self.bot_client.on(events.CallbackQuery)
            async def callback_handler(event):
                await self.handle_callback(event)
                
        except Exception as e:
            logger.error(f"❌ Ошибка запуска бота: {e}")
    
    async def load_user_sessions(self):
        """Загружает существующие пользовательские сессии"""
        for f in os.listdir(SESSION_DIR):
            if f.endswith('.session') and not f.startswith('manager'):
                phone = f.replace('.session', '')
                try:
                    client = TelegramClient(f'{SESSION_DIR}/{phone}', API_ID, API_HASH)
                    await client.connect()
                    if await client.is_user_authorized():
                        self.user_clients[phone] = client
                        logger.info(f"✅ Загружен аккаунт: {phone[-4:]}")
                except Exception as e:
                    logger.error(f"❌ Ошибка загрузки {phone}: {e}")
    
    async def add_user_account(self, phone, code_callback, password_callback):
        """Добавляет пользовательский аккаунт"""
        try:
            client = TelegramClient(f'{SESSION_DIR}/{phone}', API_ID, API_HASH)
            await client.connect()
            
            if not await client.is_user_authorized():
                await client.send_code_request(phone)
                code = await code_callback()
                if not code:
                    return False
                try:
                    await client.sign_in(phone, code)
                except SessionPasswordNeededError:
                    pwd = await password_callback()
                    if not pwd:
                        return False
                    await client.sign_in(password=pwd)
            
            self.user_clients[phone] = client
            logger.info(f"✅ Аккаунт {phone[-4:]} добавлен")
            
            # Подписываем на все каналы
            await self.join_all_channels(phone)
            
            # Перезапускаем мониторинг
            await self.restart_monitoring()
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка добавления аккаунта: {e}")
            return False
    
    async def join_all_channels(self, phone):
        """Подписывает аккаунт на все каналы"""
        if phone not in self.user_clients:
            return
        
        client = self.user_clients[phone]
        
        for channel_name in self.channels.channels:
            try:
                if channel_name in self.channels.invite_links:
                    # Приватный канал
                    invite = self.channels.invite_links[channel_name]
                    try:
                        if 'joinchat' in invite:
                            hash_part = invite.split('joinchat/')[-1]
                        elif 't.me/+' in invite:
                            hash_part = invite.split('t.me/+')[-1]
                        else:
                            hash_part = invite
                        await client(ImportChatInviteRequest(hash=hash_part))
                        logger.info(f"✅ {phone[-4:]} присоединился к {channel_name}")
                    except Exception as e:
                        logger.info(f"⚠️ {phone[-4:]} уже в {channel_name}")
                else:
                    # Публичный канал
                    try:
                        entity = await client.get_entity(channel_name)
                        if hasattr(entity, 'broadcast'):
                            try:
                                await client(JoinChannelRequest(entity))
                                logger.info(f"✅ {phone[-4:]} подписался на {channel_name}")
                            except:
                                logger.info(f"⚠️ {phone[-4:]} уже подписан")
                    except Exception as e:
                        logger.error(f"❌ Ошибка подписки: {e}")
                
                await asyncio.sleep(1)
            except Exception as e:
                logger.error(f"❌ Ошибка: {e}")
    
    async def add_channel(self, channel_input):
        """Добавляет канал"""
        if not self.user_clients:
            return False, "❌ Нет пользовательских аккаунтов"
        
        channel_input = channel_input.strip()
        is_invite = 't.me/+' in channel_input or 'joinchat' in channel_input
        
        if not is_invite:
            if channel_input.startswith('https://'):
                channel_input = '@' + channel_input.split('/')[-1]
            elif not channel_input.startswith('@'):
                channel_input = '@' + channel_input
        
        logger.info(f"🔍 Добавляю канал: {channel_input}")
        
        # Подписываем все аккаунты
        entity = None
        channel_name = None
        invite_link = None
        
        for phone, client in self.user_clients.items():
            try:
                if is_invite:
                    # Приватный канал
                    if 'joinchat' in channel_input:
                        hash_part = channel_input.split('joinchat/')[-1]
                    elif 't.me/+' in channel_input:
                        hash_part = channel_input.split('t.me/+')[-1]
                    else:
                        hash_part = channel_input
                    
                    try:
                        updates = await client(CheckChatInviteRequest(hash=hash_part))
                        if hasattr(updates, 'chat'):
                            result = await client(ImportChatInviteRequest(hash=hash_part))
                            if hasattr(result, 'chats') and result.chats:
                                channel = result.chats[0]
                                logger.info(f"✅ {phone[-4:]} присоединился")
                                
                                if entity is None:
                                    entity = channel
                                    if hasattr(channel, 'username') and channel.username:
                                        channel_name = f"@{channel.username}"
                                    else:
                                        channel_name = f"🔐 {channel.title}"
                                    invite_link = channel_input
                    except Exception as e:
                        logger.info(f"⚠️ {phone[-4:]} уже в канале")
                else:
                    # Публичный канал
                    entity = await client.get_entity(channel_input)
                    if entity and hasattr(entity, 'broadcast'):
                        try:
                            await client(JoinChannelRequest(entity))
                            logger.info(f"✅ {phone[-4:]} подписался")
                        except:
                            logger.info(f"⚠️ {phone[-4:]} уже подписан")
                    
                    if phone == list(self.user_clients.keys())[0]:
                        channel_name = channel_input
            except Exception as e:
                logger.error(f"❌ Ошибка: {e}")
        
        if not entity:
            return False, "❌ Не удалось добавить канал"
        
        # Сохраняем канал
        channel_id = entity.id
        self.channels.add_channel(channel_name, channel_id, invite_link)
        
        # Обновляем список ID для мониторинга
        if channel_id not in self.channels.channel_ids:
            self.channels.channel_ids.append(channel_id)
        
        await self.restart_monitoring()
        return True, f"✅ Канал добавлен: {channel_name}"
    
    async def restart_monitoring(self):
        """Перезапускает мониторинг"""
        if self.handler and self.user_clients:
            try:
                client = list(self.user_clients.values())[0]
                client.remove_event_handler(self.handler)
            except:
                pass
            self.handler = None
        
        self.monitoring = False
        await asyncio.sleep(1)
        await self.start_monitoring()
    
    async def start_monitoring(self):
        """Запускает мониторинг каналов"""
        if not self.user_clients or not self.channels.channels:
            logger.warning("❌ Нет аккаунтов или каналов")
            return False
        
        self.monitoring = True
        logger.info("🚀 Запуск мониторинга...")
        
        # Используем первый аккаунт для мониторинга
        client = list(self.user_clients.values())[0]
        
        if not self.channels.channel_ids:
            logger.warning("❌ Нет ID каналов")
            self.monitoring = False
            return False
        
        logger.info(f"📡 Отслеживается каналов: {len(self.channels.channel_ids)}")
        
        @client.on(events.NewMessage(chats=self.channels.channel_ids))
        async def handler(event):
            try:
                if not isinstance(event.message.peer_id, PeerChannel):
                    return
                
                channel_id = event.message.peer_id.channel_id
                channel_name = self.channels.channel_names.get(str(channel_id), "Unknown")
                
                # Проверяем дубликаты
                if channel_id in self.last_post_ids:
                    if self.last_post_ids[channel_id] >= event.message.id:
                        return
                
                self.last_post_ids[channel_id] = event.message.id
                
                post_text = event.message.text or ""
                logger.info(f"📢 Новый пост в {channel_name}")
                
                # Проверяем ключевые слова
                post_lower = post_text.lower()
                found = [kw for kw in self.settings.keywords if kw.lower() in post_lower]
                
                if found:
                    logger.info(f"✅ Найдены ключевые слова: {found}")
                    await self.comment_on_post(channel_id, event.message.id, channel_name)
                    
            except Exception as e:
                logger.error(f"❌ Ошибка в обработчике: {e}")
        
        self.handler = handler
        logger.info(f"✅ Мониторинг активен")
        return True
    
    async def comment_on_post(self, channel_id, post_id, channel_name):
        """Отправляет комментарий на пост"""
        try:
            # Выбираем аккаунты для комментариев
            accounts = list(self.user_clients.keys())
            if not accounts:
                return
            
            accounts_to_use = []
            if self.settings.comment_mode == "random":
                accounts_to_use = [random.choice(accounts)]
            elif self.settings.comment_mode == "all":
                accounts_to_use = accounts
            elif self.settings.comment_mode == "round_robin":
                # По очереди (простая реализация)
                accounts_to_use = [accounts[0]]
            
            # Получаем entity канала
            client = list(self.user_clients.values())[0]
            entity = await client.get_entity(channel_id)
            
            for phone in accounts_to_use:
                client = self.user_clients[phone]
                
                # Генерируем комментарий
                length = random.randint(self.settings.comment_length[0], self.settings.comment_length[1])
                comment = ''.join(random.choice(RUSSIAN_LETTERS) for _ in range(length))
                
                try:
                    await client.send_message(entity, comment, comment_to=post_id)
                    logger.info(f"✅ {phone[-4:]} отправил: '{comment}'")
                    
                    # Обновляем статистику
                    self.settings.add_comment(phone[-4:], channel_name)
                    
                    # Задержка
                    delay = random.uniform(self.settings.delay_between[0], self.settings.delay_between[1])
                    await asyncio.sleep(delay)
                    
                except FloodWaitError as e:
                    logger.warning(f"⏳ Flood wait {e.seconds}с")
                    await asyncio.sleep(e.seconds)
                except Exception as e:
                    logger.error(f"❌ Ошибка отправки: {e}")
                    
        except Exception as e:
            logger.error(f"❌ Ошибка в comment_on_post: {e}")
    
    # ========== ОБРАБОТЧИКИ БОТА ==========
    
    async def handle_message(self, event):
        """Обрабатывает сообщения"""
        if event.message.text:
            user_id = event.sender_id
            
            # Проверяем ожидание ввода
            if user_id in self.waiting_for:
                await self.handle_input(event)
                return
            
            if event.message.text.startswith('/'):
                await self.handle_command(event)
            else:
                await event.reply("🤖 Используйте кнопки для управления:", buttons=self.main_menu())
    
    async def handle_command(self, event):
        """Обрабатывает команды"""
        cmd = event.message.text.lower()
        
        if cmd == '/start' or cmd == '/menu':
            await event.reply(
                "🤖 *Telegram Auto Commenter*\n\n"
                "Бот для автоматических комментариев в Telegram каналах.\n"
                "Используйте кнопки для управления.",
                buttons=self.main_menu(),
                parse_mode='markdown'
            )
        elif cmd == '/help':
            await event.reply(
                "❓ *Помощь*\n\n"
                "Используйте кнопки меню для управления ботом.\n"
                "Основные функции:\n"
                "• Добавление аккаунтов\n"
                "• Управление каналами\n"
                "• Настройка комментариев\n"
                "• Просмотр статистики",
                buttons=self.main_menu(),
                parse_mode='markdown'
            )
    
    async def handle_callback(self, event):
        """Обрабатывает нажатия на кнопки"""
        data = event.data.decode('utf-8')
        user_id = event.sender_id
        
        # Главное меню
        if data == "main_menu":
            await event.edit(
                "🤖 Главное меню:",
                buttons=self.main_menu()
            )
        
        # Статистика
        elif data == "stats":
            text = self.format_stats()
            await event.edit(text, buttons=self.main_menu(), parse_mode='markdown')
        
        # Аккаунты
        elif data == "accounts":
            text = self.format_accounts()
            await event.edit(text, buttons=self.accounts_menu(), parse_mode='markdown')
        
        # Добавить аккаунт
        elif data == "add_account":
            self.waiting_for[user_id] = "add_account"
            await event.edit(
                "📱 Отправьте номер телефона в формате:\n"
                "`+79123456789`\n\n"
                "Или нажмите Отмена для возврата.",
                buttons=[[Button.inline("◀️ Отмена", data="main_menu")]],
                parse_mode='markdown'
            )
        
        # Каналы
        elif data == "channels":
            text = self.format_channels()
            await event.edit(text, buttons=self.channels_menu(), parse_mode='markdown')
        
        # Добавить канал
        elif data == "add_channel":
            self.waiting_for[user_id] = "add_channel"
            await event.edit(
                "➕ Отправьте ссылку или username канала:\n\n"
                "Примеры:\n"
                "• `@channel`\n"
                "• `https://t.me/channel`\n"
                "• `https://t.me/+XXXXXXXXXX` (приватный)",
                buttons=[[Button.inline("◀️ Отмена", data="main_menu")]],
                parse_mode='markdown'
            )
        
        # Удалить канал
        elif data == "remove_channel":
            if not self.channels.channels:
                await event.answer("❌ Нет каналов для удаления")
                await event.edit(
                    self.format_channels(),
                    buttons=self.channels_menu(),
                    parse_mode='markdown'
                )
                return
            
            # Создаем кнопки с каналами
            buttons = []
            for i, ch in enumerate(self.channels.channels[:10], 1):
                short = ch[:20] + "..." if len(ch) > 20 else ch
                buttons.append([Button.inline(f"❌ {i}. {short}", data=f"del_{ch}")])
            
            buttons.append([Button.inline("◀️ Назад", data="channels")])
            
            await event.edit(
                f"🗑 Выберите канал для удаления (всего: {len(self.channels.channels)}):",
                buttons=buttons
            )
        
        # Подтверждение удаления
        elif data.startswith("del_"):
            channel_name = data[4:]
            self.waiting_for[user_id] = f"confirm_del_{channel_name}"
            await event.edit(
                f"❓ Удалить канал {channel_name}?",
                buttons=[
                    [Button.inline("✅ Да", data=f"confirm_{channel_name}"),
                     Button.inline("❌ Нет", data="channels")],
                    [Button.inline("◀️ Назад", data="channels")]
                ]
            )
        
        elif data.startswith("confirm_"):
            channel_name = data[8:]
            if self.channels.remove_channel(channel_name):
                await event.answer("✅ Канал удален")
            else:
                await event.answer("❌ Ошибка удаления")
            
            await event.edit(
                self.format_channels(),
                buttons=self.channels_menu(),
                parse_mode='markdown'
            )
        
        # Настройки
        elif data == "settings":
            text = self.format_settings()
            await event.edit(text, buttons=self.settings_menu(), parse_mode='markdown')
        
        # Ключевые слова
        elif data == "keywords":
            self.waiting_for[user_id] = "keywords"
            await event.edit(
                "📝 Введите ключевые слова через запятую\n\n"
                f"Текущие: {', '.join(self.settings.keywords[:5])}...\n\n"
                "Пример: первый,приз,конкурс,gift",
                buttons=[[Button.inline("◀️ Отмена", data="settings")]]
            )
        
        # Задержка
        elif data == "delay":
            self.waiting_for[user_id] = "delay"
            await event.edit(
                f"⏱ Введите минимальную и максимальную задержку через пробел\n\n"
                f"Текущая: {self.settings.delay_between[0]}-{self.settings.delay_between[1]} сек\n\n"
                "Пример: 2 5",
                buttons=[[Button.inline("◀️ Отмена", data="settings")]]
            )
        
        # Длина комментария
        elif data == "length":
            self.waiting_for[user_id] = "length"
            await event.edit(
                f"📏 Введите минимальную и максимальную длину через пробел\n\n"
                f"Текущая: {self.settings.comment_length[0]}-{self.settings.comment_length[1]} символов\n\n"
                "Пример: 1 4",
                buttons=[[Button.inline("◀️ Отмена", data="settings")]]
            )
        
        # Режим
        elif data == "mode":
            await event.edit(
                "🎲 Выберите режим отправки:",
                buttons=[
                    [Button.inline("🎲 Случайный", data="mode_random"),
                     Button.inline("👥 Все", data="mode_all")],
                    [Button.inline("🔄 По очереди", data="mode_round"),
                     Button.inline("◀️ Назад", data="settings")]
                ]
            )
        
        elif data == "mode_random":
            self.settings.comment_mode = "random"
            self.settings.save_settings()
            await event.answer("✅ Режим: Случайный")
            await event.edit(
                self.format_settings(),
                buttons=self.settings_menu(),
                parse_mode='markdown'
            )
        
        elif data == "mode_all":
            self.settings.comment_mode = "all"
            self.settings.save_settings()
            await event.answer("✅ Режим: Все аккаунты")
            await event.edit(
                self.format_settings(),
                buttons=self.settings_menu(),
                parse_mode='markdown'
            )
        
        elif data == "mode_round":
            self.settings.comment_mode = "round_robin"
            self.settings.save_settings()
            await event.answer("✅ Режим: По очереди")
            await event.edit(
                self.format_settings(),
                buttons=self.settings_menu(),
                parse_mode='markdown'
            )
        
        # Управление мониторингом
        elif data == "start_monitor":
            if not self.user_clients:
                await event.answer("❌ Нет аккаунтов")
                return
            if not self.channels.channels:
                await event.answer("❌ Нет каналов")
                return
            
            await self.restart_monitoring()
            await event.answer("✅ Мониторинг запущен")
            await event.edit(
                "✅ Мониторинг запущен!\n\n" + self.format_status(),
                buttons=self.main_menu(),
                parse_mode='markdown'
            )
        
        elif data == "stop_monitor":
            self.monitoring = False
            await event.answer("⏸️ Мониторинг остановлен")
            await event.edit(
                "⏸️ Мониторинг остановлен\n\n" + self.format_status(),
                buttons=self.main_menu(),
                parse_mode='markdown'
            )
        
        elif data == "restart_monitor":
            await event.answer("🔄 Перезапускаю...")
            await self.restart_monitoring()
            await event.edit(
                "🔄 Мониторинг перезапущен\n\n" + self.format_status(),
                buttons=self.main_menu(),
                parse_mode='markdown'
            )
    
    async def handle_input(self, event):
        """Обрабатывает ввод от пользователя"""
        user_id = event.sender_id
        action = self.waiting_for[user_id]
        text = event.message.text.strip()
        
        if action == "add_account":
            # Здесь нужно реализовать процесс авторизации
            await event.reply(
                "📱 Функция добавления аккаунта через бота в разработке.\n"
                "Пока добавьте аккаунт вручную через файловую систему.",
                buttons=self.main_menu()
            )
            del self.waiting_for[user_id]
        
        elif action == "add_channel":
            success, msg = await self.add_channel(text)
            await event.reply(msg, buttons=self.channels_menu())
            del self.waiting_for[user_id]
        
        elif action == "keywords":
            keywords = [k.strip() for k in text.split(',') if k.strip()]
            if keywords:
                self.settings.keywords = keywords
                self.settings.save_settings()
                await event.reply(
                    f"✅ Ключевые слова обновлены:\n{', '.join(keywords[:10])}",
                    buttons=self.settings_menu()
                )
            else:
                await event.reply("❌ Некорректный ввод", buttons=self.settings_menu())
            del self.waiting_for[user_id]
        
        elif action == "delay":
            parts = text.split()
            if len(parts) == 2:
                try:
                    min_d = int(parts[0])
                    max_d = int(parts[1])
                    if 1 <= min_d <= max_d <= 60:
                        self.settings.delay_between = (min_d, max_d)
                        self.settings.save_settings()
                        await event.reply(
                            f"✅ Задержка установлена: {min_d}-{max_d} сек",
                            buttons=self.settings_menu()
                        )
                    else:
                        await event.reply(
                            "❌ Значения должны быть от 1 до 60",
                            buttons=self.settings_menu()
                        )
                except:
                    await event.reply("❌ Введите два числа", buttons=self.settings_menu())
            else:
                await event.reply("❌ Пример: 2 5", buttons=self.settings_menu())
            del self.waiting_for[user_id]
        
        elif action == "length":
            parts = text.split()
            if len(parts) == 2:
                try:
                    min_l = int(parts[0])
                    max_l = int(parts[1])
                    if 1 <= min_l <= max_l <= 20:
                        self.settings.comment_length = (min_l, max_l)
                        self.settings.save_settings()
                        await event.reply(
                            f"✅ Длина установлена: {min_l}-{max_l} символов",
                            buttons=self.settings_menu()
                        )
                    else:
                        await event.reply(
                            "❌ Значения должны быть от 1 до 20",
                            buttons=self.settings_menu()
                        )
                except:
                    await event.reply("❌ Введите два числа", buttons=self.settings_menu())
            else:
                await event.reply("❌ Пример: 1 4", buttons=self.settings_menu())
            del self.waiting_for[user_id]
    
    # ========== МЕНЮ ==========
    
    def main_menu(self):
        """Главное меню"""
        return [
            [Button.inline("📊 Статистика", data="stats"),
             Button.inline("📱 Аккаунты", data="accounts")],
            [Button.inline("📺 Каналы", data="channels"),
             Button.inline("⚙️ Настройки", data="settings")],
            [Button.inline("▶️ Запуск", data="start_monitor"),
             Button.inline("⏸️ Стоп", data="stop_monitor")],
            [Button.inline("🔄 Перезапуск", data="restart_monitor")]
        ]
    
    def accounts_menu(self):
        """Меню аккаунтов"""
        return [
            [Button.inline("➕ Добавить", data="add_account")],
            [Button.inline("◀️ Назад", data="main_menu")]
        ]
    
    def channels_menu(self):
        """Меню каналов"""
        return [
            [Button.inline("➕ Добавить", data="add_channel"),
             Button.inline("➖ Удалить", data="remove_channel")],
            [Button.inline("◀️ Назад", data="main_menu")]
        ]
    
    def settings_menu(self):
        """Меню настроек"""
        return [
            [Button.inline("📝 Ключевые слова", data="keywords"),
             Button.inline("⏱ Задержка", data="delay")],
            [Button.inline("📏 Длина", data="length"),
             Button.inline("🎲 Режим", data="mode")],
            [Button.inline("◀️ Назад", data="main_menu")]
        ]
    
    # ========== ФОРМАТИРОВАНИЕ ==========
    
    def format_status(self):
        """Форматирует статус"""
        monitoring = "✅ АКТИВЕН" if self.monitoring else "❌ ОСТАНОВЛЕН"
        mode_names = {
            'random': '🎲 Случайный',
            'all': '👥 Все',
            'round_robin': '🔄 По очереди'
        }
        return (
            f"📊 *ТЕКУЩИЙ СТАТУС*\n\n"
            f"Мониторинг: {monitoring}\n"
            f"Аккаунтов: {len(self.user_clients)}\n"
            f"Каналов: {len(self.channels.channels)}\n"
            f"Комментариев: {self.settings.stats['comments']}\n\n"
            f"🎯 Режим: {mode_names.get(self.settings.comment_mode, self.settings.comment_mode)}"
        )
    
    def format_stats(self):
        """Форматирует статистику"""
        text = "📈 *СТАТИСТИКА*\n\n"
        
        text += "*По аккаунтам:*\n"
        if self.settings.stats['by_account']:
            for acc, cnt in self.settings.stats['by_account'].items():
                text += f"📱 {acc}: {cnt} комм\n"
        else:
            text += "Нет данных\n"
        
        text += "\n*По каналам (топ 5):*\n"
        if self.settings.stats['by_channel']:
            sorted_channels = sorted(self.settings.stats['by_channel'].items(), key=lambda x: x[1], reverse=True)[:5]
            for ch, cnt in sorted_channels:
                short = ch[:20] + "..." if len(ch) > 20 else ch
                text += f"📺 {short}: {cnt}\n"
        else:
            text += "Нет данных\n"
        
        text += f"\n📊 *Всего:* {self.settings.stats['comments']}"
        return text
    
    def format_accounts(self):
        """Форматирует список аккаунтов"""
        if not self.user_clients:
            return "📱 *АККАУНТЫ*\n\n❌ Нет добавленных аккаунтов"
        
        text = f"📱 *АККАУНТЫ ({len(self.user_clients)})*\n\n"
        
        for i, phone in enumerate(self.user_clients.keys(), 1):
            comments = self.settings.stats['by_account'].get(phone[-4:], 0)
            text += f"{i}. 📱 `{phone[-4:]}`: {comments} комм\n"
        
        return text
    
    def format_channels(self):
        """Форматирует список каналов"""
        if not self.channels.channels:
            return "📺 *КАНАЛЫ*\n\n❌ Нет добавленных каналов"
        
        text = f"📺 *КАНАЛЫ ({len(self.channels.channels)})*\n\n"
        
        for i, ch in enumerate(self.channels.channels, 1):
            comments = self.settings.stats['by_channel'].get(ch, 0)
            ch_type = "🔐" if ch.startswith('🔐') else "🌐"
            short = ch[:30] + "..." if len(ch) > 30 else ch
            text += f"{i}. {ch_type} {short}: {comments} комм\n"
        
        return text
    
    def format_settings(self):
        """Форматирует настройки"""
        mode_names = {
            'random': '🎲 Случайный',
            'all': '👥 Все',
            'round_robin': '🔄 По очереди'
        }
        
        keywords_text = ', '.join(self.settings.keywords[:5])
        if len(self.settings.keywords) > 5:
            keywords_text += f" и еще {len(self.settings.keywords) - 5}"
        
        return (
            f"⚙️ *ТЕКУЩИЕ НАСТРОЙКИ*\n\n"
            f"📝 Ключевые слова: {keywords_text}\n"
            f"⏱ Задержка: {self.settings.delay_between[0]}-{self.settings.delay_between[1]} сек\n"
            f"📏 Длина коммента: {self.settings.comment_length[0]}-{self.settings.comment_length[1]} симв\n"
            f"🎯 Режим: {mode_names.get(self.settings.comment_mode, self.settings.comment_mode)}"
        )
    
    async def run_forever(self):
        """Запускает бота навсегда"""
        await self.start()
        await asyncio.Event().wait()

# ========== ЗАПУСК ==========
async def main():
    bot = AutoCommenterBot()
    await bot.run_forever()

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("👋 Бот остановлен")
