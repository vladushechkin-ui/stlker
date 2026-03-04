#!/usr/bin/env python3
import asyncio
import os
import json
import logging
import random
from aiohttp import web
from telethon import TelegramClient, events, Button
from telethon.tl.types import PeerChannel
from telethon.errors import SessionPasswordNeededError, FloodWaitError, PhoneCodeExpiredError
from telethon.tl.functions.channels import JoinChannelRequest
from telethon.tl.functions.messages import ImportChatInviteRequest, CheckChatInviteRequest

# ========== НАСТРОЙКИ ==========
API_ID = 34933719
API_HASH = '19fec1ce8a25b608afa68875633715f4'
BOT_TOKEN = '8252577084:AAF6exibor5RKeCL-ob3WRS9in7DVOpbwBY'
PORT = int(os.environ.get('PORT', 10000))
SESSION_DIR = 'sessions'
os.makedirs(SESSION_DIR, exist_ok=True)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
RUSSIAN_LETTERS = 'абвгдеёжзийклмнопрстуфхцчшщъыьэюя'

# ========== ХРАНИЛИЩЕ ==========
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
        self.pending_auth = {}
        self.load_all()
    
    def load_all(self):
        try:
            if os.path.exists('channels.json'):
                with open('channels.json') as f:
                    d = json.load(f)
                    self.channels = d.get('channels', [])
                    self.channel_ids = d.get('channel_ids', [])
                    self.channel_names = d.get('channel_names', {})
                    self.invite_links = d.get('invite_links', {})
        except: pass
        try:
            if os.path.exists('config.json'):
                with open('config.json') as f:
                    d = json.load(f)
                    self.keywords = d.get('keywords', self.keywords)
                    self.comment_length = tuple(d.get('comment_length', self.comment_length))
                    self.delay_between = tuple(d.get('delay_between', self.delay_between))
                    self.comment_mode = d.get('comment_mode', self.comment_mode)
                    self.stats = d.get('stats', self.stats)
        except: pass
    
    def save_channels(self):
        with open('channels.json', 'w') as f:
            json.dump({'channels': self.channels, 'channel_ids': self.channel_ids, 'channel_names': self.channel_names, 'invite_links': self.invite_links}, f)
    
    def save_config(self):
        with open('config.json', 'w') as f:
            json.dump({'keywords': self.keywords, 'comment_length': list(self.comment_length), 'delay_between': list(self.delay_between), 'comment_mode': self.comment_mode, 'stats': self.stats}, f)

