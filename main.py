#!/usr/bin/env python3
import asyncio
import os
import json
import logging
import random
from datetime import datetime
from aiohttp import web
from telethon import TelegramClient, events, Button
from telethon.tl.types import PeerChannel
from telethon.errors import FloodWaitError
from telethon.tl.functions.channels import JoinChannelRequest
from telethon.tl.functions.messages import ImportChatInviteRequest, CheckChatInviteRequest

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ========== НАСТРОЙКИ ==========
API_ID = 34933719
API_HASH = '19fec1ce8a25b608afa68875633715f4'
BOT_TOKEN = '8252577084:AAF6exibor5RKeCL-ob3WRS9in7DVOpbwBY'
PORT = int(os.environ.get('PORT', 10000))
CONFIG_FILE = 'config.json'
CHANNELS_FILE = 'channels.json'
SESSION_DIR = 'sessions'
# ================================

os.makedirs(SESSION_DIR, exist_ok=True)
RUSSIAN_LETTERS = 'абвгдеёжзийклмнопрстуфхцчшщъыьэюя'

# ========== КЛАССЫ ДЛЯ ДАННЫХ ==========
class Storage:
    def __init__(self):
        self.channels = []
        self.channel_ids = []
        self.channel_names = {}
        self.invite_links = {}
        self.keywords = ['первый', 'коммент', 'приз', 'конкурс', 'gift']
        self.comment_length = (1, 4)
        self.delay_between = (2, 5)
        self.comment_mode = 'random'
        self.stats = {'comments': 0, 'by_account': {}, 'by_channel': {}}
        self.load_all()
    
    def load_all(self):
        # Загрузка каналов
        if os.path.exists(CHANNELS_FILE):
            try:
                with open(CHANNELS_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                self.channels = data.get('channels', [])
                self.channel_ids = data.get('channel_ids', [])
                self.channel_names = data.get('channel_names', {})
                self.invite_links = data.get('invite_links', {})
            except: pass
        
        # Загрузка настроек
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                self.keywords = data.get('keywords', self.keywords)
                self.comment_length = tuple(data.get('comment_length', self.comment_length))
                self.delay_between = tuple(data.get('delay_between', self.delay_between))
                self.comment_mode = data.get('comment_mode', self.comment_mode)
                self.stats = data.get('stats', self.stats)
            except: pass
    
    def save_channels(self):
        try:
            with open(CHANNELS_FILE, 'w', encoding='utf-8') as f:
                json.dump({
                    'channels': self.channels,
                    'channel_ids': self.channel_ids,
                    'channel_names': self.channel_names,
                    'invite_links': self.invite_links
                }, f, ensure_ascii=False, indent=2)
        except: pass
    
    def save_settings(self):
        try:
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump({
                    'keywords': self.keywords,
                    'comment_length': list(self.comment_length),
                    'delay_between': list(self.delay_between),
                    'comment_mode': self.comment_mode,
                    'stats': self.stats
                }, f, ensure_ascii=False, indent=2)
        except: pass

# ========== ОСНОВНОЙ КЛАСС ==========
class AutoCommenterBot:
    def __init__(self):
        self.storage = Storage()
        self.bot = None
        self.user_clients = {}
        self.monitoring = False
        self.last_post_ids = {}
        self.handler = None
        self.waiting_for = {}
    
    async def start(self):
        # Запуск веб-сервера для Render
        app = web.Application()
        app.router.add_get('/', lambda r: web.Response(text="Bot is running!"))
        runner = web.AppRunner(app)
        await runner.setup()
        await web.TCPSite(runner, '0.0.0.0', PORT).start()
        logger.info("✅ Веб-сервер запущен")
        
        # Запуск бота-управлятора
        self.bot = await TelegramClient(f'{SESSION_DIR}/manager', API_ID, API_HASH).start(bot_token=BOT_TOKEN)
        logger.info("✅ Бот-управлятор запущен")
        
        # Регистрация обработчиков
        @self.bot.on(events.NewMessage)
        async def msg_handler(e):
            await self.handle_message(e)
        
        @self.bot.on(events.CallbackQuery)
        async def callback_handler(e):
            await self.handle_callback(e)
        
        # Загрузка пользовательских аккаунтов
        await self.load_user_sessions()
        
        # Запуск мониторинга если есть аккаунты
        if self.user_clients and self.storage.channels:
            await self.start_monitoring()
        
        await self.bot.run_until_disconnected()
    
    async def load_user_sessions(self):
        for f in os.listdir(SESSION_DIR):
            if f.endswith('.session') and not f.startswith('manager'):
                phone = f.replace('.session', '')
                try:
                    client = TelegramClient(f'{SESSION_DIR}/{phone}', API_ID, API_HASH)
                    await client.connect()
                    if await client.is_user_authorized():
                        self.user_clients[phone] = client
                        logger.info(f"✅ Загружен аккаунт: {phone[-4:]}")
                except: pass
    
    async def handle_message(self, event):
        if not event.message.text: return
        user_id = event.sender_id
        
        if user_id in self.waiting_for:
            await self.handle_input(event)
            return
        
        if event.message.text.startswith('/'):
            await event.reply("🤖 Используйте кнопки:", buttons=self.main_menu())
    
    async def handle_callback(self, event):
        data = event.data.decode('utf-8')
        user_id = event.sender_id
        
        if data == "main_menu":
            await event.edit("🤖 Главное меню:", buttons=self.main_menu())
        
        elif data == "stats":
            text = self.format_stats()
            await event.edit(text, buttons=self.main_menu(), parse_mode='markdown')
        
        elif data == "channels":
            text = self.format_channels()
            await event.edit(text, buttons=self.channels_menu(), parse_mode='markdown')
        
        elif data == "add_channel":
            self.waiting_for[user_id] = "add_channel"
            await event.edit(
                "➕ Отправьте ссылку или username канала:",
                buttons=[[Button.inline("◀️ Отмена", data="main_menu")]]
            )
        
        elif data == "remove_channel":
            if not self.storage.channels:
                await event.answer("❌ Нет каналов")
                return
            buttons = []
            for i, ch in enumerate(self.storage.channels[:10]):
                short = ch[:20] + "..." if len(ch) > 20 else ch
                buttons.append([Button.inline(f"❌ {i+1}. {short}", data=f"del_{ch}")])
            buttons.append([Button.inline("◀️ Назад", data="channels")])
            await event.edit("🗑 Выберите канал:", buttons=buttons)
        
        elif data.startswith("del_"):
            ch = data[4:]
            self.storage.channels.remove(ch)
            self.storage.save_channels()
            await event.answer("✅ Канал удален")
            await event.edit(self.format_channels(), buttons=self.channels_menu(), parse_mode='markdown')
        
        elif data == "settings":
            text = self.format_settings()
            await event.edit(text, buttons=self.settings_menu(), parse_mode='markdown')
        
        elif data == "keywords":
            self.waiting_for[user_id] = "keywords"
            await event.edit(
                f"📝 Введите ключевые слова через запятую\nТекущие: {', '.join(self.storage.keywords)}",
                buttons=[[Button.inline("◀️ Отмена", data="settings")]]
            )
        
        elif data == "delay":
            self.waiting_for[user_id] = "delay"
            await event.edit(
                f"⏱ Введите мин и макс задержку\nТекущая: {self.storage.delay_between[0]}-{self.storage.delay_between[1]} сек",
                buttons=[[Button.inline("◀️ Отмена", data="settings")]]
            )
        
        elif data == "mode":
            await event.edit(
                "🎲 Режим:",
                buttons=[
                    [Button.inline("🎲 Случайный", data="mode_random"),
                     Button.inline("👥 Все", data="mode_all")],
                    [Button.inline("🔄 По очереди", data="mode_round"),
                     Button.inline("◀️ Назад", data="settings")]
                ]
            )
        
        elif data == "mode_random":
            self.storage.comment_mode = "random"
            self.storage.save_settings()
            await event.answer("✅ Режим: Случайный")
            await event.edit(self.format_settings(), buttons=self.settings_menu(), parse_mode='markdown')
        
        elif data == "mode_all":
            self.storage.comment_mode = "all"
            self.storage.save_settings()
            await event.answer("✅ Режим: Все")
            await event.edit(self.format_settings(), buttons=self.settings_menu(), parse_mode='markdown')
        
        elif data == "mode_round":
            self.storage.comment_mode = "round_robin"
            self.storage.save_settings()
            await event.answer("✅ Режим: По очереди")
            await event.edit(self.format_settings(), buttons=self.settings_menu(), parse_mode='markdown')
        
        elif data == "start_monitor":
            if not self.user_clients:
                await event.answer("❌ Нет аккаунтов")
                return
            await self.start_monitoring()
            await event.answer("✅ Мониторинг запущен")
            await event.edit(self.format_status(), buttons=self.main_menu(), parse_mode='markdown')
        
        elif data == "stop_monitor":
            self.monitoring = False
            await event.answer("⏸️ Мониторинг остановлен")
            await event.edit(self.format_status(), buttons=self.main_menu(), parse_mode='markdown')
    
    async def handle_input(self, event):
        user_id = event.sender_id
        action = self.waiting_for[user_id]
        text = event.message.text.strip()
        
        if action == "add_channel":
            await self.add_channel(text, event)
        elif action == "keywords":
            self.storage.keywords = [k.strip() for k in text.split(',') if k.strip()]
            self.storage.save_settings()
            await event.reply("✅ Ключевые слова обновлены", buttons=self.settings_menu())
        elif action == "delay":
            parts = text.split()
            if len(parts) == 2:
                try:
                    self.storage.delay_between = (int(parts[0]), int(parts[1]))
                    self.storage.save_settings()
                    await event.reply("✅ Задержка обновлена", buttons=self.settings_menu())
                except:
                    await event.reply("❌ Ошибка", buttons=self.settings_menu())
            else:
                await event.reply("❌ Введите 2 числа", buttons=self.settings_menu())
        
        del self.waiting_for[user_id]
    
    async def add_channel(self, channel_input, event):
        if not self.user_clients:
            await event.reply("❌ Нет аккаунтов")
            return
        
        is_invite = 't.me/+' in channel_input or 'joinchat' in channel_input
        if not is_invite:
            if channel_input.startswith('https://'):
                channel_input = '@' + channel_input.split('/')[-1]
            elif not channel_input.startswith('@'):
                channel_input = '@' + channel_input
        
        entity = None
        channel_name = None
        
        for phone, client in self.user_clients.items():
            try:
                if is_invite:
                    hash_part = channel_input.split('joinchat/')[-1] if 'joinchat' in channel_input else channel_input.split('t.me/+')[-1]
                    updates = await client(CheckChatInviteRequest(hash=hash_part))
                    if hasattr(updates, 'chat'):
                        result = await client(ImportChatInviteRequest(hash=hash_part))
                        if result.chats:
                            channel = result.chats[0]
                            if entity is None:
                                entity = channel
                                channel_name = f"@{channel.username}" if channel.username else f"🔐 {channel.title}"
                else:
                    entity = await client.get_entity(channel_input)
                    channel_name = channel_input
            except: pass
        
        if entity and channel_name not in self.storage.channels:
            self.storage.channels.append(channel_name)
            if entity.id not in self.storage.channel_ids:
                self.storage.channel_ids.append(entity.id)
                self.storage.channel_names[str(entity.id)] = channel_name
            self.storage.save_channels()
            await event.reply(f"✅ Канал добавлен: {channel_name}", buttons=self.channels_menu())
        else:
            await event.reply("❌ Ошибка", buttons=self.channels_menu())
    
    async def start_monitoring(self):
        if not self.user_clients or not self.storage.channels:
            return
        
        self.monitoring = True
        client = list(self.user_clients.values())[0]
        
        if self.handler:
            client.remove_event_handler(self.handler)
        
        @client.on(events.NewMessage(chats=self.storage.channel_ids))
        async def handler(event):
            if not isinstance(event.message.peer_id, PeerChannel):
                return
            
            channel_id = event.message.peer_id.channel_id
            if channel_id in self.last_post_ids and self.last_post_ids[channel_id] >= event.message.id:
                return
            
            self.last_post_ids[channel_id] = event.message.id
            channel_name = self.storage.channel_names.get(str(channel_id), "Unknown")
            
            post_text = event.message.text or ""
            found = [kw for kw in self.storage.keywords if kw.lower() in post_text.lower()]
            
            if found:
                logger.info(f"✅ Ключевые слова в {channel_name}")
                await self.comment_on_post(channel_id, event.message.id, channel_name)
        
        self.handler = handler
        logger.info("✅ Мониторинг активен")
    
    async def comment_on_post(self, channel_id, post_id, channel_name):
        accounts = list(self.user_clients.keys())
        if not accounts: return
        
        accounts_to_use = []
        if self.storage.comment_mode == "random":
            accounts_to_use = [random.choice(accounts)]
        elif self.storage.comment_mode == "all":
            accounts_to_use = accounts
        elif self.storage.comment_mode == "round_robin":
            accounts_to_use = [accounts[0]]
        
        client = list(self.user_clients.values())[0]
        entity = await client.get_entity(channel_id)
        
        for phone in accounts_to_use:
            client = self.user_clients[phone]
            length = random.randint(self.storage.comment_length[0], self.storage.comment_length[1])
            comment = ''.join(random.choice(RUSSIAN_LETTERS) for _ in range(length))
            
            try:
                await client.send_message(entity, comment, comment_to=post_id)
                self.storage.stats['comments'] += 1
                self.storage.stats['by_account'][phone[-4:]] = self.storage.stats['by_account'].get(phone[-4:], 0) + 1
                self.storage.stats['by_channel'][channel_name] = self.storage.stats['by_channel'].get(channel_name, 0) + 1
                self.storage.save_settings()
                logger.info(f"✅ Комментарий с {phone[-4:]}")
                await asyncio.sleep(random.uniform(self.storage.delay_between[0], self.storage.delay_between[1]))
            except FloodWaitError as e:
                await asyncio.sleep(e.seconds)
            except: pass
    
    def format_status(self):
        return f"📊 *Статус*\n\nМониторинг: {'✅' if self.monitoring else '❌'}\nАккаунтов: {len(self.user_clients)}\nКаналов: {len(self.storage.channels)}\nКомментариев: {self.storage.stats['comments']}"
    
    def format_stats(self):
        text = f"📈 *Статистика*\n\nВсего: {self.storage.stats['comments']}\n\n*По каналам:*\n"
        for ch, cnt in list(self.storage.stats['by_channel'].items())[:5]:
            text += f"📺 {ch[:20]}: {cnt}\n"
        return text
    
    def format_channels(self):
        if not self.storage.channels:
            return "📺 *Каналы*\n\n❌ Нет каналов"
        text = f"📺 *Каналы ({len(self.storage.channels)})*\n\n"
        for i, ch in enumerate(self.storage.channels, 1):
            text += f"{i}. {ch[:30]}\n"
        return text
    
    def format_settings(self):
        modes = {'random': '🎲 Случайный', 'all': '👥 Все', 'round_robin': '🔄 По очереди'}
        return f"⚙️ *Настройки*\n\n📝 Ключевые слова: {', '.join(self.storage.keywords[:3])}...\n⏱ Задержка: {self.storage.delay_between[0]}-{self.storage.delay_between[1]} сек\n🎯 Режим: {modes.get(self.storage.comment_mode, self.storage.comment_mode)}"
    
    def main_menu(self):
        return [
            [Button.inline("📊 Статистика", "stats"), Button.inline("📺 Каналы", "channels")],
            [Button.inline("⚙️ Настройки", "settings"), Button.inline("▶️ Запуск", "start_monitor")],
            [Button.inline("⏸️ Стоп", "stop_monitor")]
        ]
    
    def channels_menu(self):
        return [
            [Button.inline("➕ Добавить", "add_channel"), Button.inline("➖ Удалить", "remove_channel")],
            [Button.inline("◀️ Назад", "main_menu")]
        ]
    
    def settings_menu(self):
        return [
            [Button.inline("📝 Ключевые слова", "keywords"), Button.inline("⏱ Задержка", "delay")],
            [Button.inline("🎲 Режим", "mode"), Button.inline("◀️ Назад", "main_menu")]
        ]

# ========== ЗАПУСК ==========
async def main():
    bot = AutoCommenterBot()
    await bot.start()

if __name__ == '__main__':
    asyncio.run(main())