# ========== БОТ ==========
class Bot:
    def __init__(self):
        self.s = Storage()
        self.user_clients = {}
        self.bot = None
        self.monitoring = False
        self.last_post_ids = {}
        self.handler = None
        self.waiting = {}
    
    async def start(self):
        # ВЕБ-СЕРВЕР
        app = web.Application()
        app.router.add_get('/', lambda r: web.Response(text='OK'))
        runner = web.AppRunner(app)
        await runner.setup()
        await web.TCPSite(runner, '0.0.0.0', PORT).start()
        logger.info("✅ Веб-сервер запущен")
        
        # БОТ
        self.bot = await TelegramClient(f'{SESSION_DIR}/manager', API_ID, API_HASH).start(bot_token=BOT_TOKEN)
        logger.info("✅ Бот запущен")
        
        @self.bot.on(events.NewMessage)
        async def on_msg(e): await self.handle_message(e)
        
        @self.bot.on(events.CallbackQuery)
        async def on_cb(e): await self.handle_callback(e)
        
        await self.load_sessions()
        if self.user_clients and self.s.channels:
            await self.start_monitoring()
        
        await self.bot.run_until_disconnected()
    
    async def load_sessions(self):
        for f in os.listdir(SESSION_DIR):
            if f.endswith('.session') and not f.startswith('manager'):
                phone = f.replace('.session', '')
                client = TelegramClient(f'{SESSION_DIR}/{phone}', API_ID, API_HASH)
                await client.connect()
                if await client.is_user_authorized():
                    self.user_clients[phone] = client
                    logger.info(f"✅ Загружен {phone[-4:]}")
    
    async def handle_message(self, e):
        if not e.message.text: return
        uid = e.sender_id
        if uid in self.waiting:
            await self.handle_input(e)
        elif e.message.text.startswith('/'):
            await e.reply("Меню:", buttons=self.main_menu())
    
    async def handle_callback(self, e):
        data, uid = e.data.decode(), e.sender_id
        if data == 'main_menu':
            await e.edit("Меню:", buttons=self.main_menu())
        elif data == 'stats':
            await e.edit(self.fmt_stats(), buttons=self.main_menu(), parse_mode='md')
        elif data == 'channels':
            await e.edit(self.fmt_channels(), buttons=self.channels_menu(), parse_mode='md')
        elif data == 'add_channel':
            self.waiting[uid] = 'add_channel'
            await e.edit("➕ Отправь ссылку/username:", buttons=[[Button.inline("❌ Отмена", 'main_menu')]])
        elif data == 'remove_channel':
            if not self.s.channels:
                return await e.answer("❌ Нет каналов")
            btns = []
            for ch in self.s.channels[:10]:
                btns.append([Button.inline(f"❌ {ch[:20]}", f"del_{ch}")])
            btns.append([Button.inline("◀️ Назад", 'channels')])
            await e.edit("🗑 Выбери:", buttons=btns)
        elif data.startswith('del_'):
            ch = data[4:]
            self.s.channels.remove(ch)
            self.s.save_channels()
            await e.answer("✅ Удалено")
            await e.edit(self.fmt_channels(), buttons=self.channels_menu(), parse_mode='md')
        elif data == 'accounts':
            await e.edit(self.fmt_accounts(), buttons=self.accounts_menu(), parse_mode='md')
        elif data == 'add_account':
            self.waiting[uid] = 'add_account_phone'
            await e.edit("📱 Отправь номер (пример: +79123456789):", buttons=[[Button.inline("❌ Отмена", 'main_menu')]])
        elif data == 'settings':
            await e.edit(self.fmt_settings(), buttons=self.settings_menu(), parse_mode='md')
        elif data == 'keywords':
            self.waiting[uid] = 'keywords'
            await e.edit(f"📝 Сейчас: {', '.join(self.s.keywords)}\nВведи новые через запятую:", buttons=[[Button.inline("❌ Отмена", 'settings')]])
        elif data == 'delay':
            self.waiting[uid] = 'delay'
            await e.edit(f"⏱ Сейчас: {self.s.delay_between[0]}-{self.s.delay_between[1]}\nВведи мин макс (пример: 2 5):", buttons=[[Button.inline("❌ Отмена", 'settings')]])
        elif data == 'mode':
            await e.edit("🎲 Режим:", buttons=[
                [Button.inline("🎲 Случайный", 'mode_random'), Button.inline("👥 Все", 'mode_all')],
                [Button.inline("🔄 По очереди", 'mode_round'), Button.inline("◀️ Назад", 'settings')]
            ])
        elif data in ('mode_random', 'mode_all', 'mode_round'):
            self.s.comment_mode = data[5:]
            self.s.save_config()
            await e.answer("✅ Ок")
            await e.edit(self.fmt_settings(), buttons=self.settings_menu(), parse_mode='md')
        elif data == 'start_monitor':
            if not self.user_clients:
                return await e.answer("❌ Нет аккаунтов")
            await self.start_monitoring()
            await e.answer("✅ Мониторинг запущен")
        elif data == 'stop_monitor':
            self.monitoring = False
            await e.answer("⏸️ Остановлен")
    
    async def handle_input(self, e):
        uid, text = e.sender_id, e.message.text.strip()
        action = self.waiting.pop(uid, None)
        
        if action == 'add_account_phone':
            self.s.pending_auth[uid] = {'phone': text, 'step': 'code', 'client': TelegramClient(f'{SESSION_DIR}/{text}', API_ID, API_HASH)}
            client = self.s.pending_auth[uid]['client']
            await client.connect()
            await client.send_code_request(text)
            await e.reply("📲 Введи код (придет в Telegram):", buttons=[[Button.inline("❌ Отмена", 'main_menu')]])
            self.waiting[uid] = 'add_account_code'
        
        elif action == 'add_account_code':
            data = self.s.pending_auth.get(uid)
            if not data: return
            try:
                await data['client'].sign_in(data['phone'], text)
                self.user_clients[data['phone']] = data['client']
                self.s.pending_auth.pop(uid, None)
                await e.reply("✅ Аккаунт добавлен!", buttons=self.main_menu())
                await self.join_all_channels(data['phone'])
                await self.start_monitoring()
            except SessionPasswordNeededError:
                data['step'] = 'password'
                await e.reply("🔐 Введи пароль 2FA:", buttons=[[Button.inline("❌ Отмена", 'main_menu')]])
                self.waiting[uid] = 'add_account_password'
            except PhoneCodeExpiredError:
                # Код истек - запрашиваем новый
                await e.reply("❌ Код истек. Запрашиваю новый код...", buttons=[[Button.inline("❌ Отмена", 'main_menu')]])
                try:
                    await data['client'].send_code_request(data['phone'])
                    await e.reply("📲 Новый код отправлен. Введи его:", buttons=[[Button.inline("❌ Отмена", 'main_menu')]])
                    self.waiting[uid] = 'add_account_code'
                except Exception as ex:
                    await e.reply(f"❌ Ошибка: {ex}", buttons=self.main_menu())
                    self.s.pending_auth.pop(uid, None)
            except Exception as ex:
                await e.reply(f"❌ Ошибка: {ex}", buttons=self.main_menu())
                self.s.pending_auth.pop(uid, None)
        
        elif action == 'add_account_password':
            data = self.s.pending_auth.get(uid)
            if not data: return
            try:
                await data['client'].sign_in(password=text)
                self.user_clients[data['phone']] = data['client']
                self.s.pending_auth.pop(uid, None)
                await e.reply("✅ Аккаунт добавлен!", buttons=self.main_menu())
                await self.join_all_channels(data['phone'])
                await self.start_monitoring()
            except Exception as ex:
                await e.reply(f"❌ Ошибка: {ex}", buttons=self.main_menu())
                self.s.pending_auth.pop(uid, None)
        
        elif action == 'add_channel':
            await self.add_channel(text, e)
        elif action == 'keywords':
            self.s.keywords = [k.strip() for k in text.split(',') if k.strip()]
            self.s.save_config()
            await e.reply("✅ Готово", buttons=self.settings_menu())
        elif action == 'delay':
            parts = text.split()
            if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
                self.s.delay_between = (int(parts[0]), int(parts[1]))
                self.s.save_config()
                await e.reply("✅ Готово", buttons=self.settings_menu())
            else:
                await e.reply("❌ Надо два числа", buttons=self.settings_menu())
    
    async def add_channel(self, inp, e):
        if not self.user_clients:
            return await e.reply("❌ Нет аккаунтов")
        is_invite = 't.me/+' in inp or 'joinchat' in inp
        if not is_invite:
            inp = '@' + inp.split('/')[-1] if 'https://' in inp else ('@' + inp if not inp.startswith('@') else inp)
        entity = None
        for client in self.user_clients.values():
            try:
                if is_invite:
                    h = inp.split('joinchat/')[-1] if 'joinchat' in inp else inp.split('t.me/+')[-1]
                    r = await client(ImportChatInviteRequest(h))
                    if r.chats:
                        entity = r.chats[0]
                else:
                    entity = await client.get_entity(inp)
                if entity:
                    break
            except:
                continue
        if not entity:
            return await e.reply("❌ Не удалось")
        name = f"@{entity.username}" if entity.username else f"🔐 {entity.title}"
        if name in self.s.channels:
            return await e.reply("⚠️ Уже есть")
        self.s.channels.append(name)
        self.s.channel_ids.append(entity.id)
        self.s.channel_names[str(entity.id)] = name
        self.s.save_channels()
        await e.reply(f"✅ {name}", buttons=self.channels_menu())
        await self.start_monitoring()
    
    async def join_all_channels(self, phone):
        if phone not in self.user_clients:
            return
        client = self.user_clients[phone]
        for ch in self.s.channels:
            try:
                if ch in self.s.invite_links:
                    link = self.s.invite_links[ch]
                    h = link.split('joinchat/')[-1] if 'joinchat' in link else link.split('t.me/+')[-1]
                    await client(ImportChatInviteRequest(h))
                else:
                    await client(JoinChannelRequest(await client.get_entity(ch)))
            except:
                pass
            await asyncio.sleep(1)
    
    async def start_monitoring(self):
        if not self.user_clients or not self.s.channels:
            return
        self.monitoring = True
        client = list(self.user_clients.values())[0]
        if self.handler:
            client.remove_event_handler(self.handler)
        
        @client.on(events.NewMessage(chats=self.s.channel_ids))
        async def handler(event):
            if not isinstance(event.message.peer_id, PeerChannel):
                return
            cid = event.message.peer_id.channel_id
            if cid in self.last_post_ids and self.last_post_ids[cid] >= event.message.id:
                return
            self.last_post_ids[cid] = event.message.id
            text = event.message.text or ''
            if any(kw in text.lower() for kw in self.s.keywords):
                await self.comment(cid, event.message.id, self.s.channel_names.get(str(cid), 'Unknown'))
        
        self.handler = handler
        logger.info("✅ Мониторинг активен")
    
    async def comment(self, cid, pid, ch_name):
        accs = list(self.user_clients.keys())
        if not accs:
            return
        if self.s.comment_mode == 'random':
            use = [random.choice(accs)]
        elif self.s.comment_mode == 'all':
            use = accs
        else:
            use = [accs[0]]
        entity = await list(self.user_clients.values())[0].get_entity(cid)
        for phone in use:
            client = self.user_clients[phone]
            length = random.randint(self.s.comment_length[0], self.s.comment_length[1])
            comment = ''.join(random.choice(RUSSIAN_LETTERS) for _ in range(length))
            try:
                await client.send_message(entity, comment, comment_to=pid)
                self.s.stats['comments'] += 1
                self.s.stats['by_account'][phone[-4:]] = self.s.stats['by_account'].get(phone[-4:], 0) + 1
                self.s.stats['by_channel'][ch_name] = self.s.stats['by_channel'].get(ch_name, 0) + 1
                self.s.save_config()
                logger.info(f"✅ {phone[-4:]}: {comment}")
                await asyncio.sleep(random.uniform(*self.s.delay_between))
            except FloodWaitError as f:
                await asyncio.sleep(f.seconds)
            except:
                pass
    
    def fmt_stats(self):
        return f"📊 *Всего:* {self.s.stats['comments']}\n\n" + '\n'.join(f"📺 {k[:20]}: {v}" for k, v in list(self.s.stats['by_channel'].items())[:5])
    
    def fmt_channels(self):
        if not self.s.channels:
            return "📺 *Каналы*\n\n❌ Нет каналов"
        return f"📺 *Каналы ({len(self.s.channels)})*\n\n" + '\n'.join(f"{i}. {ch[:30]}" for i, ch in enumerate(self.s.channels, 1))
    
    def fmt_accounts(self):
        if not self.user_clients:
            return "📱 *Аккаунты*\n\n❌ Нет аккаунтов"
        return f"📱 *Аккаунты ({len(self.user_clients)})*\n\n" + '\n'.join(f"{i}. {p[-4:]}" for i, p in enumerate(self.user_clients.keys(), 1))
    
    def fmt_settings(self):
        mode = '🎲 Случ' if self.s.comment_mode == 'random' else '👥 Все' if self.s.comment_mode == 'all' else '🔄 Очередь'
        return f"⚙️ *Настройки*\n\n📝 {', '.join(self.s.keywords[:3])}...\n⏱ {self.s.delay_between[0]}-{self.s.delay_between[1]} сек\n🎯 {mode}"
    
    def main_menu(self):
        return [
            [Button.inline("📊 Стат", 'stats'), Button.inline("📺 Каналы", 'channels')],
            [Button.inline("📱 Акки", 'accounts'), Button.inline("⚙️ Настр", 'settings')],
            [Button.inline("▶️ Старт", 'start_monitor'), Button.inline("⏸️ Стоп", 'stop_monitor')]
        ]
    
    def channels_menu(self):
        return [
            [Button.inline("➕ Добавить", 'add_channel'), Button.inline("➖ Удалить", 'remove_channel')],
            [Button.inline("◀️ Назад", 'main_menu')]
        ]
    
    def accounts_menu(self):
        return [
            [Button.inline("➕ Добавить", 'add_account')],
            [Button.inline("◀️ Назад", 'main_menu')]
        ]
    
    def settings_menu(self):
        return [
            [Button.inline("📝 Ключ.слова", 'keywords'), Button.inline("⏱ Задержка", 'delay')],
            [Button.inline("🎲 Режим", 'mode'), Button.inline("◀️ Назад", 'main_menu')]
        ]

async def main():
    bot = Bot()
    await bot.start()

if __name__ == '__main__':
    asyncio.run(main())
