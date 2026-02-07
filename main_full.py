# В самом начале файла, где другие импорты
import vk_api
from vk_api.bot_longpoll import VkBotLongPoll, VkBotEventType
from vk_api.keyboard import VkKeyboard, VkKeyboardColor
import json
import random
import sqlite3
import time
from datetime import datetime

# Импорты команд
from commands.stats_command import handle_stats

# Импортируем настройки подключения
try:
    from connection_config import CONNECTION_SETTINGS, ERROR_HANDLING, LOGGING_SETTINGS
except ImportError:
    # Настройки по умолчанию если файл конфигурации не найден
    CONNECTION_SETTINGS = {
        'wait_time': 15,
        'max_reconnect_attempts': 5,
        'base_reconnect_delay': 10,
        'max_reconnect_delay': 60,
        'message_cache_size': 1000,
        'command_cooldown': 2,
        'cache_cleanup_interval': 60,
    }
    ERROR_HANDLING = {
        'proxy_errors': ['ProxyError', 'RemoteDisconnected', 'ConnectionError'],
        'retry_errors': ['Max retries exceeded', 'Connection timeout', 'Read timeout'],
        'critical_errors': ['Invalid token', 'Access denied'],
    }
    LOGGING_SETTINGS = {
        'log_commands_only': True,
        'log_duplicates': False,
        'log_reconnections': True,
        'verbose_errors': True,
    }

# Импорты команд
from commands.stats_command import handle_stats
from commands.user_commands import handle_id, handle_bonus
from commands.moderator_commands import handle_kick, handle_warn, handle_mute
from commands.senior_moderator_commands import handle_ban, handle_unban, handle_banlist
from commands.admin_commands import handle_roles
from commands.senior_admin_commands import handle_remove_role, handle_remove_nick
from commands.chat_owner_commands import handle_pull, handle_pullinfo, handle_transfer_ownership
from commands.owner_commands import handle_givemoney, handle_addmoder, handle_stop_bot
from commands.mtop_command import handle_mtop, handle_mtop_navigation

# Загружаем конфиг
with open("config.json", "r") as js:
    config = json.load(js)

# Загружаем цены магазина
with open("shop_prices.json", "r", encoding="utf-8") as f:
    shop_prices = json.load(f)

# Инициализация VK API
vk_session = vk_api.VkApi(token=config['bot-token'])
vk = vk_session.get_api()
group_info = vk.groups.getById()
group_id = group_info[0]['id']
longpoll = VkBotLongPoll(vk_session, group_id, wait=CONNECTION_SETTINGS['wait_time'])

# База данных
database = sqlite3.connect('database.db', check_same_thread=False)
sql = database.cursor()

# Загружаем спец-админов
with open("special_admins.json", "r") as f:
    special_admins = json.load(f)["special_admins"]

# Владелец проекта
BOT_OWNER_ID = 772638324  # Ваш ID

# Кэш для предотвращения дублирования команд
processed_messages = {}
MAX_CACHE_SIZE = CONNECTION_SETTINGS['message_cache_size']

# Кэш для предотвращения спама команд
command_cooldown = {}
COMMAND_COOLDOWN_TIME = CONNECTION_SETTINGS['command_cooldown']

# Загружаем модераторов бота из базы
try:
    sql.execute("ALTER TABLE bot_admins ADD COLUMN role TEXT DEFAULT 'moderator'")
    database.commit()
except:
    pass

try:
    sql.execute("SELECT user_id FROM bot_admins")
    BOT_MODERATORS = [row[0] for row in sql.fetchall()]
except:
    BOT_MODERATORS = []

if BOT_OWNER_ID not in BOT_MODERATORS:
    BOT_MODERATORS.append(BOT_OWNER_ID)

print(f"Бот запущен | ID: {group_id}")

# Скрываем все инлайн кнопки при запуске
from commands.mtop_command import hide_all_keyboards
hide_all_keyboards(vk, sql)  

# Создание таблиц
sql.execute('''CREATE TABLE IF NOT EXISTS chats (
    chat_id INTEGER, peer_id INTEGER, owner_id INTEGER, 
    welcome_text TEXT, silence INTEGER, filter INTEGER, 
    antiflood INTEGER, invite_kick INTEGER, leave_kick INTEGER, in_pull INTEGER,
    pull_id TEXT
)''')

sql.execute('''CREATE TABLE IF NOT EXISTS global_managers (
    user_id INTEGER, level INTEGER
)''')

sql.execute('''CREATE TABLE IF NOT EXISTS bot_admins (
    user_id INTEGER PRIMARY KEY,
    role TEXT DEFAULT 'moderator'
)''')

sql.execute('''CREATE TABLE IF NOT EXISTS global_coins (
    user_id INTEGER PRIMARY KEY,
    coins INTEGER DEFAULT 0
)''')

sql.execute('''CREATE TABLE IF NOT EXISTS vip_statuses (
    user_id INTEGER,
    chat_id INTEGER,
    vip_type TEXT,
    end_time INTEGER DEFAULT 0,
    PRIMARY KEY (user_id, chat_id)
)''')

# Создание таблиц
sql.execute('''CREATE TABLE IF NOT EXISTS chats (
    chat_id INTEGER, peer_id INTEGER, owner_id INTEGER, 
    welcome_text TEXT, silence INTEGER, filter INTEGER, 
    antiflood INTEGER, invite_kick INTEGER, leave_kick INTEGER, in_pull INTEGER,
    pull_id TEXT
)''')

sql.execute('''CREATE TABLE IF NOT EXISTS global_managers (
    user_id INTEGER, level INTEGER
)''')

sql.execute('''CREATE TABLE IF NOT EXISTS bot_admins (
    user_id INTEGER PRIMARY KEY,
    role TEXT DEFAULT 'moderator'
)''')

sql.execute('''CREATE TABLE IF NOT EXISTS global_coins (
    user_id INTEGER PRIMARY KEY,
    coins INTEGER DEFAULT 0
)''')

sql.execute('''CREATE TABLE IF NOT EXISTS vip_statuses (
    user_id INTEGER,
    chat_id INTEGER,
    vip_type TEXT,
    end_time INTEGER DEFAULT 0,
    PRIMARY KEY (user_id, chat_id)
)''')

# ДОБАВИТЬ ЭТУ ТАБЛИЦУ:
sql.execute('''CREATE TABLE IF NOT EXISTS custom_role_names (
    chat_id INTEGER,
    role_level INTEGER,
    custom_name TEXT,
    PRIMARY KEY (chat_id, role_level)
)''')

sql.execute('''CREATE TABLE IF NOT EXISTS disabled_roles (
    chat_id INTEGER,
    role_level INTEGER,
    PRIMARY KEY (chat_id, role_level)
)''')

# Обновляем структуру базы данных для поддержки pull_id
try:
    sql.execute("ALTER TABLE chats ADD COLUMN pull_id TEXT")
    database.commit()
except:
    pass  # Колонка уже существует

# Обновляем таблицу VIP статусов
try:
    sql.execute("ALTER TABLE vip_statuses ADD COLUMN end_time INTEGER")
    database.commit()
except:
    pass  # Колонка уже существует

database.commit()

# Глобальный счетчик для random_id
_message_counter = 0

def send_message(peer_id, message, reply_to=None, keyboard=None):
    global _message_counter
    try:
        # Проверяем что сообщение не пустое и не состоит только из точек
        if not message or message.strip() == '.' or message.strip() == '......':
            print(f"[MSG WARNING] Попытка отправить пустое сообщение или только точки: '{message}'")
            return None
            
        # Генерируем уникальный random_id
        _message_counter += 1
        random_id = int(time.time() * 1000) + _message_counter
        
        params = {
            'peer_id': peer_id,
            'message': message,
            'random_id': random_id
        }
        if reply_to:
            params['reply_to'] = reply_to
            
        if keyboard:
            params['keyboard'] = keyboard.get_keyboard()
            
        result = vk.messages.send(**params)
        # Логирование отключено
        # if len(message) > 100:
        #     log_msg = message[:50] + "..."
        # else:
        #     log_msg = message
        # print(f"[MSG] -> {peer_id}: {log_msg}")
        return result
    except Exception as e:
        print(f"[MSG ERROR] Ошибка отправки: {e}")
        return None

def get_user_info(user_id):
    try:
        user = vk.users.get(user_ids=user_id)[0]
        return f"{user['first_name']} {user['last_name']}"
    except:
        return "Пользователь"

def check_chat(chat_id):
    sql.execute(f"SELECT * FROM chats WHERE chat_id = {chat_id}")
    return sql.fetchone() is not None

def new_chat(chat_id, peer_id, owner_id):
    sql.execute(f"INSERT INTO chats VALUES (?, ?, ?, 'Добро пожаловать!', 0, 0, 0, 0, 0, 0, NULL)", 
                (chat_id, peer_id, owner_id))
    
    # Создаем таблицы для чата
    sql.execute(f"CREATE TABLE IF NOT EXISTS permissions_{chat_id} (user_id INTEGER, level INTEGER)")
    sql.execute(f"CREATE TABLE IF NOT EXISTS nicks_{chat_id} (user_id INTEGER, nick TEXT)")
    sql.execute(f"CREATE TABLE IF NOT EXISTS warns_{chat_id} (user_id INTEGER, count INTEGER, moder INTEGER, reason TEXT, date INTEGER)")
    sql.execute(f"CREATE TABLE IF NOT EXISTS bans_{chat_id} (user_id INTEGER, moder INTEGER, reason TEXT, date INTEGER)")
    sql.execute(f"CREATE TABLE IF NOT EXISTS games_{chat_id} (enabled INTEGER DEFAULT 0)")
    sql.execute(f"CREATE TABLE IF NOT EXISTS bonuses_{chat_id} (user_id INTEGER, last_bonus INTEGER, streak INTEGER, coins INTEGER)")
    sql.execute(f"CREATE TABLE IF NOT EXISTS marriages_{chat_id} (user1 INTEGER, user2 INTEGER, date INTEGER)")
    sql.execute(f"CREATE TABLE IF NOT EXISTS user_stats_{chat_id} (user_id INTEGER, join_date INTEGER, inviter INTEGER, messages INTEGER DEFAULT 0)")
    
    # Добавляем бота в статистику
    sql.execute(f"INSERT OR IGNORE INTO user_stats_{chat_id} VALUES (?, ?, 0, 6666)", (-group_id, int(time.time())))
    # Добавляем владельца с 1500 сообщениями
    sql.execute(f"INSERT OR IGNORE INTO user_stats_{chat_id} VALUES (?, ?, 0, 1500)", (BOT_OWNER_ID, int(time.time())))
    
    database.commit()

def get_role_name(role_level, chat_id=None):
    """Возвращает название роли по её уровню"""
    
    # Сначала проверяем кастомные названия для конкретного чата
    if chat_id is not None:
        try:
            sql.execute("SELECT custom_name FROM custom_role_names WHERE chat_id = ? AND role_level = ?", 
                       (chat_id, role_level))
            custom_result = sql.fetchone()
            if custom_result and custom_result[0]:
                return custom_result[0]
        except:
            pass
    
    role_names = {
        0: 'Хелпер/Лидер',
        10: 'Младший Модератор', 
        20: 'Модератор',
        30: 'Старший модератор',
        40: 'Администратор',
        45: 'Старший администратор',
        60: 'Куратор Администрации',
        70: 'Заместитель Главного Администратора',
        80: 'Главный Администратор',
        90: 'Заместитель Специального Администратора',
        95: 'Специальный Администратор',
        99: 'Директор проекта',
        100: 'Владелец Проекта',
        150: 'Модератор Бота',
        350: 'Администратор Бота',
        500: 'Куратор бота',
        1000: 'Владелец бота',
        1500: 'БОТ'
    }
    return role_names.get(role_level, 'Пользователь')

def get_role(user_id, chat_id):
    # Новая система ролей:
    # БОТ 1500
    # Владелец бота 1000
    # Куратор бота 500
    # Администратор Бота 350
    # Модератор бота 150
    # Владелец Проекта 100
    # Директор проекта 99
    # Специальный Администратор 95
    # Заместитель Специального Администратора 90
    # Главный Администратор 80
    # Заместитель Главного Администратора 70
    # Куратор Администрации 60
    # Старший администратор 45
    # Администратор 40
    # Старший модератор 30
    # Модератор 20
    # Младший Модератор 10
    # Хелпер/Лидер 0
    
    # Проверяем статус бота
    try:
        sql.execute("SELECT user_id FROM bot_users WHERE user_id = ?", (user_id,))
        if sql.fetchone():
            return 1500  # БОТ
    except:
        pass
    
    # Проверяем владельца бота
    if user_id == BOT_OWNER_ID:
        return 1000  # Владелец бота
    
    # Проверяем администраторов и модераторов бота
    try:
        sql.execute("SELECT role FROM bot_admins WHERE user_id = ?", (user_id,))
        bot_role = sql.fetchone()
        if bot_role:
            if bot_role[0] == 'curator':
                return 500  # Куратор бота
            elif bot_role[0] == 'admin':
                return 350  # Администратор бота
            elif bot_role[0] == 'moderator':
                return 150  # Модератор бота
    except:
        pass
    
    # Проверяем спец-администраторов
    if user_id in special_admins:
        return 150  # Модератор бота
    
    # Проверяем владельца чата
    sql.execute(f"SELECT owner_id FROM chats WHERE chat_id = {chat_id}")
    owner = sql.fetchone()
    if owner and owner[0] == user_id:
        return 100  # Владелец Проекта
    
    # Проверяем роли в чате
    sql.execute(f"SELECT level FROM permissions_{chat_id} WHERE user_id = {user_id}")
    fetch = sql.fetchone()
    if fetch:
        level = fetch[0]
        # Конвертируем старые уровни в новые
        # Конвертируем старые уровни в новые
        if level == 6: return 95   # Специальный Администратор
        elif level == 5: return 80 # Главный Администратор
        elif level == 4: return 45 # Старший администратор
        elif level == 3: return 40 # Администратор
        elif level == 2: return 30 # Старший Администратор
        elif level == 1: return 20 # Модератор
        else: return level
    
    return 0  # Хелпер/Лидер

def set_role(user_id, chat_id, role):
    sql.execute(f"SELECT user_id FROM permissions_{chat_id} WHERE user_id = {user_id}")
    if sql.fetchone():
        if role == 0:
            sql.execute(f"DELETE FROM permissions_{chat_id} WHERE user_id = {user_id}")
        else:
            sql.execute(f"UPDATE permissions_{chat_id} SET level = ? WHERE user_id = ?", (role, user_id))
    else:
        if role > 0:
            sql.execute(f"INSERT INTO permissions_{chat_id} VALUES (?, ?)", (user_id, role))
    database.commit()

def kick_user(chat_id, user_id):
    try:
        vk.messages.removeChatUser(chat_id=chat_id, user_id=user_id)
        return True
    except:
        return False

def warn_user(user_id, chat_id, moder_id, reason):
    sql.execute(f"CREATE TABLE IF NOT EXISTS warns_{chat_id} (user_id INTEGER, count INTEGER, moder INTEGER, reason TEXT, date INTEGER)")
    sql.execute(f"SELECT count FROM warns_{chat_id} WHERE user_id = {user_id}")
    current = sql.fetchone()
    count = (current[0] + 1) if current else 1
    
    if current:
        sql.execute(f"UPDATE warns_{chat_id} SET count = ?, moder = ?, reason = ?, date = ? WHERE user_id = ?", 
                   (count, moder_id, reason, int(time.time()), user_id))
    else:
        sql.execute(f"INSERT INTO warns_{chat_id} (user_id, count, moder, reason, date) VALUES (?, ?, ?, ?, ?)", 
                   (user_id, count, moder_id, reason, int(time.time())))
    database.commit()
    return count

def ban_user(user_id, chat_id, moder_id, reason, duration=0):
    # duration = 0 означает перманентный бан
    # duration > 0 означает временный бан в минутах
    ban_until = int(time.time()) + (duration * 60) if duration > 0 else 0
    sql.execute(f"CREATE TABLE IF NOT EXISTS bans_{chat_id} (user_id INTEGER, moder INTEGER, reason TEXT, date INTEGER, ban_until INTEGER DEFAULT 0)")
    try:
        sql.execute(f"ALTER TABLE bans_{chat_id} ADD COLUMN ban_until INTEGER DEFAULT 0")
        sql.execute(f"ALTER TABLE bans_{chat_id} ADD COLUMN temp_column INTEGER DEFAULT 0")
    except:
        pass
    # Проверяем количество колонок в таблице
    sql.execute(f"PRAGMA table_info(bans_{chat_id})")
    columns = sql.fetchall()
    if len(columns) == 6:
        sql.execute(f"INSERT OR REPLACE INTO bans_{chat_id} VALUES (?, ?, ?, ?, ?, 0)", 
                   (user_id, moder_id, reason, int(time.time()), ban_until))
    else:
        sql.execute(f"INSERT OR REPLACE INTO bans_{chat_id} VALUES (?, ?, ?, ?, ?)", 
                   (user_id, moder_id, reason, int(time.time()), ban_until))
    database.commit()

def is_banned(user_id, chat_id):
    try:
        sql.execute(f"SELECT ban_until FROM bans_{chat_id} WHERE user_id = {user_id}")
        result = sql.fetchone()
        if result:
            ban_until = result[0]
            # Если бан временный и истек
            if ban_until > 0 and int(time.time()) >= ban_until:
                unban_user(user_id, chat_id)
                return False
            return True
        return False
    except:
        sql.execute(f"SELECT * FROM bans_{chat_id} WHERE user_id = {user_id}")
        return sql.fetchone() is not None

def set_nick(user_id, chat_id, nick):
    try:
        sql.execute(f"CREATE TABLE IF NOT EXISTS nicks_{chat_id} (user_id INTEGER, nick TEXT)")
        sql.execute(f"DELETE FROM nicks_{chat_id} WHERE user_id = ?", (user_id,))
        sql.execute(f"INSERT INTO nicks_{chat_id} VALUES (?, ?)", (user_id, nick))
        database.commit()
    except Exception as e:
        print(f"Ошибка set_nick: {e}")

def get_nick(user_id, chat_id):
    sql.execute(f"SELECT nick FROM nicks_{chat_id} WHERE user_id = {user_id}")
    result = sql.fetchone()
    return result[0] if result else None

def unban_user(user_id, chat_id):
    sql.execute(f"DELETE FROM bans_{chat_id} WHERE user_id = {user_id}")
    database.commit()

def unwarn_user(user_id, chat_id):
    sql.execute(f"SELECT count FROM warns_{chat_id} WHERE user_id = {user_id}")
    current = sql.fetchone()
    if current:
        if current[0] <= 1:
            sql.execute(f"DELETE FROM warns_{chat_id} WHERE user_id = {user_id}")
        else:
            sql.execute(f"UPDATE warns_{chat_id} SET count = ? WHERE user_id = ?", (current[0] - 1, user_id))
        database.commit()
        return max(0, current[0] - 1)
    return 0

def mute_user(user_id, chat_id, moder_id, reason, minutes):
    end_time = int(time.time()) + (minutes * 60)
    try:
        sql.execute(f"CREATE TABLE IF NOT EXISTS mutes_{chat_id} (user_id INTEGER, moder INTEGER, reason TEXT, end_time INTEGER)")
    except:
        pass
    try:
        sql.execute(f"ALTER TABLE mutes_{chat_id} ADD COLUMN end_time INTEGER DEFAULT 0")
    except:
        pass
    sql.execute(f"DELETE FROM mutes_{chat_id} WHERE user_id = ?", (user_id,))
    sql.execute(f"INSERT INTO mutes_{chat_id} (user_id, moder, reason, end_time) VALUES (?, ?, ?, ?)", (user_id, moder_id, reason, end_time))
    database.commit()

def unmute_user(user_id, chat_id):
    sql.execute(f"DELETE FROM mutes_{chat_id} WHERE user_id = {user_id}")
    database.commit()

def is_muted(user_id, chat_id):
    try:
        sql.execute(f"CREATE TABLE IF NOT EXISTS mutes_{chat_id} (user_id INTEGER, moder INTEGER, reason TEXT, end_time INTEGER)")
        try:
            sql.execute(f"ALTER TABLE mutes_{chat_id} ADD COLUMN end_time INTEGER DEFAULT 0")
        except:
            pass
        sql.execute(f"SELECT end_time FROM mutes_{chat_id} WHERE user_id = {user_id}")
        result = sql.fetchone()
        if result:
            if int(time.time()) >= result[0]:
                unmute_user(user_id, chat_id)
                return False
            return True
        return False
    except:
        return False

def parse_user_mention(text):
    """Извлекает ID пользователя из упоминания"""
    if text.startswith('[id') and '|' in text:
        return int(text.split('|')[0][3:])
    return None

def get_user_from_reply_or_mention(event_obj, args, arg_index=1):
    """Получает ID пользователя из ответа или упоминания"""
    # Проверяем ответ на сообщение
    if 'reply_message' in event_obj.message:
        return event_obj.message['reply_message']['from_id']
    
    # Проверяем упоминание в аргументах
    if len(args) > arg_index:
        return parse_user_mention(args[arg_index])
    
    return None

def get_online_users(peer_id):
    """Получает список пользователей онлайн"""
    try:
        members = vk.messages.getConversationMembers(peer_id=peer_id, fields='online')
        online_users = []
        for profile in members['profiles']:
            if profile.get('online', 0) == 1:
                online_users.append(profile['id'])
        return online_users
    except:
        return []

def get_mention(user_id, chat_id=0):
    """Форматирует упоминание пользователя: [id123|Имя]"""
    nick = get_nick(user_id, chat_id) if chat_id else None
    name = nick or get_user_info(user_id)
    return f"[id{user_id}|{name}]"

def format_user_with_nick(user_id, chat_id):
    """Форматирует пользователя с ником (совместимость)"""
    return get_mention(user_id, chat_id)

def generate_pull_id():
    import random
    import string
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=12))

def get_pull_by_id(pull_id):
    sql.execute("SELECT chat_id FROM chats WHERE pull_id = ?", (pull_id,))
    fetch = sql.fetchall()
    return [row[0] for row in fetch] if fetch else False

def set_pull_id(chat_id, pull_id):
    sql.execute("UPDATE chats SET pull_id = ? WHERE chat_id = ?", (pull_id, chat_id))
    database.commit()

def get_chat_pull_id(chat_id):
    sql.execute("SELECT pull_id FROM chats WHERE chat_id = ?", (chat_id,))
    fetch = sql.fetchone()
    return fetch[0] if fetch and fetch[0] else None

def get_pull_chats(chat_id):
    pull_id = get_chat_pull_id(chat_id)
    if not pull_id:
        return False
    return get_pull_by_id(pull_id)

def send_to_all_pull_chats(chat_id, message):
    """Отправляет сообщение во все чаты объединения"""
    pull_chats = get_pull_chats(chat_id)
    if not pull_chats:
        return False
    
    sent_count = 0
    for target_chat in pull_chats:
        try:
            target_peer_id = target_chat + 2000000000
            result = send_message(target_peer_id, message)
            if result:
                sent_count += 1
            # Небольшая задержка между отправками
            time.sleep(0.1)
        except Exception as e:
            print(f"[PULL ERROR] Ошибка отправки в чат {target_chat}: {e}")
    
    print(f"[PULL] Отправлено в {sent_count} чатов объединения")
    return sent_count > 0

def is_bot_admin(user_id):
    """Проверяет, является ли пользователь администратором бота"""
    return user_id == BOT_OWNER_ID or user_id in BOT_MODERATORS or user_id in special_admins

def has_command_access(user_id, command):
    """Проверяет, есть ли у пользователя доступ к команде"""
    try:
        # Команды владельца бота
        owner_commands = ['bot_info', 'info', 'dell_chat_db', 'asu_cmd', 'asu_delcmd', 'asu_cmdinfo', 'givemoney', 'delmoney', 'givevip', 'delvip', 'addmoder', 'addadmin', 'addcurator', 'start_bot', 'stop_bot', 'off_bot', 'notif', 'addma', 'givebot', 'delbot', 'asu_giveallcmd', 'asu_delallcmd', 'give_mes']
        
        if command in owner_commands:
            # Для команд владельца: владелец всегда имеет доступ, остальным нужно разрешение
            if user_id == BOT_OWNER_ID:
                return True
            sql.execute("CREATE TABLE IF NOT EXISTS allowed_commands (user_id INTEGER, command TEXT)")
            sql.execute("SELECT command FROM allowed_commands WHERE user_id = ? AND command = ?", (user_id, command))
            return sql.fetchone() is not None
        
        # Для обычных команд
        if user_id == BOT_OWNER_ID:
            return True
            
        # Проверяем запрещенные команды
        sql.execute("CREATE TABLE IF NOT EXISTS restricted_commands (user_id INTEGER, command TEXT)")
        sql.execute("SELECT command FROM restricted_commands WHERE user_id = ? AND command = ?", (user_id, command))
        if sql.fetchone():
            return False
        
        # Остальные команды доступны всем
        return True
    except:
        return False

def get_new_role_level(user_id, chat_id):
    """Получает новый уровень роли пользователя"""
    return get_role(user_id, chat_id)

def is_games_enabled(chat_id):
    try:
        sql.execute(f"CREATE TABLE IF NOT EXISTS games_{chat_id} (enabled INTEGER DEFAULT 0)")
        sql.execute(f"SELECT enabled FROM games_{chat_id}")
        result = sql.fetchone()
        return result[0] == 1 if result else False
    except:
        return False

def toggle_games(chat_id):
    try:
        sql.execute(f"CREATE TABLE IF NOT EXISTS games_{chat_id} (enabled INTEGER DEFAULT 0)")
        sql.execute(f"SELECT enabled FROM games_{chat_id}")
        current = sql.fetchone()
        new_state = 0 if (current and current[0] == 1) else 1
        
        if current:
            sql.execute(f"UPDATE games_{chat_id} SET enabled = ?", (new_state,))
        else:
            sql.execute(f"INSERT INTO games_{chat_id} VALUES (?)", (new_state,))
        
        database.commit()
        return new_state == 1
    except Exception as e:
        print(f"Ошибка toggle_games: {e}")
        return False

def get_bonus(user_id, chat_id):
    try:
        sql.execute(f"CREATE TABLE IF NOT EXISTS bonuses_{chat_id} (user_id INTEGER, last_bonus INTEGER, streak INTEGER, coins INTEGER)")
        current_time = int(time.time())
        sql.execute(f"SELECT last_bonus, streak, coins FROM bonuses_{chat_id} WHERE user_id = {user_id}")
        result = sql.fetchone()
        
        if not result:
            # Проверяем глобальные монеты
            sql.execute(f"SELECT coins FROM global_coins WHERE user_id = {user_id}")
            global_coins = sql.fetchone()
            initial_coins = global_coins[0] + 10 if global_coins else 10
            sql.execute(f"INSERT INTO bonuses_{chat_id} VALUES (?, ?, 1, ?)", (user_id, current_time, initial_coins))
            if global_coins:
                sql.execute(f"DELETE FROM global_coins WHERE user_id = {user_id}")
            database.commit()
            return 10, 1
        
        last_bonus, streak, coins = result
        
        if current_time - last_bonus < 21600:  # 6 часов
            return 0, streak
        
        if current_time - last_bonus <= 43200:  # 12 часов
            new_streak = streak + 1
        else:
            new_streak = 1
        
        bonus_amount = 10 + (new_streak - 1) * 10

        # Проверяем VIP статус для бонуса
        try:
            sql.execute(f"SELECT vip_type FROM vip_statuses WHERE user_id = {user_id} AND chat_id = {chat_id}")
            vip_result = sql.fetchone()
            if vip_result:
                vip_type = vip_result[0]
                if vip_type == 'gold':
                    bonus_amount = int(bonus_amount * 1.5)  # 50% больше
                elif vip_type == 'elite':
                    bonus_amount = int(bonus_amount * 2)  # двойной
                elif vip_type == 'diamond':
                    bonus_amount = int(bonus_amount * 3)  # тройной
        except:
            pass

        new_coins = coins + bonus_amount
        
        sql.execute(f"UPDATE bonuses_{chat_id} SET last_bonus = ?, streak = ?, coins = ? WHERE user_id = ?", 
                   (current_time, new_streak, new_coins, user_id))
        database.commit()
        
        return bonus_amount, new_streak
    except Exception as e:
        print(f"Ошибка get_bonus: {e}")
        return 0, 0



def is_married(user_id, chat_id):
    try:
        sql.execute(f"CREATE TABLE IF NOT EXISTS marriages_{chat_id} (user1 INTEGER, user2 INTEGER, date INTEGER)")
        sql.execute(f"SELECT user1, user2 FROM marriages_{chat_id} WHERE user1 = {user_id} OR user2 = {user_id}")
        return sql.fetchone() is not None
    except:
        return False

def get_marriage_partner(user_id, chat_id):
    try:
        sql.execute(f"CREATE TABLE IF NOT EXISTS marriages_{chat_id} (user1 INTEGER, user2 INTEGER, date INTEGER)")
        sql.execute(f"SELECT user1, user2 FROM marriages_{chat_id} WHERE user1 = {user_id} OR user2 = {user_id}")
        result = sql.fetchone()
        if result:
            return result[1] if result[0] == user_id else result[0]
        return None
    except:
        return None

def marry_users(user1, user2, chat_id):
    try:
        sql.execute(f"CREATE TABLE IF NOT EXISTS marriages_{chat_id} (user1 INTEGER, user2 INTEGER, date INTEGER)")
        sql.execute(f"INSERT INTO marriages_{chat_id} VALUES (?, ?, ?)", (user1, user2, int(time.time())))
        database.commit()
    except Exception as e:
        print(f"Ошибка marry_users: {e}")

def get_user_stats(user_id, chat_id):
    try:
        sql.execute(f"CREATE TABLE IF NOT EXISTS user_stats_{chat_id} (user_id INTEGER, join_date INTEGER, inviter INTEGER, messages INTEGER DEFAULT 0)")
        database.commit()
        
        sql.execute(f"SELECT join_date, inviter, messages FROM user_stats_{chat_id} WHERE user_id = {user_id}")
        result = sql.fetchone()
        if result:
            return result
        else:
            # Создаем запись если нет
            sql.execute(f"INSERT INTO user_stats_{chat_id} VALUES (?, ?, 0, 0)", (user_id, int(time.time())))
            database.commit()
            return (int(time.time()), 0, 0)
    except:
        return (int(time.time()), 0, 0)

def get_warn_count(user_id, chat_id):
    try:
        sql.execute(f"CREATE TABLE IF NOT EXISTS warns_{chat_id} (user_id INTEGER, count INTEGER, moder INTEGER, reason TEXT, date INTEGER)")
        sql.execute(f"SELECT count FROM warns_{chat_id} WHERE user_id = {user_id}")
        result = sql.fetchone()
        return result[0] if result else 0
    except:
        return 0

def get_mute_info(user_id, chat_id):
    try:
        sql.execute(f"CREATE TABLE IF NOT EXISTS mutes_{chat_id} (user_id INTEGER, moder INTEGER, reason TEXT, end_time INTEGER)")
        try:
            sql.execute(f"ALTER TABLE mutes_{chat_id} ADD COLUMN end_time INTEGER DEFAULT 0")
        except:
            pass
        sql.execute(f"SELECT end_time FROM mutes_{chat_id} WHERE user_id = {user_id}")
        result = sql.fetchone()
        if result and int(time.time()) < result[0]:
            return result[0]
        return None
    except:
        return None



def main_loop():
    """Основной цикл бота с обработкой ошибок"""
    global longpoll, processed_messages, vk_session, vk, command_cooldown
    
    print("[MAIN] Запуск основного цикла бота...")
    reconnect_attempts = 0
    max_reconnect_attempts = 5
    
    while True:
        try:
            for event in longpoll.listen():
                try:
                    process_event(event)
                    reconnect_attempts = 0  # Сбрасываем счетчик при успешной обработке
                except Exception as event_error:
                    print(f"[EVENT ERROR] Ошибка обработки события: {event_error}")
                    continue
        except Exception as e:
            error_str = str(e)
            print(f"[MAIN ERROR] Ошибка подключения: {error_str}")
            
            # Проверяем тип ошибки
            error_type = "unknown"
            for proxy_error in ERROR_HANDLING['proxy_errors']:
                if proxy_error in error_str:
                    error_type = "proxy"
                    if LOGGING_SETTINGS['verbose_errors']:
                        print("[MAIN] Обнаружена проблема с прокси/соединением")
                    break
            
            for retry_error in ERROR_HANDLING['retry_errors']:
                if retry_error in error_str:
                    error_type = "retry"
                    if LOGGING_SETTINGS['verbose_errors']:
                        print("[MAIN] Превышено максимальное количество попыток")
                    break
            
            # Проверяем критические ошибки
            for critical_error in ERROR_HANDLING['critical_errors']:
                if critical_error in error_str:
                    print(f"[MAIN CRITICAL] Критическая ошибка: {critical_error}")
                    return  # Выходим из функции
            
            reconnect_attempts += 1
            max_attempts = CONNECTION_SETTINGS['max_reconnect_attempts']
            if reconnect_attempts > max_attempts:
                print(f"[MAIN CRITICAL] Превышено максимальное количество попыток переподключения ({max_attempts})")
                print(f"[MAIN] Увеличиваем время ожидания до {CONNECTION_SETTINGS['max_reconnect_delay']} секунд...")
                time.sleep(CONNECTION_SETTINGS['max_reconnect_delay'])
                reconnect_attempts = 0
            else:
                base_delay = CONNECTION_SETTINGS['base_reconnect_delay']
                max_delay = CONNECTION_SETTINGS['max_reconnect_delay']
                wait_time = min(base_delay * reconnect_attempts, max_delay)
                if LOGGING_SETTINGS['log_reconnections']:
                    print(f"[MAIN] Попытка переподключения #{reconnect_attempts} через {wait_time} секунд...")
                time.sleep(wait_time)
            
            # Очищаем кэш при переподключении
            processed_messages.clear()
            
            try:
                # Пересоздаем сессию VK API
                vk_session = vk_api.VkApi(token=config['bot-token'])
                vk = vk_session.get_api()
                longpoll = VkBotLongPoll(vk_session, group_id, wait=CONNECTION_SETTINGS['wait_time'])
                print("[MAIN] Переподключение успешно!")
            except Exception as reconnect_error:
                print(f"[MAIN ERROR] Ошибка переподключения: {reconnect_error}")
            continue

def process_event(event):
    global processed_messages
    
    # Обработка callback кнопок
    if event.type == VkBotEventType.MESSAGE_EVENT:
        try:
            payload = json.loads(event.obj.payload)
            if payload.get('cmd') == 'mtop':
                page = payload.get('page', 1)
                chat_id = payload.get('chat')
                peer_id = event.obj.peer_id
                
                # Удаляем предыдущее сообщение
                try:
                    vk.messages.delete(
                        message_ids=event.obj.conversation_message_id,
                        delete_for_all=1
                    )
                except:
                    pass
                
                # Отправляем новую страницу
                handle_mtop(chat_id, event.obj.user_id, peer_id, page, sql, vk, send_message, get_user_info, get_nick)
        except Exception as e:
            print(f"[CALLBACK ERROR] {e}")
        return
    
    if event.type != VkBotEventType.MESSAGE_NEW:
        return
    
    try:
        # Получаем основные данные сообщения в начале
        message_text = event.obj.message.get('text', '')
        message_id = event.obj.message.get('id')
        conversation_message_id = event.obj.message.get('conversation_message_id')
        from_id = event.obj.message['from_id']
        peer_id = event.obj.message['peer_id']
        
        # Создаем уникальный ключ для сообщения
        message_key = f"{peer_id}_{conversation_message_id}"
        
        # Проверяем, не обрабатывали ли мы уже это сообщение
        current_time = int(time.time())
        if message_key in processed_messages:
            # Если сообщение было обработано менее 5 секунд назад, игнорируем
            if current_time - processed_messages[message_key] < 5:
                return  # Убираем логирование дубликатов
        
        # Добавляем сообщение в кэш
        processed_messages[message_key] = current_time
        
        # Логирование сообщений
        if LOGGING_SETTINGS['log_commands_only']:
            if message_text.startswith(('/', '!', '+')):
                print(f"[PROCESS] Обрабатываем команду от {from_id}: {message_text[:50]}...")
        else:
            print(f"[PROCESS] Обрабатываем сообщение от {from_id}: {message_text[:50]}...")
        
        # Очищаем старые записи из кэша
        if len(processed_messages) > MAX_CACHE_SIZE:
            cleanup_interval = CONNECTION_SETTINGS['cache_cleanup_interval']
            old_keys = [k for k, v in processed_messages.items() if current_time - v > cleanup_interval]
            for key in old_keys:
                del processed_messages[key]
        
        # Проверяем действия в чате
        if 'action' in event.obj.message:
            action = event.obj.message['action']
            peer_id = event.obj.message['peer_id']
            from_id = event.obj.message['from_id']
            chat_id = peer_id - 2000000000 if peer_id > 2000000000 else 0
            
            # Проверяем выход пользователя
            if action['type'] == 'chat_kick_user':
                kicked_user = action.get('member_id')

                # Сбрасываем предупреждения при любом выходе (кик или сам вышел)
                if chat_id > 0 and check_chat(chat_id):
                    try:
                        sql.execute(f"DELETE FROM warns_{chat_id} WHERE user_id = ?", (kicked_user,))
                        database.commit()
                    except:
                        pass

                # Если пользователь сам вышел (не бот кикнул)
                if kicked_user == from_id and chat_id > 0 and check_chat(chat_id):
                    try:
                        user_nick = get_nick(kicked_user, chat_id) or get_user_info(kicked_user)
                        
                        # Удаляем роль и ник при выходе
                        old_role = get_role(kicked_user, chat_id)
                        if old_role > 0:
                            set_role(kicked_user, chat_id, 0)
                        
                        if user_nick != get_user_info(kicked_user):
                            sql.execute(f"DELETE FROM nicks_{chat_id} WHERE user_id = ?", (kicked_user,))
                            database.commit()
                        
                        # Сообщение о выходе
                        message = f"🚪 {get_mention(kicked_user, chat_id)} покинул беседу\n"
                        if old_role > 0:
                            message += f"👑 Автоматически снята роль: {get_role_name(old_role)}\n"
                        if user_nick != get_user_info(kicked_user):
                            message += f"🏷️ Автоматически удален ник: {user_nick}\n"
                        message += f"⛔ Может вернуться только по приглашению"
                        send_message(peer_id, message)

                        # Кикаем пользователя без сообщений
                        kick_user(chat_id, kicked_user)

                    except Exception as e:
                        print(f"Ошибка автокика: {e}")
            
            if action['type'] == 'chat_invite_user':
                invited_user = action.get('member_id')
                
                # Если добавили нашего бота
                if invited_user == -group_id:
                    welcome_msg = "✨ Благодарим за добавление бота!\n\n"
                    welcome_msg += "🚀 Чтобы запустить бота, сначала предоставьте ему права администратора, после этого нажмите кнопку «Активировать» либо отправьте команду /start.\n\n"
                    welcome_msg += "📚 Список доступных команд: "
                    
                    keyboard = VkKeyboard(inline=True)
                    keyboard.add_button("Активировать", color=VkKeyboardColor.POSITIVE, payload={"cmd": "start"})
                    
                    send_message(event.obj.message['peer_id'], welcome_msg, keyboard=keyboard)
                    return
                
                # Восстанавливаем монеты пользователя при входе в чат
                if chat_id > 0 and check_chat(chat_id) and invited_user > 0:
                    try:
                        sql.execute(f"SELECT coins FROM global_coins WHERE user_id = {invited_user}")
                        global_coins = sql.fetchone()
                        if global_coins:
                            sql.execute(f"CREATE TABLE IF NOT EXISTS bonuses_{chat_id} (user_id INTEGER, last_bonus INTEGER, streak INTEGER, coins INTEGER)")
                            sql.execute(f"INSERT OR REPLACE INTO bonuses_{chat_id} VALUES (?, 0, 0, ?)", (invited_user, global_coins[0]))
                            sql.execute(f"DELETE FROM global_coins WHERE user_id = {invited_user}")
                            database.commit()
                    except:
                        pass
                
                # Проверяем забаненных и кикнутых пользователей
                if chat_id > 0 and check_chat(chat_id) and invited_user > 0:
                    
                    # Проверяем кикнутых (самокик)
                    try:
                        sql.execute(f"SELECT user_id FROM kicked_{chat_id} WHERE user_id = {invited_user}")
                        if sql.fetchone() and from_id == invited_user:
                            # Пользователь пытается вернуться сам - просто кикаем
                            kick_user(chat_id, invited_user)
                            return
                        elif sql.fetchone() and from_id != invited_user:
                            # Пользователя пригласили - удаляем из списка
                            sql.execute(f"DELETE FROM kicked_{chat_id} WHERE user_id = {invited_user}")
                            database.commit()
                    except:
                        pass
                    
                    # Проверяем бан
                    if is_banned(invited_user, chat_id):
                        try:
                            # Получаем информацию о бане
                            sql.execute(f"SELECT moder, reason, date, ban_until FROM bans_{chat_id} WHERE user_id = {invited_user}")
                            ban_info = sql.fetchone()
                            
                            if ban_info:
                                moder_id, reason, ban_date, ban_until = ban_info
                                
                                # Кикаем пользователя
                                kick_user(chat_id, invited_user)
                                
                                # Формируем сообщение
                                user_nick = get_nick(invited_user, chat_id) or get_user_info(invited_user)
                                moder_nick = get_nick(moder_id, chat_id) or get_user_info(moder_id)
                                
                                ban_date_str = datetime.fromtimestamp(ban_date).strftime('%d.%m.%Y %H:%M')
                                
                                message = f"⛔ Данный пользователь {get_mention(invited_user, chat_id)} находится в бане\n"
                                message += f"👤 Никнейм Администратора: {get_mention(moder_id, chat_id)}\n"
                                message += f"📝 Причина бана: {reason}\n"
                                message += f"📅 Дата блокировки: {ban_date_str}\n"
                                
                                if ban_until > 0:
                                    unban_date_str = datetime.fromtimestamp(ban_until).strftime('%d.%m.%Y %H:%M')
                                    message += f"🔓 Дата разблокировки: {unban_date_str}"
                                else:
                                    message += f"🔓 Дата разблокировки: Перманентный бан"
                                
                                send_message(peer_id, message)
                        except Exception as e:
                            print(f"Ошибка проверки бана: {e}")
        
        # Определяем chat_id для бесед
        
        # Определяем chat_id для бесед
        chat_id = peer_id - 2000000000 if peer_id > 2000000000 else 0
        
        # Обновляем статистику сообщений
        if chat_id > 0 and check_chat(chat_id):
            try:
                sql.execute(f"CREATE TABLE IF NOT EXISTS user_stats_{chat_id} (user_id INTEGER, join_date INTEGER, inviter INTEGER, messages INTEGER DEFAULT 0)")
                sql.execute(f"SELECT messages FROM user_stats_{chat_id} WHERE user_id = {from_id}")
                if sql.fetchone():
                    sql.execute(f"UPDATE user_stats_{chat_id} SET messages = messages + 1 WHERE user_id = {from_id}")
                else:
                    sql.execute(f"INSERT INTO user_stats_{chat_id} VALUES (?, ?, 0, 1)", (from_id, int(time.time())))
                database.commit()
            except:
                pass
        
        # Парсим команду
        args = message_text.split()
        if not args:
            return
            
        command = args[0].lower()
        
        # Обработка кнопок навигации mtop
        if chat_id > 0 and check_chat(chat_id) and ("◀" in message_text or "▶" in message_text or "назад" in message_text.lower() or "вперед" in message_text.lower()):
            # Проверяем права на использование mtop
            if get_role(from_id, chat_id) >= 20:
                if handle_mtop_navigation(message_text, chat_id, from_id, peer_id, message_id, sql, vk, send_message, get_user_info, get_nick):
                    return
        
        # Команды с префиксами
        if command.startswith(('/', '!', '+')):
            cmd = command[1:]
            
            # Проверяем кулдаун команд
            command_key = f"{from_id}_{cmd}"
            current_time = int(time.time())
            if command_key in command_cooldown:
                if current_time - command_cooldown[command_key] < COMMAND_COOLDOWN_TIME:
                    return  # Игнорируем команду в кулдауне
            
            command_cooldown[command_key] = current_time
            
            # Очищаем старые записи кулдауна
            if len(command_cooldown) > 500:
                cleanup_interval = CONNECTION_SETTINGS['cache_cleanup_interval']
                old_cooldowns = [k for k, v in command_cooldown.items() if current_time - v > cleanup_interval]
                for key in old_cooldowns:
                    del command_cooldown[key]
            

            

            
            # Убираем reply_to - он вызывает ошибки
            reply_to = None
            
            # Проверяем активацию чата (кроме команды start)
            if chat_id > 0 and cmd not in ['start', 'старт'] and not check_chat(chat_id):
                send_message(peer_id, "❌ Беседа не активирована, используйте /start", reply_to)
                return
            
            # Команда notif
            if cmd in ['notif', 'уведомление']:
                if not is_bot_admin(from_id):
                    send_message(peer_id, "❌ Недостаточно прав! Команда доступна только администраторам бота!", reply_to)
                    return
                
                if len(args) < 2:
                    send_message(peer_id, "❌ Укажите текст уведомления!\nПример: /notif Текст сообщения", reply_to)
                    return
                
                notification_text = ' '.join(args[1:])
                
                notification_msg = f"📢 Важное уведомление от администрации бота\n"
                notification_msg += f"👤 Отправитель: {get_user_info(from_id)}\n\n"
                notification_msg += notification_text
                
                # Отправляем во все чаты
                sql.execute("SELECT peer_id FROM chats")
                all_chats = sql.fetchall()
                success_count = 0
                for chat in all_chats:
                    try:
                        send_message(chat[0], notification_msg)
                        success_count += 1
                    except:
                        pass
                
                send_message(peer_id, f"✅ Уведомление отправлено в {success_count} чатов!", reply_to)
                return
            
            # Команда stop
            elif cmd in ['stop', 'стоп']:
                if chat_id == 0 or not check_chat(chat_id):
                    return
                if not is_bot_admin(from_id):
                    send_message(peer_id, "❌ Недостаточно прав! Команда доступна только модераторам бота и выше!", reply_to)
                    return
                try:
                    # Удаляем все таблицы чата
                    tables_to_drop = [
                        f"permissions_{chat_id}", f"nicks_{chat_id}", f"warns_{chat_id}",
                        f"bans_{chat_id}", f"games_{chat_id}", f"bonuses_{chat_id}",
                        f"marriages_{chat_id}", f"user_stats_{chat_id}", f"mutes_{chat_id}",
                        f"kicked_{chat_id}", f"marriage_proposals_{chat_id}", f"transfer_pending_{chat_id}"
                    ]
                    for table in tables_to_drop:
                        try:
                            sql.execute(f"DROP TABLE IF EXISTS {table}")
                        except:
                            pass
                    
                    # Удаляем запись из основной таблицы
                    sql.execute(f"DELETE FROM chats WHERE chat_id = {chat_id}")
                    database.commit()
                    send_message(peer_id, "✅ Беседа полностью удалена из базы данных! Для повторной активации используйте /start", reply_to)
                except Exception as e:
                    send_message(peer_id, f"❌ Ошибка деактивации: {str(e)}", reply_to)
            
            # Команда start
            elif cmd in ['start', 'старт']:
                if chat_id == 0:
                    send_message(peer_id, "🚫 Эта команда работает только в беседах!", reply_to)
                    return
                    
                if check_chat(chat_id):
                    send_message(peer_id, "✅ Бот уже активирован!\n", reply_to)
                    return
                
                try:
                    # Проверяем, является ли пользователь создателем беседы
                    try:
                        members = vk.messages.getConversationMembers(peer_id=peer_id)
                        is_owner = False
                        for member in members['items']:
                            if member['member_id'] == from_id and member.get('is_owner'):
                                is_owner = True
                                break
                        
                        if not is_owner and from_id != BOT_OWNER_ID:
                            send_message(peer_id, "🚫 Активировать бота может только создатель беседы!", reply_to)
                            return
                    except Exception as e:
                        # Если не админ, может не дать список. Но для активации админка нужна.
                        print(f"Ошибка проверки создателя: {e}")
                        # Если не удалось проверить (нет админки), но команда вызвана - требуем админку
                        # Но если бот не админ, он может не видеть всех.
                        # Впрочем, start часто вызывают когда бот уже админ.
                        pass

                    new_chat(chat_id, peer_id, from_id)
                    
                    # Выдаем права владельца (100)
                    set_role(from_id, chat_id, 100)
                    
                    welcome_msg = "🎉 Бот успешно активирован!\n"
                    welcome_msg += "👑 Вам выданы права Владельца Проекта (level 100)!"
                    send_message(peer_id, welcome_msg, reply_to)
                except Exception as e:
                    send_message(peer_id, f"❌ Ошибка активации: {str(e)}", reply_to)
            
            # Команда help
            elif cmd in ['help', 'хелп', 'помощь']:
                if chat_id > 0 and not check_chat(chat_id):
                    return
                    
                user_role = get_role(from_id, chat_id) if chat_id > 0 else 0
                
                # Определяем название роли для отображения
                role_name = get_role_name(user_role, chat_id)
                
                help_text = f"💎 SHADOW MANAGER — Список доступных команд\n"
                help_text += f"━━━━━━━━━━━━━━\n\n"
                
                # --- Пользовательские команды (0+) ---
                help_text += f"👤 Пользовательские команды:\n"
                help_text += f"• /id — Узнать свой ID или ID пользователя\n"
                help_text += f"• /bonus — Получить ежедневный бонус\n"
                help_text += f"• /stats — Посмотреть свою статистику\n"
                help_text += f"• /ping — Проверить работоспособность\n"
                help_text += f"• /online — Список участников в сети\n"
                help_text += f"• /roles — Иерархия всех ролей чата\n"
                help_text += f"• /shop — Магазин VIP-статусов\n"
                help_text += f"• /transfer [сумма] — Перевод монет\n"
                help_text += f"• /q — Покинуть беседу (самокик)\n"
                help_text += f"• /брак /дуэль /игры — Развлечения\n\n"
                
                # --- Команды Администратора (40+) ---
                if user_role >= 40:
                    help_text += f"👮 Команды Администратора (40+):\n"
                    help_text += f"• /kick — Исключить пользователя\n"
                    help_text += f"• /warn — Выдать предупреждение\n"
                    help_text += f"• /unwarn — Снять предупреждение\n"
                    help_text += f"• /mute [мин] [причина] — Выдать мут\n"
                    help_text += f"• /unmute — Снять блокировку чата\n"
                    help_text += f"• /getban — Информация о блокировке\n\n"
                    
                # --- Команды Куратора (60+) ---
                if user_role >= 60:
                    help_text += f"👔 Команды Куратора (60+):\n"
                    help_text += f"• /ban — Заблокировать в беседе\n"
                    help_text += f"• /banlist — Список заблокированных\n"
                    help_text += f"• /warnlist — Список предупреждений\n"
                    help_text += f"• /mutelist — Список замученных\n"
                    help_text += f"• /удалить — Удалить сообщение (ответ)\n\n"
                    
                # --- Команды Руководства (70+) ---
                if user_role >= 70:
                    help_text += f"🏢 Команды Заместителя Главного Администратора (70+):\n"
                    help_text += f"• /unban — Разблокировать пользователя\n"
                    help_text += f"• /gban <user> — Глобальный бан\n"
                    help_text += f"• /gwarn <user> — Глобальный варн\n"
                    help_text += f"• /gunwarn <user> — Глобальное снятие варна\n"
                    help_text += f"• /gunmute <user> — Глобальный размут\n"
                    help_text += f"• /gmute <user> — Глобальный мут\n\n"
                    if user_role >= 90:
                        help_text += f"🏢 Команды Специального Администратора (90+)\n"
                        help_text += f"• /quiet, /тишина — Включить/выключить режим тишины\n\n"
                    if user_role >= 99:
                        help_text += f"🏢 Команды Владельца беседы (99+)\n"
                        help_text += f"• /start — Запуск\n"
                        help_text += f"• /transfervl <user> — Передать права владельца\n"
                        help_text += f"• /pull — Управление сеткой бесед\n"
                        help_text += f"• /resetrole <level> — Сбросить название роли\n"
                        help_text += f"• /delrole [lvl] — Сбросить/скрыть роль\n"
                        help_text += f"• /ping — Статус бота и задержка\n"
                    help_text += f"\n"

                help_text += f"━━━━━━━━━━━━━━\n"
                
                send_message(peer_id, help_text, reply_to)
            
            # Команда pull
            elif cmd in ['pull']:
                if chat_id == 0 or not check_chat(chat_id):
                    return
                    
                if get_role(from_id, chat_id) < 100:
                    send_message(peer_id, "❌ Недостаточно прав!", reply_to)
                    return

                if len(args) < 2:
                    current_pull_id = get_chat_pull_id(chat_id)
                    if current_pull_id:
                        pull_chats = get_pull_by_id(current_pull_id)
                        message = f"🔗 Текущий ID объединения: {current_pull_id}\n"
                        message += f"📊 Чатов в объединении: {len(pull_chats)}\n\n"
                        message += f"💡 Использование:\n"
                        message += f"• /pull - показать текущее объединение\n"
                        message += f"• /pull [название] - подключить чат или создать новое объединение\n"
                        message += f"• /removepull - отключить чат от объединения"
                        send_message(peer_id, message, reply_to)
                    else:
                        new_pull_id = generate_pull_id()
                        set_pull_id(chat_id, new_pull_id)
                        message = f"✅ Создано новое объединение чатов!\n"
                        message += f"🆔 ID объединения: {new_pull_id}\n\n"
                        message += f"📋 Скопируйте этот ID и используйте команду:\n"
                        message += f"/pull {new_pull_id}\n"
                        message += f"в других чатах для их объединения"
                        send_message(peer_id, message, reply_to)
                    return

                pull_arg = args[1]
                
                if pull_arg.lower() == 'off':
                    current_pull_id = get_chat_pull_id(chat_id)
                    if current_pull_id:
                        sql.execute("UPDATE chats SET pull_id = NULL WHERE chat_id = ?", (chat_id,))
                        database.commit()
                        send_message(peer_id, "✅ Чат отключен от объединения", reply_to)
                    else:
                        send_message(peer_id, "❌ Чат не находится в объединении", reply_to)
                    return

                # Подключение к объединению или создание своего
                existing_chats = get_pull_by_id(pull_arg)
                if not existing_chats:
                    # Создаем новое с этим названием
                    set_pull_id(chat_id, pull_arg)
                    message = f"✅ Создано новое объединение с вашим названием!\n"
                    message += f"🆔 ID объединения: {pull_arg}\n"
                    send_message(peer_id, message, reply_to)
                else:
                    set_pull_id(chat_id, pull_arg)
                    message = f"✅ Чат успешно подключен к объединению!\n"
                    message += f"🆔 ID объединения: {pull_arg}\n"
                    message += f"📊 Всего чатов в объединении: {len(existing_chats) + 1}"
                    send_message(peer_id, message, reply_to)

            # Команда q (выход с киком)
            elif cmd in ['q', 'quit']:
                if chat_id == 0 or not check_chat(chat_id):
                    return
                # Кикнуть пользователя без сообщений
                kick_user(chat_id, from_id)
                return
            
            # Команда pull_info
            elif cmd in ['pullinfo', 'pull_info']:
                if chat_id == 0 or not check_chat(chat_id):
                    return
                    
                if get_role(from_id, chat_id) < 100:
                    send_message(peer_id, "❌ Недостаточно прав!", reply_to)
                    return

                pull_id = get_chat_pull_id(chat_id)
                pull_chats = get_pull_chats(chat_id)
                
                if not pull_id or not pull_chats:
                    message = "📋 Информация об объединении чатов:\n\n"
                    message += "❌ Чат не находится в объединении\n\n"
                    message += "💡 Используйте /pull для создания или подключения к объединению"
                    send_message(peer_id, message, reply_to)
                else:
                    try:
                        message = f"📋 Информация об объединении чатов:\n\n"
                        message += f"🆔 ID объединения: {pull_id}\n"
                        message += f"💬 Всего чатов в объединении: {len(pull_chats)}\n\n"
                        
                        # Получаем названия чатов
                        message += "📝 Чаты в объединении:\n"
                        for i, target_chat in enumerate(pull_chats, 1):
                            try:
                                target_peer_id = target_chat + 2000000000
                                conv = vk.messages.getConversationsById(peer_ids=target_peer_id)
                                title = conv['items'][0]['chat_settings']['title']
                                message += f"{i}. {title}\n"
                            except:
                                message += f"{i}. Чат {target_chat}\n"
                        
                        message += f"\n🌐 Глобальные команды работают во всех {len(pull_chats)} чатах"
                        send_message(peer_id, message, reply_to)
                    except Exception as e:
                        message = f"📋 Информация об объединении чатов:\n\n"
                        message += f"🆔 ID объединения: {pull_id}\n"
                        message += f"💬 Всего чатов: {len(pull_chats)}\n"
                        message += f"🌐 Глобальные команды работают во всех чатах"
                        send_message(peer_id, message, reply_to)

            # Команда removepull - убрать беседу с пулла
            elif cmd in ['removepull']:
                if chat_id == 0 or not check_chat(chat_id):
                    return
                if get_role(from_id, chat_id) < 100:
                    send_message(peer_id, "❌ Недостаточно прав!", reply_to)
                    return
                
                current_pull_id = get_chat_pull_id(chat_id)
                if current_pull_id:
                    sql.execute("UPDATE chats SET pull_id = NULL WHERE chat_id = ?", (chat_id,))
                    database.commit()
                    send_message(peer_id, f"✅ Чат успешно исключен из объединения «{current_pull_id}»", reply_to)
                else:
                    send_message(peer_id, "❌ Чат не находится в объединении", reply_to)

            # Команда delpull - удалить пулл полностью
            elif cmd in ['delpull']:
                if chat_id == 0 or not check_chat(chat_id):
                    return
                if get_role(from_id, chat_id) < 100:
                    send_message(peer_id, "❌ Недостаточно прав!", reply_to)
                    return
                
                current_pull_id = get_chat_pull_id(chat_id)
                if current_pull_id:
                    sql.execute("UPDATE chats SET pull_id = NULL WHERE pull_id = ?", (current_pull_id,))
                    database.commit()
                    send_message(peer_id, f"🗑️ Объединение «{current_pull_id}» полностью удалено.\n🔓 Все чаты ({len(pull_chats)}) теперь работают независимо.", reply_to)
                else:
                    send_message(peer_id, "❌ Чат не находится в объединении", reply_to)
            
            # Глобальные команды
            elif cmd in ['gmute', 'гмут']:
                if chat_id == 0 or not check_chat(chat_id):
                    return
                    
                if get_role(from_id, chat_id) < 60:
                    send_message(peer_id, "❌ Недостаточно прав!", reply_to)
                    return

                target_id = get_user_from_reply_or_mention(event.obj, args, 1)
                if not target_id:
                    send_message(peer_id, "❌ Укажите пользователя!", reply_to)
                    return

                if get_role(from_id, chat_id) <= get_role(target_id, chat_id):
                    send_message(peer_id, "❌ Вы не можете замутить данного пользователя!", reply_to)
                    return

                # Определяем время и причину
                if 'reply_message' in event.obj.message:
                    if len(args) < 2:
                        send_message(peer_id, "❌ Укажите время и причину!\nПример: /gmute 30 Спам", reply_to)
                        return
                    try:
                        mute_time = int(args[1])
                        reason = ' '.join(args[2:]) if len(args) > 2 else "Причина не указана"
                    except:
                        send_message(peer_id, "❌ Укажите время в минутах!", reply_to)
                        return
                else:
                    if len(args) < 4:
                        send_message(peer_id, "❌ Укажите время и причину!\nПример: /gmute @user 30 Спам", reply_to)
                        return
                    try:
                        mute_time = int(args[2])
                        reason = ' '.join(args[3:]) if len(args) > 3 else "Причина не указана"
                    except:
                        send_message(peer_id, "❌ Укажите время в минутах!", reply_to)
                        return

                if mute_time < 1 or mute_time > 1000:
                    send_message(peer_id, "❌ Время должно быть от 1 до 1000 минут!", reply_to)
                    return

                pull_chats = get_pull_chats(chat_id)
                if not pull_chats:
                    send_message(peer_id, "❌ Чат не находится в объединении!", reply_to)
                    return

                for target_chat in pull_chats:
                    try:
                        mute_user(target_id, target_chat, from_id, reason, mute_time)
                    except:
                        pass

                moder_nick = get_nick(from_id, chat_id) or get_user_info(from_id)
                message = f"🔇 Глобальный мут выдан!\n"
                message += f"👤 Пользователь: {get_mention(target_id, chat_id)}\n"
                message += f"👮 Администратор: {get_mention(from_id, chat_id)}\n"
                message += f"⏰ Время: {mute_time} минут\n"
                message += f"📝 Причина: {reason}"
                send_to_all_pull_chats(chat_id, message)
            
            elif cmd in ['gban', 'гбан']:
                if chat_id == 0 or not check_chat(chat_id):
                    return
                    
                if get_role(from_id, chat_id) < 70:
                    send_message(peer_id, "❌ Недостаточно прав! Команда доступна с Спец. Администратора!", reply_to)
                    return

                target_id = get_user_from_reply_or_mention(event.obj, args, 1)
                if not target_id:
                    send_message(peer_id, "❌ Укажите пользователя!", reply_to)
                    return

                if get_role(from_id, chat_id) <= get_role(target_id, chat_id):
                    send_message(peer_id, "❌ Вы не можете забанить данного пользователя!", reply_to)
                    return

                # Определяем время и причину
                days = 0
                duration = 0
                if 'reply_message' in event.obj.message:
                    try:
                        days = int(args[1])
                        reason = ' '.join(args[2:]) if len(args) > 2 else "Причина не указана"
                        duration = days * 1440
                    except:
                        reason = ' '.join(args[1:]) if len(args) > 1 else "Причина не указана"
                else:
                    try:
                        days = int(args[2])
                        reason = ' '.join(args[3:]) if len(args) > 3 else "Причина не указана"
                        duration = days * 1440
                    except:
                        reason = ' '.join(args[2:]) if len(args) > 2 else "Причина не указана"

                pull_chats = get_pull_chats(chat_id)
                if not pull_chats:
                    send_message(peer_id, "❌ Чат не находится в объединении!", reply_to)
                    return

                for target_chat in pull_chats:
                    try:
                        ban_user(target_id, target_chat, from_id, reason, duration)
                        kick_user(target_chat, target_id)
                    except:
                        pass

                moder_nick = get_nick(from_id, chat_id) or get_user_info(from_id)
                message = f"🚫 Глобальный бан выдан!\n"
                message += f"👤 Пользователь: {get_mention(target_id, chat_id)}\n"
                message += f"👮 Администратор: {get_mention(from_id, chat_id)}\n"
                if days > 0:
                    message += f"⏰ Срок: {days} дней\n"
                else:
                    message += f"⏰ Срок: Навсегда\n"
                message += f"📝 Причина: {reason}"
                send_to_all_pull_chats(chat_id, message)
            
            elif cmd in ['gunban', 'гразбан']:
                if chat_id == 0 or not check_chat(chat_id):
                    return
                    
                if get_role(from_id, chat_id) < 70:
                    send_message(peer_id, "❌ Недостаточно прав! Команда доступна с Спец. Администратора!", reply_to)
                    return

                target_id = get_user_from_reply_or_mention(event.obj, args, 1)
                if not target_id:
                    send_message(peer_id, "❌ Укажите пользователя!", reply_to)
                    return

                pull_chats = get_pull_chats(chat_id)
                if not pull_chats:
                    send_message(peer_id, "❌ Чат не находится в объединении!", reply_to)
                    return

                for target_chat in pull_chats:
                    try:
                        unban_user(target_id, target_chat)
                    except:
                        pass

                moder_nick = get_nick(from_id, chat_id) or get_user_info(from_id)
                message = f"✅ Глобальный разбан выдан!\n"
                message += f"👤 Пользователь: {get_mention(target_id, chat_id)}\n"
                message += f"👮 Администратор: {get_mention(from_id, chat_id)}"
                send_to_all_pull_chats(chat_id, message)
            
            elif cmd in ['gwarn', 'гварн']:
                if chat_id == 0 or not check_chat(chat_id):
                    return
                    
                if get_role(from_id, chat_id) < 70:
                    send_message(peer_id, "❌ Недостаточно прав! Команда доступна с Спец. Администратора!", reply_to)
                    return

                target_id = get_user_from_reply_or_mention(event.obj, args, 1)
                if not target_id:
                    send_message(peer_id, "❌ Укажите пользователя!", reply_to)
                    return

                if get_role(from_id, chat_id) <= get_role(target_id, chat_id):
                    send_message(peer_id, "❌ Вы не можете выдать предупреждение данному пользователю!", reply_to)
                    return

                # Определяем причину
                if 'reply_message' in event.obj.message:
                    reason = ' '.join(args[1:]) if len(args) > 1 else "Причина не указана"
                else:
                    reason = ' '.join(args[2:]) if len(args) > 2 else "Причина не указана"

                pull_chats = get_pull_chats(chat_id)
                if not pull_chats:
                    send_message(peer_id, "❌ Чат не находится в объединении!", reply_to)
                    return
                
                kick_count = 0
                kick_failed = []
                warn_count = 0
                
                for target_chat in pull_chats:
                    try:
                        target_peer = target_chat + 2000000000
                        
                        sql.execute(f"CREATE TABLE IF NOT EXISTS warns_{target_chat} (user_id INTEGER, count INTEGER, moder INTEGER, reason TEXT, date INTEGER)")
                        database.commit()
                        
                        sql.execute(f"SELECT count FROM warns_{target_chat} WHERE user_id = {target_id}")
                        current = sql.fetchone()
                        old_count = current[0] if current else 0
                        new_count = old_count + 1
                        
                        if current:
                            sql.execute(f"UPDATE warns_{target_chat} SET count = ?, moder = ?, reason = ?, date = ? WHERE user_id = ?", 
                                       (new_count, from_id, reason, int(time.time()), target_id))
                        else:
                            sql.execute(f"INSERT INTO warns_{target_chat} (user_id, count, moder, reason, date) VALUES (?, ?, ?, ?, ?)", 
                                       (target_id, new_count, from_id, reason, int(time.time())))
                        database.commit()
                        
                        sql.execute(f"SELECT count FROM warns_{target_chat} WHERE user_id = {target_id}")
                        verify = sql.fetchone()
                        
                        if verify and verify[0] == new_count:
                            warn_count = verify[0]
                        else:
                            warn_count = new_count
                        
                        if warn_count >= 3:
                            if kick_user(target_chat, target_id):
                                kick_count += 1
                            else:
                                kick_failed.append(target_chat)
                    except Exception as e:
                        pass

                moder_nick = get_nick(from_id, chat_id) or get_user_info(from_id)
                message = f"⚠️ Глобальное предупреждение выдано!\n"
                message += f"👤 Пользователь: {get_mention(target_id, chat_id)}\n"
                message += f"👮 Администратор: {get_mention(from_id, chat_id)}\n"
                message += f"📝 Причина: {reason}"
                if kick_count > 0:
                    message += f"\n🚪 Исключен из {kick_count} чатов за 3 предупреждения"
                if kick_failed:
                    message += f"\n⚠️ {get_mention(target_id, chat_id)} не удалось кикнуть. У пользователя имеется звезда в чате или тех причины."

                send_to_all_pull_chats(chat_id, message)
            
            elif cmd in ['gkick', 'гкик']:
                if chat_id == 0 or not check_chat(chat_id):
                    return
                    
                if get_role(from_id, chat_id) < 60:
                    send_message(peer_id, "❌ Недостаточно прав! Команда доступна с ГС ОПГ/ГОСС!", reply_to)
                    return

                target_id = get_user_from_reply_or_mention(event.obj, args, 1)
                if not target_id:
                    send_message(peer_id, "❌ Укажите пользователя!", reply_to)
                    return

                if get_role(from_id, chat_id) <= get_role(target_id, chat_id):
                    send_message(peer_id, "❌ Вы не можете исключить данного пользователя!", reply_to)
                    return

                # Определяем причину
                if 'reply_message' in event.obj.message:
                    reason = ' '.join(args[1:]) if len(args) > 1 else None
                else:
                    reason = ' '.join(args[2:]) if len(args) > 2 else None

                pull_chats = get_pull_chats(chat_id)
                if not pull_chats:
                    send_message(peer_id, "❌ Чат не находится в объединении!", reply_to)
                    return

                for target_chat in pull_chats:
                    try:
                        kick_user(target_chat, target_id)
                    except:
                        pass

                moder_nick = get_nick(from_id, chat_id) or get_user_info(from_id)
                message = f"🚪 Глобальное исключение выполнено!\n"
                message += f"👤 Пользователь: {get_mention(target_id, chat_id)}\n"
                message += f"👮 Администратор: {get_mention(from_id, chat_id)}"
                if reason:
                    message += f"\n📝 Причина: {reason}"

                send_to_all_pull_chats(chat_id, message)
            
            elif cmd in ['grole', 'гроль']:
                if chat_id == 0 or not check_chat(chat_id):
                    return
                    
                if get_role(from_id, chat_id) < 60:
                    send_message(peer_id, "❌ Недостаточно прав! Команда доступна с ГС ОПГ/ГОСС!", reply_to)
                    return

                target_id = get_user_from_reply_or_mention(event.obj, args, 1)
                if not target_id:
                    send_message(peer_id, "❌ Укажите пользователя!", reply_to)
                    return

                if get_role(from_id, chat_id) <= get_role(target_id, chat_id):
                    send_message(peer_id, "❌ Вы не можете взаимодействовать с данным пользователем!", reply_to)
                    return

                # Определяем уровень роли
                if 'reply_message' in event.obj.message:
                    if len(args) < 2:
                        send_message(peer_id, "❌ Укажите уровень роли!\n\n🎭 Уровни ролей:\n0 - Хелпер/Лидер\n10 - Модератор\n20 - Старший модератор\n25 - Администратор\n30 - Старший Администратор\n40 - Заместитель Главного Следящего\n45 - Главный Следящий\n50 - Куратор Администрации\n60 - Заместитель Главного Администратора\n65 - Главный Администратор\n70 - Специальный Администратор\n75 - Заместитель Руководителя Проекта\n80 - Руководитель Проекта\n90 - Заместитель Основателя\n95 - Основатель Проекта\n99 - Владелец Проекта\n100 - Владелец Проекта", reply_to)
                        return
                    try:
                        role_level = int(args[1])
                    except:
                        send_message(peer_id, "❌ Укажите число!", reply_to)
                        return
                else:
                    if len(args) < 3:
                        send_message(peer_id, "❌ Укажите уровень роли!\n\n🎭 Уровни ролей:\n0 - Хелпер/Лидер\n10 - Модератор\n20 - Старший модератор\n25 - Администратор\n30 - Старший Администратор\n40 - Заместитель Главного Следящего\n45 - Главный Следящий\n50 - Куратор Администрации\n60 - Заместитель Главного Администратора\n65 - Главный Администратор\n70 - Специальный Администратор\n75 - Заместитель Руководителя Проекта\n80 - Руководитель Проекта\n90 - Заместитель Основателя\n95 - Основатель Проекта\n99 - Владелец Проекта\n100 - Владелец Проекта", reply_to)
                        return
                    try:
                        role_level = int(args[2])
                    except:
                        send_message(peer_id, "❌ Укажите число!", reply_to)
                        return

                valid_roles = [0, 10, 20, 25, 30, 40, 45, 50, 60, 65, 70, 75, 80, 90, 95, 100]
                if role_level not in valid_roles:
                    send_message(peer_id, "❌ Уровень роли должен быть одним из допустимых!\n\n🎭 Уровни ролей:\n0 - Хелпер/Лидер\n10 - Модератор\n20 - Старший модератор\n25 - Администратор\n30 - Старший Администратор\n40 - Заместитель Главного Следящего\n45 - Главный Следящий\n50 - Куратор Администрации\n60 - Заместитель Главного Администратора\n65 - Главный Администратор\n70 - Специальный Администратор\n75 - Заместитель Руководителя Проекта\n80 - Руководитель Проекта\n90 - Заместитель Основателя\n95 - Основатель Проекта\n99 - Владелец Проекта\n100 - Владелец Проекта", reply_to)
                    return

                # Конвертируем уровни в новые значения
                level = role_level

                if level >= get_role(from_id, chat_id):
                    send_message(peer_id, "❌ Вы не можете выдать роль выше своей!", reply_to)
                    return

                if level < 0:
                    send_message(peer_id, "❌ Нельзя выдать такую роль!", reply_to)
                    return

                pull_chats = get_pull_chats(chat_id)
                if not pull_chats:
                    send_message(peer_id, "❌ Чат не находится в объединении!", reply_to)
                    return

                for target_chat in pull_chats:
                    try:
                        set_role(target_id, target_chat, level)
                    except:
                        pass

                message = f"👑 Глобальная роль выдана!\n"
                message += f"👤 Пользователь: {get_mention(target_id, chat_id)}\n"
                message += f"🎭 Роль: {get_role_name(level, target_chat)}"  # Добавить chat_id
                # Или для каждого чата в цикле
                send_to_all_pull_chats(chat_id, message)
            
            elif cmd in ['gnick', 'гник']:
                if chat_id == 0 or not check_chat(chat_id):
                    return
                    
                if get_role(from_id, chat_id) < 60:
                    send_message(peer_id, "❌ Недостаточно прав! Команда доступна с ГС ОПГ/ГОСС!", reply_to)
                    return

                target_id = get_user_from_reply_or_mention(event.obj, args, 1)
                if not target_id:
                    send_message(peer_id, "❌ Укажите пользователя!", reply_to)
                    return

                if get_role(from_id, chat_id) <= get_role(target_id, chat_id) and from_id != target_id:
                    send_message(peer_id, "❌ Вы не можете изменить ник данному пользователю!", reply_to)
                    return

                # Определяем ник
                if 'reply_message' in event.obj.message:
                    new_nick = ' '.join(args[1:]) if len(args) > 1 else None
                else:
                    new_nick = ' '.join(args[2:]) if len(args) > 2 else None

                if not new_nick:
                    send_message(peer_id, "❌ Укажите ник!", reply_to)
                    return

                pull_chats = get_pull_chats(chat_id)
                if not pull_chats:
                    send_message(peer_id, "❌ Чат не находится в объединении!", reply_to)
                    return

                for target_chat in pull_chats:
                    try:
                        sql.execute(f"CREATE TABLE IF NOT EXISTS nicks_{target_chat} (user_id INTEGER, nick TEXT)")
                        sql.execute(f"DELETE FROM nicks_{target_chat} WHERE user_id = ?", (target_id,))
                        sql.execute(f"INSERT INTO nicks_{target_chat} VALUES (?, ?)", (target_id, new_nick))
                        database.commit()
                    except Exception as e:
                        print(f"Ошибка gnick в чате {target_chat}: {e}")

                message = f"🏷️ Глобальный ник установлен!\n"
                message += f"👤 Пользователь: {get_mention(target_id, chat_id)}\n"
                message += f"🏷️ Новый ник: {new_nick}"
                send_to_all_pull_chats(chat_id, message)
            
            elif cmd in ['gdelnick', 'гделник']:
                if chat_id == 0 or not check_chat(chat_id):
                    return
                    
                if get_role(from_id, chat_id) < 60:
                    send_message(peer_id, "❌ Недостаточно прав! Команда доступна с ГС ОПГ/ГОСС!", reply_to)
                    return

                target_id = get_user_from_reply_or_mention(event.obj, args, 1)
                if not target_id:
                    send_message(peer_id, "❌ Укажите пользователя!", reply_to)
                    return

                if get_role(from_id, chat_id) <= get_role(target_id, chat_id) and from_id != target_id:
                    send_message(peer_id, "❌ Вы не можете удалить ник данному пользователю!", reply_to)
                    return

                pull_chats = get_pull_chats(chat_id)
                if not pull_chats:
                    send_message(peer_id, "❌ Чат не находится в объединении!", reply_to)
                    return

                for target_chat in pull_chats:
                    try:
                        sql.execute(f"CREATE TABLE IF NOT EXISTS nicks_{target_chat} (user_id INTEGER, nick TEXT)")
                        sql.execute(f"DELETE FROM nicks_{target_chat} WHERE user_id = ?", (target_id,))
                        database.commit()
                    except Exception as e:
                        print(f"Ошибка gdelnick в чате {target_chat}: {e}")

                message = f"🗑️ Глобальное удаление ника!\n"
                message += f"👤 Пользователь: {get_mention(target_id, chat_id)}"
                send_to_all_pull_chats(chat_id, message)
            
            elif cmd in ['gunmute', 'гунмут']:
                if chat_id == 0 or not check_chat(chat_id):
                    return
                    
                if get_role(from_id, chat_id) < 60:
                    send_message(peer_id, "❌ Недостаточно прав! Команда доступна с ГС ОПГ/ГОСС!", reply_to)
                    return

                target_id = get_user_from_reply_or_mention(event.obj, args, 1)
                if not target_id:
                    send_message(peer_id, "❌ Укажите пользователя!", reply_to)
                    return

                if get_role(from_id, chat_id) <= get_role(target_id, chat_id):
                    send_message(peer_id, "❌ Вы не можете размутить данного пользователя!", reply_to)
                    return

                pull_chats = get_pull_chats(chat_id)
                if not pull_chats:
                    send_message(peer_id, "❌ Чат не находится в объединении!", reply_to)
                    return

                for target_chat in pull_chats:
                    try:
                        unmute_user(target_id, target_chat)
                    except:
                        pass

                message = f"🔊 Глобальный размут!\n"
                message += f"👤 Пользователь: {get_mention(target_id, chat_id)}"
                send_to_all_pull_chats(chat_id, message)
            
            elif cmd in ['gunwarn', 'гунварн']:
                if chat_id == 0 or not check_chat(chat_id):
                    return
                    
                if get_role(from_id, chat_id) < 60:
                    send_message(peer_id, "❌ Недостаточно прав!", reply_to)
                    return

                target_id = get_user_from_reply_or_mention(event.obj, args, 1)
                if not target_id:
                    send_message(peer_id, "❌ Укажите пользователя!", reply_to)
                    return

                if get_role(from_id, chat_id) <= get_role(target_id, chat_id):
                    send_message(peer_id, "❌ Вы не можете снять предупреждение данному пользователю!", reply_to)
                    return

                pull_chats = get_pull_chats(chat_id)
                if not pull_chats:
                    send_message(peer_id, "❌ Чат не находится в объединении!", reply_to)
                    return

                for target_chat in pull_chats:
                    try:
                        unwarn_user(target_id, target_chat)
                    except:
                        pass

                message = f"✅ Глобальное снятие предупреждения!\n"
                message += f"👤 Пользователь: {get_mention(target_id, chat_id)}"
                send_to_all_pull_chats(chat_id, message)
            
            elif cmd in ['grnick', 'грник']:
                if chat_id == 0 or not check_chat(chat_id):
                    return
                    
                if get_role(from_id, chat_id) < 60:
                    send_message(peer_id, "❌ Недостаточно прав! Команда доступна с ГС ОПГ/ГОСС!", reply_to)
                    return

                target_id = get_user_from_reply_or_mention(event.obj, args, 1)
                if not target_id:
                    send_message(peer_id, "❌ Укажите пользователя!", reply_to)
                    return

                if get_role(from_id, chat_id) <= get_role(target_id, chat_id) and from_id != target_id:
                    send_message(peer_id, "❌ Вы не можете удалить ник данному пользователю!", reply_to)
                    return

                pull_chats = get_pull_chats(chat_id)
                if not pull_chats:
                    send_message(peer_id, "❌ Чат не находится в объединении!", reply_to)
                    return

                for target_chat in pull_chats:
                    try:
                        sql.execute(f"DELETE FROM nicks_{target_chat} WHERE user_id = ?", (target_id,))
                        database.commit()
                    except:
                        pass

                message = f"🗑️ Глобальное удаление ника!\n"
                message += f"👤 Пользователь: {get_mention(target_id, chat_id)}"
                send_to_all_pull_chats(chat_id, message)
            
            elif cmd in ['grr', 'грр']:
                if chat_id == 0 or not check_chat(chat_id):
                    return
                    
                if get_role(from_id, chat_id) < 60:
                    send_message(peer_id, "❌ Недостаточно прав! Команда доступна с ГС ОПГ/ГОСС!", reply_to)
                    return

                target_id = get_user_from_reply_or_mention(event.obj, args, 1)
                if not target_id:
                    send_message(peer_id, "❌ Укажите пользователя!", reply_to)
                    return

                if target_id == from_id:
                    send_message(peer_id, "❌ Вы не можете снять роль самому себе!", reply_to)
                    return

                if get_role(from_id, chat_id) <= get_role(target_id, chat_id):
                    send_message(peer_id, "❌ Вы не можете снять роль пользователю с равной или выше ролью!", reply_to)
                    return

                pull_chats = get_pull_chats(chat_id)
                if not pull_chats:
                    send_message(peer_id, "❌ Чат не находится в объединении!", reply_to)
                    return

                for target_chat in pull_chats:
                    try:
                        set_role(target_id, target_chat, 0)
                    except:
                        pass

                message = f"❌ Глобальное снятие роли!\n"
                message += f"👤 Пользователь: {get_mention(target_id, chat_id)}"
# Здесь нужно было бы получить текущую роль перед снятием
                send_to_all_pull_chats(chat_id, message)
            
            # Команда ID
            elif cmd in ['id', 'ид']:
                handle_id(args, from_id, peer_id, reply_to, send_message)
            
            # Команда kick
            elif cmd in ['kick', 'кик']:
                if not has_command_access(from_id, 'kick'): 
                    send_message(peer_id, f"❌ Извините, у вас нет доступа к этой команде!\n\n🔧 Если это ошибка, обратитесь к Владелец {get_mention(BOT_OWNER_ID, chat_id)}!", reply_to)
                    return
                    
                if chat_id == 0:
                    send_message(peer_id, "Команда работает только в беседах!", reply_to)
                    return
                    
                if not check_chat(chat_id):
                    send_message(peer_id, "❌ Чат не зарегистрирован!", reply_to)
                    return
                

                    
                user_role = get_new_role_level(from_id, chat_id)
                if user_role < 40:
                    send_message(peer_id, "❌ Недостаточно прав!", reply_to)
                    return
                
                if len(args) < 2:
                    send_message(peer_id, "Укажите пользователя: /kick @пользователь", reply_to)
                    return
                
                mention = args[1]
                if mention.startswith('[id') and '|' in mention:
                    try:
                        target_id = int(mention.split('|')[0][3:])
                        target_role = get_role(target_id, chat_id)
                        
                        if user_role <= target_role:
                            send_message(peer_id, "❌ Нельзя исключить пользователя с равной или выше ролью!", reply_to)
                            return
                        
                        if kick_user(chat_id, target_id):
                            reason = ' '.join(args[2:]) if len(args) > 2 else "Не указана"
                            send_message(peer_id, f"✅ {get_user_info(from_id)} исключил {get_user_info(target_id)}\nПричина: {reason}", reply_to)
                        else:
                            send_message(peer_id, "❌ Не удалось исключить пользователя!", reply_to)
                    except Exception as e:
                        send_message(peer_id, "❌ Ошибка обработки упоминания!", reply_to)
                else:
                    send_message(peer_id, "Неверный формат! Используйте: /kick @пользователь", reply_to)
            
            # Команда addmoder (модератор бота)
            elif cmd in ['addmoder', 'moder']:
                if from_id != BOT_OWNER_ID:
                    send_message(peer_id, "❌ Недостаточно прав! Команда доступна только владельцу бота!", reply_to)
                    return
                if len(args) < 2:
                    send_message(peer_id, "Укажите пользователя: /addmoder @пользователь", reply_to)
                    return
                target_id = parse_user_mention(args[1])
                if not target_id:
                    send_message(peer_id, "Неверный формат пользователя!", reply_to)
                    return
                if target_id not in BOT_MODERATORS:
                    BOT_MODERATORS.append(target_id)
                sql.execute("INSERT OR REPLACE INTO bot_admins VALUES (?, 'moderator')", (target_id,))
                database.commit()
                send_message(peer_id, f"✅ {get_user_info(target_id)} получил права модератора бота!", reply_to)
            
            # Команда addcurator (куратор бота)
            elif cmd in ['addcurator', 'curator']:
                if from_id != BOT_OWNER_ID:
                    send_message(peer_id, "❌ Недостаточно прав! Команда доступна только владельцу бота!", reply_to)
                    return
                if len(args) < 2:
                    send_message(peer_id, "Укажите пользователя: /addcurator @пользователь", reply_to)
                    return
                target_id = parse_user_mention(args[1])
                if not target_id:
                    send_message(peer_id, "Неверный формат пользователя!", reply_to)
                    return
                if target_id not in BOT_MODERATORS:
                    BOT_MODERATORS.append(target_id)
                sql.execute("INSERT OR REPLACE INTO bot_admins VALUES (?, 'curator')", (target_id,))
                database.commit()
                send_message(peer_id, f"✅ {get_user_info(target_id)} получил права куратора бота!", reply_to)
            
            # Команда asustaff
            elif cmd in ['asustaff', 'асустафф']:
                staff_text = f"👑 Владелец бота: Владелец {get_mention(BOT_OWNER_ID, chat_id)}\n\n"
                
                # Получаем админов и модеров
                try:
                    sql.execute("SELECT user_id, role FROM bot_admins WHERE user_id != ?", (BOT_OWNER_ID,))
                    bot_staff = sql.fetchall()
                    admins = [uid for uid, role in bot_staff if role == 'admin']
                    moderators = [uid for uid, role in bot_staff if role == 'moderator']
                    
                    # Получаем всех пользователей одним запросом
                    all_ids = admins + moderators
                    if all_ids:
                        users_info = vk.users.get(user_ids=all_ids)
                        users_dict = {u['id']: f"{u['first_name']} {u['last_name']}" for u in users_info}
                    else:
                        users_dict = {}
                except:
                    admins = []
                    moderators = []
                    users_dict = {}
                
                if admins:
                    staff_text += "🔧 Администраторы бота:\n"
                    for admin_id in admins:
                        name = users_dict.get(admin_id, "Пользователь")
                        staff_text += f"• {get_mention(admin_id, chat_id)}\n"
                    staff_text += "\n"
                
                if moderators:
                    staff_text += "🛡️ Модераторы бота:\n"
                    for mod_id in moderators:
                        name = users_dict.get(mod_id, "Пользователь")
                        staff_text += f"• {get_mention(mod_id, chat_id)}\n"
                
                send_message(peer_id, staff_text, reply_to)
            
            # Команда staff
            elif cmd in ['staff', 'стафф']:
                if chat_id == 0 or not check_chat(chat_id):
                    return
                
                sql.execute(f"SELECT owner_id FROM chats WHERE chat_id = {chat_id}")
                owner = sql.fetchone()[0]
                
                # Получаем всех участников чата
                try:
                    members = vk.messages.getConversationMembers(peer_id=peer_id, fields='online')
                    all_members = [m['member_id'] for m in members['items'] if m['member_id'] > 0]
                except Exception as e:
                    print(f"[STAFF ERROR] Не удалось получить участников чата: {e}")
                    # Fallback: показываем только администрацию
                    sql.execute(f"SELECT user_id FROM permissions_{chat_id} WHERE level > 0")
                    admin_users = [r[0] for r in sql.fetchall()]
                    all_members = [owner] + admin_users
                
                # Получаем информацию порциями по 30 человек
                users_dict = {}
                for i in range(0, len(all_members), 30):
                    batch = all_members[i:i+30]
                    try:
                        users_info = vk.users.get(user_ids=batch)
                        for u in users_info:
                            users_dict[u['id']] = f"{u['first_name']} {u['last_name']}"
                    except:
                        pass
                
                        role_names = {0: "Хелпер/Лидер", 10: "Модератор", 20: "Старший модератор", 
                              25: "Администратор", 30: "Старший Администратор", 40: "Заместитель Главного Следящего", 
                              45: "Главный Следящий", 50: "Куратор Администрации", 60: "Заместитель Главного Администратора",
                              65: "Главный Администратор", 70: "Специальный Администратор", 75: "Заместитель Руководителя Проекта",
                              80: "Руководитель Проекта", 90: "Заместитель Основателя", 95: "Основатель Проекта", 99: "Владелец Проекта", 100: "Владелец Проекта"}
                role_emojis = {100: "👑", 99: "👑", 95: "🏛️", 90: "🔱", 80: "🎩", 75: "📋", 70: "⭐", 65: "🛡️", 60: "⚔️", 50: "👁️", 45: "🔍", 40: "👀", 30: "🔧", 25: "🛠️", 20: "🚔", 10: "👮", 0: "🤝"}
                
                valid_roles = [0, 10, 20, 25, 30, 40, 45, 50, 60, 65, 70, 75, 80, 90, 95, 99, 100]
                
                # Собираем всех пользователей с ролями
                from collections import defaultdict
                role_to_users = defaultdict(list)
                for user_id in all_members:
                    role = get_role(user_id, chat_id)
                    if role is not None and role >= 0 and role in valid_roles:
                        role_to_users[role].append(user_id)
                
                # Сортируем роли по уровню (высокий к низкому)
                sorted_roles = sorted(valid_roles, reverse=True)
                
                staff_text = ""
                has_users = False
                for role in sorted_roles:
                    emoji = role_emojis.get(role, '👤')
                    # ИСПОЛЬЗУЕМ КАСТОМНОЕ НАЗВАНИЕ ИЛИ СТАНДАРТНОЕ
                    role_name = get_role_name(role, chat_id)  # Изменено здесь
                    users = role_to_users.get(role, [])
                    if users:
                        has_users = True
                        staff_text += f"{emoji} {role_name}\n"
                        for user_id in users:
                            name = users_dict.get(user_id, "Пользователь")
                            staff_text += f"- {get_mention(user_id, chat_id)}\n"
                        staff_text += "\n"
                
                if not has_users:
                    staff_text = "👥 В чате нет пользователей с ролями."
                
                send_message(peer_id, staff_text, reply_to)
            
            # Команда warn
            elif cmd in ['warn', 'пред', 'варн']:
                if chat_id == 0 or not check_chat(chat_id):
                    return
                    
                if get_role(from_id, chat_id) < 40:
                    send_message(peer_id, "❌ Недостаточно прав!", reply_to)
                    return
                
                target_id = get_user_from_reply_or_mention(event.obj, args, 1)
                if not target_id:
                    send_message(peer_id, "Укажите пользователя или ответьте на сообщение!", reply_to)
                    return
                
                if get_role(from_id, chat_id) <= get_role(target_id, chat_id):
                    send_message(peer_id, "❌ Нельзя выдать предупреждение пользователю с равной или выше ролью!", reply_to)
                    return
                
                # Определяем причину
                if 'reply_message' in event.obj.message:
                    reason = ' '.join(args[1:]) if len(args) > 1 else "Не указана"
                else:
                    reason = ' '.join(args[2:]) if len(args) > 2 else "Не указана"
                
                warns = warn_user(target_id, chat_id, from_id, reason)
                
                moder_nick = get_nick(from_id, chat_id) or get_user_info(from_id)
                if warns >= 3:
                    if kick_user(chat_id, target_id):
                        message = f"⚠️ Предупреждение выдано!\n"
                        message += f"👤 Пользователь: {get_mention(target_id, chat_id)}\n"
                        message += f"👮 Администратор: {get_mention(from_id, chat_id)}\n"
                        message += f"💥 Пользователь исключен за 3 предупреждения!\n"
                        message += f"📝 Причина: {reason}"
                    else:
                        message = f"⚠️ Предупреждение выдано!\n"
                        message += f"👤 Пользователь: {get_mention(target_id, chat_id)}\n"
                        message += f"👮 Администратор: {get_mention(from_id, chat_id)}\n"
                        message += f"📝 Причина: {reason}\n"
                        message += f"⚠️ {get_mention(target_id, chat_id)} не удалось кикнуть. У пользователя имеется звезда в чате или тех причины."
                    send_message(peer_id, message, reply_to)
                else:
                    message = f"⚠️ Предупреждение выдано!\n"
                    message += f"👤 Пользователь: {get_mention(target_id, chat_id)}\n"
                    message += f"👮 Администратор: {get_mention(from_id, chat_id)}\n"
                    message += f"📊 Количество: {warns}/3\n"
                    message += f"📝 Причина: {reason}"
                    send_message(peer_id, message, reply_to)
            
            # Команда ban
            elif cmd in ['ban', 'бан']:
                if not has_command_access(from_id, 'ban'):
                    send_message(peer_id, f"❌ Извините, у вас нет доступа к этой команде!\n\n🔧 Ограничение доступа было выдано {get_mention(BOT_OWNER_ID, chat_id)}(Владельцем)!", reply_to)
                    return
                    
                if chat_id == 0 or not check_chat(chat_id):
                    return
                    
                if get_role(from_id, chat_id) < 40:
                    send_message(peer_id, "❌ Недостаточно прав!", reply_to)
                    return
                
                target_id = get_user_from_reply_or_mention(event.obj, args, 1)
                if not target_id:
                    send_message(peer_id, "❌ Укажите пользователя или ответьте на сообщение!", reply_to)
                    return
                
                if get_role(from_id, chat_id) <= get_role(target_id, chat_id):
                    send_message(peer_id, "❌ Нельзя заблокировать пользователя с равной или выше ролью!", reply_to)
                    return
                
                # Определяем время и причину
                if 'reply_message' in event.obj.message:
                    # Ответ на сообщение: /ban [дни] причина
                    if len(args) < 2:
                        send_message(peer_id, "❌ Укажите причину!\nИспользование: /ban причина или /ban дни причина", reply_to)
                        return
                    
                    # Проверяем первый аргумент - число или нет
                    try:
                        days = int(args[1])
                        if days < 3 or days > 9999:
                            send_message(peer_id, "❌ Время бана должно быть от 3 до 9999 дней!", reply_to)
                            return
                        reason = ' '.join(args[2:]) if len(args) > 2 else "Не указана"
                        duration = days * 1440  # дни в минуты
                    except:
                        # Не число - значит сразу причина
                        days = 0
                        duration = 0
                        reason = ' '.join(args[1:])
                else:
                    # Упоминание: /ban @user [дни] причина
                    if len(args) < 3:
                        send_message(peer_id, "❌ Укажите причину!\nИспользование: /ban @user причина или /ban @user дни причина", reply_to)
                        return
                    
                    # Проверяем второй аргумент - число или нет
                    try:
                        days = int(args[2])
                        if days < 3 or days > 9999:
                            send_message(peer_id, "❌ Время бана должно быть от 3 до 9999 дней!", reply_to)
                            return
                        reason = ' '.join(args[3:]) if len(args) > 3 else "Не указана"
                        duration = days * 1440  # дни в минуты
                    except:
                        # Не число - значит сразу причина
                        days = 0
                        duration = 0
                        reason = ' '.join(args[2:])
                
                if reason == "Не указана" or not reason:
                    send_message(peer_id, "❌ Укажите причину бана!", reply_to)
                    return
                
                ban_user(target_id, chat_id, from_id, reason, duration)
                kicked = kick_user(chat_id, target_id)
                
                moder_nick = get_nick(from_id, chat_id) or get_user_info(from_id)
                message = f"🔴 Бан выдан!\n"
                message += f"👤 Пользователь: {get_mention(target_id, chat_id)}\n"
                message += f"👮 Администратор: {get_mention(from_id, chat_id)}\n"
                if days > 0:
                    message += f"⏰ Срок: {days} дней\n"
                else:
                    message += f"⏰ Срок: Навсегда\n"
                message += f"📝 Причина: {reason}"
                if not kicked:
                    message += f"\n⚠️ {get_mention(target_id, chat_id)} не удалось кикнуть. У пользователя имеется звезда в чате или тех причины."
                send_message(peer_id, message, reply_to)
            
            # Команда setnick
            elif cmd in ['setnick', 'nick', 'ник']:
                if chat_id == 0 or not check_chat(chat_id):
                    return
                    
                if get_role(from_id, chat_id) < 40:
                    send_message(peer_id, "❌ Недостаточно прав!", reply_to)
                    return
                
                target_id = get_user_from_reply_or_mention(event.obj, args, 1)
                if not target_id:
                    send_message(peer_id, "Укажите пользователя или ответьте на сообщение!", reply_to)
                    return
                
                if get_role(from_id, chat_id) <= get_role(target_id, chat_id) and from_id != target_id:
                    send_message(peer_id, "❌ Нельзя изменить ник пользователю с равной или выше ролью!", reply_to)
                    return
                
                # Определяем ник
                if 'reply_message' in event.obj.message:
                    new_nick = ' '.join(args[1:]) if len(args) > 1 else "Не указан"
                else:
                    new_nick = ' '.join(args[2:]) if len(args) > 2 else "Не указан"
                
                if new_nick == "Не указан":
                    send_message(peer_id, "Укажите ник!", reply_to)
                    return
                
                # Получаем старый ник
                old_nick = get_nick(target_id, chat_id)
                
                # Устанавливаем новый ник
                set_nick(target_id, chat_id, new_nick)
                
                # Красивое сообщение
                message = f"🏷️ {get_mention(from_id, chat_id)} выдал никнейм {get_mention(target_id, chat_id)}\n"
                message += f"✨ Новый ник: {new_nick}"
                
                if old_nick:
                    message += f"\n🔄 Бывший ник: {old_nick}"
                
                send_message(peer_id, message, reply_to)
            
            # Команда rnick (удаление ника)
            elif cmd in ['rnick', 'удалитьник']:
                if chat_id == 0 or not check_chat(chat_id):
                    return
                    
                if get_role(from_id, chat_id) < 60:
                    send_message(peer_id, "❌ Недостаточно прав! Команда доступна с ГС ОПГ/ГОСС!", reply_to)
                    return
                
                target_id = get_user_from_reply_or_mention(event.obj, args, 1)
                if not target_id:
                    target_id = from_id
                
                # Проверяем права
                if target_id != from_id:
                    if get_role(from_id, chat_id) <= get_role(target_id, chat_id):
                        send_message(peer_id, "❌ Вы не можете удалить ник пользователю с равной или выше ролью!", reply_to)
                        return
                
                old_nick = get_nick(target_id, chat_id)
                if not old_nick:
                    send_message(peer_id, f"ℹ️ У {get_mention(target_id, chat_id)} нет ника", reply_to)
                    return
                
                try:
                    sql.execute(f"DELETE FROM nicks_{chat_id} WHERE user_id = ?", (target_id,))
                    database.commit()
                    
                    message = f"🗑️ Ник успешно удалён!\n"
                    message += f"👤 Пользователь: {get_mention(target_id, chat_id)}\n"
                    message += f"📝 Удалённый ник: {old_nick}"
                    send_message(peer_id, message, reply_to)
                except Exception as e:
                    send_message(peer_id, "❌ Ошибка удаления ника!", reply_to)
            
            # Команда getnick
            elif cmd in ['getnick', 'нику']:
                if chat_id == 0 or not check_chat(chat_id):
                    return
                    
                if get_new_role_level(from_id, chat_id) < 40:
                    send_message(peer_id, "❌ Недостаточно прав!", reply_to)
                    return
                
                target_id = get_user_from_reply_or_mention(event.obj, args, 1) or from_id
                
                nick = get_nick(target_id, chat_id)
                if nick:
                    send_message(peer_id, f"Ник {get_user_info(target_id)}: {nick}", reply_to)
                else:
                    send_message(peer_id, f"У {get_user_info(target_id)} нет ника", reply_to)
            
            # Команда nlist
            elif cmd in ['nlist', 'ники']:
                if chat_id == 0 or not check_chat(chat_id):
                    return
                
                user_role = get_role(from_id, chat_id)
                if user_role < 40 and from_id != BOT_OWNER_ID:
                    send_message(peer_id, "❌ Недостаточно прав! Команда доступна с ЗГС!", reply_to)
                    return
                
                try:
                    sql.execute(f"SELECT user_id, nick FROM nicks_{chat_id}")
                    nicks = sql.fetchall()
                    
                    if not nicks:
                        send_message(peer_id, "📋 Список пользователей с никами пуст", reply_to)
                        return
                    
                    # Оптимизированное формирование списка
                    nick_list = []
                    for i, (uid, nick) in enumerate(nicks, 1):
                        nick_list.append(f"{i}. {get_mention(uid, chat_id)} → {nick}")
                    
                    if not nick_list:
                        send_message(peer_id, "📋 Список пользователей с никами пуст", reply_to)
                    else:
                        nick_text = f"📋 Пользователи с никами ({len(nick_list)}): \n\n" + "\n".join(nick_list)
                        send_message(peer_id, nick_text, reply_to)
                except Exception as e:
                    send_message(peer_id, "❌ Ошибка получения списка!", reply_to)
            
            # Команда nonlist
            elif cmd in ['nonlist', 'безников', 'нетника']:
                if chat_id == 0 or not check_chat(chat_id):
                    return
                    
                if get_role(from_id, chat_id) < 40:
                    send_message(peer_id, "❌ Недостаточно прав!", reply_to)
                    return
                    
                try:
                    # Получаем всех участников беседы
                    members = vk.messages.getConversationMembers(peer_id=peer_id)
                    all_users = [m['member_id'] for m in members['items'] if m['member_id'] > 0]
                    
                    # Получаем пользователей с никами
                    sql.execute(f"CREATE TABLE IF NOT EXISTS nicks_{chat_id} (user_id INTEGER, nick TEXT)")
                    sql.execute(f"SELECT user_id FROM nicks_{chat_id}")
                    users_with_nicks = [row[0] for row in sql.fetchall()]
                    
                    # Фильтруем: без ников и не админы бота
                    users_without_nicks = [uid for uid in all_users if uid not in users_with_nicks and not is_bot_admin(uid)]
                    
                    if not users_without_nicks:
                        send_message(peer_id, "📋 Все пользователи имеют ники", reply_to)
                    else:
                        text = "📋 Пользователи без ников:\n\n"
                        for i, uid in enumerate(users_without_nicks, 1):
                            text += f"{i}. {get_mention(uid, chat_id)}\n"
                        send_message(peer_id, text, reply_to)
                except Exception as e:
                    print(f"Error in nonlist: {e}")
                    send_message(peer_id, "❌ Ошибка получения списка!", reply_to)
            
            # Команда addadmin (администратор бота)
            elif cmd in ['addadmin', 'admin']:
                if from_id != BOT_OWNER_ID:
                    send_message(peer_id, "❌ Недостаточно прав! Команда доступна только владельцу бота!", reply_to)
                    return
                if len(args) < 2:
                    send_message(peer_id, "Укажите пользователя: /addadmin @пользователь", reply_to)
                    return
                target_id = parse_user_mention(args[1])
                if not target_id:
                    send_message(peer_id, "Неверный формат пользователя!", reply_to)
                    return
                if target_id not in BOT_MODERATORS:
                    BOT_MODERATORS.append(target_id)
                sql.execute("INSERT OR REPLACE INTO bot_admins VALUES (?, 'admin')", (target_id,))
                database.commit()
                send_message(peer_id, f"✅ {get_user_info(target_id)} получил права администратора бота!", reply_to)
            
            # Команда addma
            elif cmd in ['addma']:
                if from_id != BOT_OWNER_ID:
                    send_message(peer_id, "❌ Недостаточно прав! Команда доступна только владельцу бота!", reply_to)
                    return
                
                if len(args) < 2:
                    send_message(peer_id, "Использование: /addma @пользователь", reply_to)
                    return
                
                target_id = parse_user_mention(args[1])
                if not target_id:
                    send_message(peer_id, "Неверный формат пользователя!", reply_to)
                    return
                
                removed_roles = []
                
                # Снимаем роль модератора/админа бота
                try:
                    sql.execute("SELECT role FROM bot_admins WHERE user_id = ?", (target_id,))
                    bot_role = sql.fetchone()
                    if bot_role:
                        sql.execute("DELETE FROM bot_admins WHERE user_id = ?", (target_id,))
                        database.commit()
                        if target_id in BOT_MODERATORS:
                            BOT_MODERATORS.remove(target_id)
                        role_name = "Администратор бота" if bot_role[0] == 'admin' else "Модератор бота"
                        removed_roles.append(role_name)
                except:
                    pass
                
                # Снимаем роли во всех чатах
                if chat_id > 0:
                    try:
                        sql.execute("SELECT chat_id FROM chats")
                        all_chats = sql.fetchall()
                        for (c_id,) in all_chats:
                            try:
                                sql.execute(f"SELECT level FROM permissions_{c_id} WHERE user_id = {target_id}")
                                chat_role = sql.fetchone()
                                if chat_role:
                                    sql.execute(f"DELETE FROM permissions_{c_id} WHERE user_id = {target_id}")
                                    role_names = {
                                        0: 'Пользователь',
                                        10: 'Модератор', 
                                        20: 'Старший Модератор',
                                        30: 'Администратор',
                                        40: 'Старший Администратор',
                                        50: 'ЗГС ГОСС/ОПГ',
                                        60: 'ГС ОПГ/ГОСС',
                                        70: 'Куратор Администрации',
                                        80: 'ЗГА',
                                        90: 'Главный Администратор',
                                        95: 'Спец Админ',
                                        100: 'Владелец Беседы',
                                        150: 'Модератор бота',
                                        350: 'Администратор Бота',
                                        500: 'Куратор бота',
                                        1000: 'Владелец бота'
                                    }
                                    removed_roles.append(f"{role_names.get(chat_role[0], 'Роль')} в чате {c_id}")
                            except:
                                pass
                        database.commit()
                    except:
                        pass
                
                if removed_roles:
                    message = f"✅ У {get_user_info(target_id)} сняты следующие роли:\n"
                    for role in removed_roles:
                        message += f"• {role}\n"
                    send_message(peer_id, message, reply_to)
                else:
                    send_message(peer_id, f"ℹ️ У {get_user_info(target_id)} нет активных ролей", reply_to)
            
            # Команда rr (удаление роли)
            elif cmd in ['rr', 'снятьроль']:
                if chat_id == 0 or not check_chat(chat_id):
                    return
                    
                if get_role(from_id, chat_id) < 90:
                    send_message(peer_id, "❌ Недостаточно прав! Команда доступна с Заместителя Основателя!", reply_to)
                    return
                
                target_id = get_user_from_reply_or_mention(event.obj, args, 1)
                if not target_id:
                    send_message(peer_id, "❌ Укажите пользователя или ответьте на сообщение!", reply_to)
                    return
                
                # Нельзя снять самому себе
                if target_id == from_id:
                    send_message(peer_id, "❌ Вы не можете снять роль самому себе!", reply_to)
                    return
                
                # Проверяем админов/модеров бота - владелец может снимать роли
                if is_bot_admin(target_id) and from_id == BOT_OWNER_ID:
                    # Снимаем роль модератора/админа бота
                    try:
                        sql.execute("DELETE FROM bot_admins WHERE user_id = ?", (target_id,))
                        database.commit()
                        if target_id in BOT_MODERATORS:
                            BOT_MODERATORS.remove(target_id)
                        send_message(peer_id, f"✅ У {get_user_info(target_id)} снята роль администратора/модератора бота!", reply_to)
                        return
                    except:
                        send_message(peer_id, "❌ Ошибка снятия роли!", reply_to)
                        return
                elif is_bot_admin(target_id) and from_id != BOT_OWNER_ID:
                    send_message(peer_id, "❌ Снимать роли админам и модерам бота может только Владелец бота!", reply_to)
                    return
                
                # Проверяем роли в чате
                if get_role(from_id, chat_id) <= get_role(target_id, chat_id):
                    send_message(peer_id, "❌ Вы не можете снять роль пользователю с равной или выше ролью!", reply_to)
                    return
                
                old_role = get_role(target_id, chat_id)
                
                set_role(target_id, chat_id, 0)

                message = f"✅ Роль успешно снята!\n"
                message += f"👤 Пользователь: {get_mention(target_id, chat_id)}\n"
                message += f"📝 Снята роль: {get_role_name(old_role, chat_id)}"  # Добавили chat_id
                send_message(peer_id, message, reply_to)
            
            # Команда removerole
            elif cmd in ['removerole', 'rrole']:
                if chat_id == 0 or not check_chat(chat_id):
                    return
                    
                if get_role(from_id, chat_id) < 90:
                    send_message(peer_id, "❌ Недостаточно прав! Команда доступна с Заместителя Основателя!", reply_to)
                    return
                
                if len(args) < 2:
                    send_message(peer_id, "Укажите пользователя: /removerole @пользователь", reply_to)
                    return
                
                target_id = parse_user_mention(args[1])
                if not target_id:
                    send_message(peer_id, "Неверный формат пользователя!", reply_to)
                    return
                
                # Проверяем, не является ли цель владельцем беседы
                sql.execute(f"SELECT owner_id FROM chats WHERE chat_id = {chat_id}")
                chat_owner = sql.fetchone()[0]
                if target_id == chat_owner and from_id != BOT_OWNER_ID:
                    send_message(peer_id, "❌ Нельзя снять роль у владельца беседы!", reply_to)
                    return
                
                if get_role(from_id, chat_id) <= get_role(target_id, chat_id):
                    send_message(peer_id, "❌ Нельзя снять роль у пользователя с равной или выше ролью!", reply_to)
                    return
                
                set_role(target_id, chat_id, 0)
                send_message(peer_id, f"✅ У {get_user_info(target_id)} снята роль!", reply_to)
            
            # Команда тишина
            elif cmd in ['тишина', 'quiet']:
                if chat_id == 0 or not check_chat(chat_id):
                    return
                    
                if get_role(from_id, chat_id) < 90:
                    send_message(peer_id, "❌ Недостаточно прав!", reply_to)
                    return
                
                sql.execute(f"SELECT silence FROM chats WHERE chat_id = {chat_id}")
                current = sql.fetchone()[0]
                new_state = 0 if current else 1
                
                sql.execute(f"UPDATE chats SET silence = ? WHERE chat_id = ?", (new_state, chat_id))
                database.commit()
                
                status = "включен" if new_state else "выключен"
                send_message(peer_id, f"🔇 Режим тишины {status}!", reply_to)
            
            # Команда ping
            elif cmd in ['ping', 'пинг']:
                start_time = time.time()
                delay = round((time.time() - start_time) * 1000, 2)
                
                # Определяем качество соединения
                if delay < 100:
                    connection = "🟢 Отличное"
                elif delay < 300:
                    connection = "🟡 Хорошее"
                else:
                    connection = "🟠 Среднее"
                
                # Простой расчет аптайма (можно заменить на реальный)
                uptime_seconds = int(time.time()) % 3600  # Примерный аптайм
                uptime_minutes = uptime_seconds // 60
                uptime_secs = uptime_seconds % 60
                
                ping_text = f"⚡ Статус системы\n\n"
                ping_text += f"📶 Соединение: {connection}\n"
                ping_text += f"⏱ Задержка: {delay}мс\n"
                ping_text += f"⚙️ Обработка: 0мс\n"
                ping_text += f"🕒 Аптайм: {uptime_minutes}м {uptime_secs}с"
                
                send_message(peer_id, ping_text, reply_to)
            
            # Команда banlist
            elif cmd in ['banlist', 'банлист']:
                if chat_id == 0 or not check_chat(chat_id):
                    return
                    
                if get_role(from_id, chat_id) < 60:
                    send_message(peer_id, "❌ Недостаточно прав! Команда доступна с ГС ОПГ/ГОСС!", reply_to)
                    return
                
                sql.execute(f"SELECT user_id, reason, ban_until FROM bans_{chat_id}")
                bans = sql.fetchall()
                
                if not bans:
                    send_message(peer_id, "🔴 Пользователи в бане: отсутствуют", reply_to)
                else:
                    ban_text = "🔴 Пользователи в бане:\n"
                    for i, (user_id, reason, ban_until) in enumerate(bans, 1):
                        user_mention = get_mention(user_id, chat_id)
                        if ban_until > 0:
                            until_str = datetime.fromtimestamp(ban_until).strftime('%d.%m.%Y')
                            ban_text += f"   {i}. {user_mention} - {reason} - до {until_str}\n"
                        else:
                            ban_text += f"   {i}. {user_mention} - {reason} - навсегда\n"
                    send_message(peer_id, ban_text, reply_to)
            
            # Команда warnlist
            elif cmd in ['warnlist', 'варнлист']:
                if chat_id == 0 or not check_chat(chat_id):
                    return
                    
                if get_role(from_id, chat_id) < 60:
                    send_message(peer_id, "❌ Недостаточно прав! Команда доступна с ГС ОПГ/ГОСС!", reply_to)
                    return
                
                sql.execute(f"SELECT user_id, count, reason FROM warns_{chat_id}")
                warns = sql.fetchall()
                
                if not warns:
                    send_message(peer_id, "⚠️ Пользователи с предупреждениями: отсутствуют", reply_to)
                else:
                    warn_text = "Пользователи с предупреждениями :\n"
                    for i, (user_id, count, reason) in enumerate(warns, 1):
                        user_mention = get_mention(user_id, chat_id)
                        warn_text += f"{i}. {user_mention} - Причина варна : \"{reason}\"\n"
                    send_message(peer_id, warn_text, reply_to)
            
            # Команда online
            elif cmd in ['online', 'онлайн']:
                try:
                    members = vk.messages.getConversationMembers(peer_id=peer_id, fields='online')
                    online_list = []
                    
                    # Создаем словарь профилей для быстрого доступа
                    profiles = {p['id']: p for p in members['profiles']}
                    
                    for profile in members['profiles']:
                        if profile.get('online') == 1:
                            user_id = profile['id']
                            first_name = profile['first_name']
                            last_name = profile['last_name']
                            full_name = f"{first_name} {last_name}"
                            
                            # Проверяем локальный ник (это быстрый SQL запрос)
                            nick = get_nick(user_id, chat_id)
                            
                            if nick:
                                online_list.append(f"💻 {get_mention(user_id, chat_id)}")
                            else:
                                online_list.append(f"💻 {get_mention(user_id, chat_id)}")
                    
                    if not online_list:
                         send_message(peer_id, "😴 В данный момент никого нет в сети", reply_to)
                    else:
                        online_text = '\n'.join(online_list)
                        message = f"🟢 Пользователи онлайн: {len(online_list)}\n\n{online_text}"
                        send_message(peer_id, message, reply_to)
                except Exception as e:
                    send_message(peer_id, f"❌ Ошибка получения списка: {e}", reply_to)
            
            # Команда roles
            elif cmd in ['roles', 'роль', 'role']:
                if chat_id == 0 or not check_chat(chat_id):
                    return
                    
                # Если аргументов нет - выводим список всех доступных ролей (иерархию)
                if len(args) == 1 and 'reply_message' not in event.obj.message:
                    try:
                        # Стандартные роли и их названия
                        valid_roles = [0, 10, 20, 25, 30, 40, 45, 50, 60, 65, 70, 75, 80, 90, 95, 99, 100]
                        default_names = {
                            0: "Хелпер/Лидер", 10: "Модератор", 20: "Старший модератор", 
                            25: "Администратор", 30: "Старший Администратор", 40: "Заместитель Главного Следящего", 
                            45: "Главный Следящий", 50: "Куратор Администрации", 60: "Заместитель Главного Администратора",
                            65: "Главный Администратор", 70: "Специальный Администратор", 75: "Заместитель Руководителя Проекта",
                            80: "Руководитель Проекта", 90: "Заместитель Основателя", 95: "Основатель Проекта", 
                            99: "Владелец Проекта", 100: "Владелец Проекта"
                        }
                        
                        # Получаем кастомные названия для этого чата
                        try:
                            sql.execute("SELECT role_level, custom_name FROM custom_role_names WHERE chat_id = ?", (chat_id,))
                            custom_names = {row[0]: row[1] for row in sql.fetchall()}
                        except:
                            custom_names = {}

                        # Получаем список отключенных ролей
                        try:
                            sql.execute("SELECT role_level FROM disabled_roles WHERE chat_id = ?", (chat_id,))
                            disabled_levels = [row[0] for row in sql.fetchall()]
                        except:
                            disabled_levels = []

                        message = "📋 Список всех ролей в чате:\n\n"
                        
                        # Сортируем от большего к меньшему
                        displayed_roles = [r for r in valid_roles if r not in disabled_levels]
                        
                        for level in sorted(displayed_roles, reverse=True):
                            name = custom_names.get(level, default_names.get(level, f"Неизвестная роль {level}"))
                            message += f"🎭 {level} — {name}\n"
                            
                        message += "\n💡 Чтобы выдать роль: /role @user [уровень]\n"
                        message += "ℹ️ Чтобы изменить название: /newrole [уровень] [название]\n"
                        message += "🗑 Чтобы удалить/скрыть роль: /delrole [уровень]"
                        
                        send_message(peer_id, message, reply_to)
                        return
                    except Exception as e:
                        print(f"Error in roles list: {e}")
                        send_message(peer_id, f"❌ Ошибка формирования списка: {e}", reply_to)
                        return

                # Определяем роль вызывающего
                user_role = get_role(from_id, chat_id)

                if user_role < 40:  # Только ЗГС и выше для выдачи
                    send_message(peer_id, "❌ Недостаточно прав! Команда доступна с ЗГС!", reply_to)
                    return
                
                # Получаем пользователя из ответа или упоминания
                target_id = get_user_from_reply_or_mention(event.obj, args, 1)
                if not target_id:
                    send_message(peer_id, "❌ Укажите пользователя или ответьте на сообщение!\n📝 Пример: /role @user 1 или ответ на сообщение + /role 1", reply_to)
                    return
                
                # Проверяем, не пытается ли выдать роль самому себе
                if target_id == from_id:
                    send_message(peer_id, "❌ Вы не можете выдать роль самому себе! 😅", reply_to)
                    return
                
                # Определяем уровень роли
                if 'reply_message' in event.obj.message:
                    if len(args) < 2:
                        send_message(peer_id, "❌ Укажите уровень роли!\n📝 Пример: /role 1", reply_to)
                        return
                    try:
                        role_level = int(args[1])
                    except:
                        send_message(peer_id, "❌ Укажите корректный уровень роли!", reply_to)
                        return
                else:
                    if len(args) < 3:
                        send_message(peer_id, "❌ Укажите уровень роли!\n📝 Пример: /role @user 1", reply_to)
                        return
                    try:
                        role_level = int(args[2])
                    except:
                        send_message(peer_id, "❌ Укажите корректный уровень роли!", reply_to)
                        return

                # Валидные уровни ролей
                valid_roles_list = [0, 10, 20, 25, 30, 40, 45, 50, 60, 65, 70, 75, 80, 90, 95, 99, 100]
                
                # Получаем список отключенных ролей
                try:
                    sql.execute("SELECT role_level FROM disabled_roles WHERE chat_id = ?", (chat_id,))
                    disabled_levels = [row[0] for row in sql.fetchall()]
                except:
                    disabled_levels = []

                if role_level not in valid_roles_list or role_level in disabled_levels:
                    # Формируем список доступных ролей
                    message = "❌ Уровень роли должен быть одним из допустимых!\n\n🎭 Уровни ролей:\n"
                    
                    displayed_roles = [r for r in valid_roles_list if r not in disabled_levels]
                    for r in sorted(displayed_roles, reverse=True):
                        # Используем get_role_name для получения кастомного или дефолтного названия
                        message += f"{r} - {get_role_name(r, chat_id)}\n"
                        
                    send_message(peer_id, message, reply_to)
                    return
                
                # Конвертируем уровни в новые значения
                actual_role = role_level
                target_current_role = get_role(target_id, chat_id)
                
                # Проверяем, не пытается ли выдать роль выше или равную своей
                if actual_role >= user_role and from_id != BOT_OWNER_ID:
                    send_message(peer_id, "❌ Невозможно выдать роль такую же как у вас или выше вашей! 🙅‍♂️", reply_to)
                    return
                
                # Проверяем, не является ли цель владельцем беседы
                sql.execute(f"SELECT owner_id FROM chats WHERE chat_id = {chat_id}")
                chat_owner = sql.fetchone()[0]
                if target_id == chat_owner and from_id != BOT_OWNER_ID:
                    send_message(peer_id, "❌ Нельзя изменить роль владельца беседы! 👑", reply_to)
                    return
                
                # Проверяем, не модератор/админ ли бота цель
                if is_bot_admin(target_id) and from_id != chat_owner:
                    send_message(peer_id, "❌ Изменять роль модераторов и администраторов бота может только владелец беседы! 🤖", reply_to)
                    return
                
                set_role(target_id, chat_id, actual_role)
                
                message = f"✅ Роль успешно выдана! 🎉\n"
                message += f"👤 Пользователь: {get_mention(target_id, chat_id)}\n"
                message += f"🎭 Новая роль: {get_role_name(role_level, chat_id)}"  # Добавили chat_id
                send_message(peer_id, message, reply_to)
            
            # Команда unban
            elif cmd in ['unban', 'разбан']:
                if chat_id == 0 or not check_chat(chat_id):
                    return
                    
                if get_role(from_id, chat_id) < 70:
                    send_message(peer_id, "❌ Недостаточно прав! Команда доступна с Спец. Администратора!", reply_to)
                    return
                
                target_id = get_user_from_reply_or_mention(event.obj, args, 1)
                if not target_id:
                    send_message(peer_id, "Укажите пользователя или ответьте на сообщение!", reply_to)
                    return
                
                if not is_banned(target_id, chat_id):
                    send_message(peer_id, f"ℹ️ {get_user_info(target_id)} не заблокирован в этой беседе", reply_to)
                    return
                
                unban_user(target_id, chat_id)
                send_message(peer_id, f"✅ {get_user_info(target_id)} разблокирован в беседе!", reply_to)
            
            # Команда unwarn
            elif cmd in ['unwarn', 'снятьпред']:
                if chat_id == 0 or not check_chat(chat_id):
                    return
                    
                if get_role(from_id, chat_id) < 40:
                    send_message(peer_id, "❌ Недостаточно прав!", reply_to)
                    return
                
                target_id = get_user_from_reply_or_mention(event.obj, args, 1)
                if not target_id:
                    send_message(peer_id, "Укажите пользователя или ответьте на сообщение!", reply_to)
                    return
                
                if get_role(from_id, chat_id) <= get_role(target_id, chat_id):
                    send_message(peer_id, "❌ Нельзя снять предупреждение пользователю с равной или выше ролью!", reply_to)
                    return
                
                warns_left = unwarn_user(target_id, chat_id)
                send_message(peer_id, f"✅ У {get_user_info(target_id)} снято предупреждение! Осталось: {warns_left}/3", reply_to)
            
            # Команда mute
            elif cmd in ['mute', 'мут']:
                if chat_id == 0 or not check_chat(chat_id):
                    return
                    
                if get_role(from_id, chat_id) < 40:
                    send_message(peer_id, "❌ Недостаточно прав!", reply_to)
                    return
                
                target_id = get_user_from_reply_or_mention(event.obj, args, 1)
                if not target_id:
                    send_message(peer_id, "Укажите пользователя или ответьте на сообщение!", reply_to)
                    return
                
                if get_role(from_id, chat_id) <= get_role(target_id, chat_id):
                    send_message(peer_id, "❌ Нельзя замутить пользователя с равной или выше ролью!", reply_to)
                    return
                
                # Определяем время и причину
                if 'reply_message' in event.obj.message:
                    if len(args) < 2:
                        send_message(peer_id, "Укажите время в минутах!", reply_to)
                        return
                    try:
                        minutes = int(args[1])
                        reason = ' '.join(args[2:]) if len(args) > 2 else "Причина не указана"
                    except:
                        send_message(peer_id, "Неверное время!", reply_to)
                        return
                else:
                    if len(args) < 3:
                        send_message(peer_id, "Использование: /mute @пользователь минуты [причина]", reply_to)
                        return
                    try:
                        minutes = int(args[2])
                        reason = ' '.join(args[3:]) if len(args) > 3 else "Причина не указана"
                    except:
                        send_message(peer_id, "Неверное время!", reply_to)
                        return
                
                if minutes < 1 or minutes > 10080:  # Макс неделя
                    send_message(peer_id, "Время должно быть от 1 до 10080 минут (неделя)!", reply_to)
                    return
                
                if is_muted(target_id, chat_id):
                    send_message(peer_id, f"ℹ️ {get_user_info(target_id)} уже замучен!", reply_to)
                    return
                
                mute_user(target_id, chat_id, from_id, reason, minutes)
                
                moder_nick = get_nick(from_id, chat_id) or get_user_info(from_id)
                message = f"🔇 Мут выдан!\n"
                message += f"👤 Пользователь: {get_mention(target_id, chat_id)}\n"
                message += f"👮 Администратор: {get_mention(from_id, chat_id)}\n"
                message += f"⏰ Время: {minutes} минут\n"
                message += f"📝 Причина: {reason}"
                send_message(peer_id, message, reply_to)
            
            # Команда unmute
            elif cmd in ['unmute', 'размут']:
                if chat_id == 0 or not check_chat(chat_id):
                    return
                    
                if get_role(from_id, chat_id) < 40:
                    send_message(peer_id, "❌ Недостаточно прав!", reply_to)
                    return
                
                target_id = get_user_from_reply_or_mention(event.obj, args, 1)
                if not target_id:
                    send_message(peer_id, "Укажите пользователя или ответьте на сообщение!", reply_to)
                    return
                
                if get_role(from_id, chat_id) <= get_role(target_id, chat_id):
                    send_message(peer_id, "❌ Нельзя размутить пользователя с равной или выше ролью!", reply_to)
                    return
                
                if not is_muted(target_id, chat_id):
                    send_message(peer_id, f"ℹ️ {get_user_info(target_id)} не замучен!", reply_to)
                    return
                
                unmute_user(target_id, chat_id)
                send_message(peer_id, f"✅ {get_user_info(target_id)} размучен!", reply_to)
            
            # Команда bonus
            elif cmd in ['bonus', 'бонус']:
                handle_bonus(chat_id, from_id, peer_id, reply_to, get_bonus, send_message)
            
            # Команда shop
            elif cmd in ['shop', 'магазин']:
                if chat_id == 0 or not check_chat(chat_id):
                    return
                
                if len(args) == 1:
                    # Показываем ассортимент
                    shop_text = "🏪 Магазин VIP статусов\n\n"
                    
                    for i, (vip_key, vip_data) in enumerate(shop_prices['vip_statuses'].items(), 1):
                        shop_text += f"{i}. {vip_data['name']} - 💰 {vip_data['price']:,} монет\n"
                    
                    shop_text += "\n💡 Для покупки: /shop [номер товара]\n"
                    shop_text += "📝 Пример: /shop 1"
                    
                    send_message(peer_id, shop_text, reply_to)
                    
                elif len(args) == 2:
                    # Показываем товар для покупки
                    try:
                        item_id = int(args[1])
                        vip_items = list(shop_prices['vip_statuses'].items())
                        
                        if 1 <= item_id <= len(vip_items):
                            vip_key, vip_data = vip_items[item_id - 1]
                            
                            message = f"🛒 Подтверждение покупки\n\n"
                            message += f"{get_mention(from_id, chat_id)} хотите купить:\n"
                            message += f"📦 {vip_data['name']}\n"
                            message += f"💰 Цена: {vip_data['price']:,} монет\n\n"
                            message += f"✅ Для подтверждения: /shop {item_id} yes\n"
                            message += f"❌ Для отмены: /shop no"
                            
                            send_message(peer_id, message, reply_to)
                        else:
                            send_message(peer_id, "❌ Неверный номер товара!", reply_to)
                    except:
                        send_message(peer_id, "❌ Укажите корректный номер товара!", reply_to)
                        
                elif len(args) == 3 and args[2].lower() == 'yes':
                    # Подтверждение покупки
                    try:
                        item_id = int(args[1])
                        vip_items = list(shop_prices['vip_statuses'].items())
                        
                        if 1 <= item_id <= len(vip_items):
                            vip_key, vip_data = vip_items[item_id - 1]
                            
                            # Проверяем баланс
                            sql.execute(f"SELECT coins FROM bonuses_{chat_id} WHERE user_id = {from_id}")
                            balance = sql.fetchone()
                            current_coins = balance[0] if balance else 0
                            
                            if current_coins >= vip_data['price']:
                                # Списываем монеты
                                sql.execute(f"UPDATE bonuses_{chat_id} SET coins = coins - ? WHERE user_id = ?", (vip_data['price'], from_id))
                                
                                # Выдаем VIP статус на 30 дней
                                end_time = int(time.time()) + (30 * 24 * 60 * 60)
                                sql.execute("INSERT OR REPLACE INTO vip_statuses VALUES (?, ?, ?, ?)", (from_id, chat_id, vip_key, end_time))
                                database.commit()
                                
                                # Сообщение покупателю
                                message = f"✅ Покупка успешно завершена! 🎉\n\n"
                                message += f"📦 Товар: {vip_data['name']}\n"
                                message += f"💰 Списано: {vip_data['price']:,} монет\n"
                                message += f"💳 Остаток: {current_coins - vip_data['price']:,} монет\n"
                                message += f"⏰ Срок действия: 30 дней"
                                send_message(peer_id, message, reply_to)
                                
                                # Уведомление владельцу бота
                                owner_msg = f"💰 Новая покупка в магазине!\n\n"
                                owner_msg += f"👤 {get_mention(from_id, chat_id)} купил:\n"
                                owner_msg += f"📦 {vip_data['name']}\n"
                                owner_msg += f"💸 За {vip_data['price']:,} монет"
                                send_message(BOT_OWNER_ID, owner_msg)
                            else:
                                send_message(peer_id, f"❌ Недостаточно монет!\n💰 Нужно: {vip_data['price']:,}\n💳 У вас: {current_coins:,}", reply_to)
                        else:
                            send_message(peer_id, "❌ Неверный номер товара!", reply_to)
                    except:
                        send_message(peer_id, "❌ Ошибка при покупке!", reply_to)
                        
                elif len(args) == 2 and args[1].lower() == 'no':
                    # Отмена покупки
                    message = f"❌ Покупка отменена\n"
                    message += f"👤 {get_mention(from_id, chat_id)} отменил покупку"
                    send_message(peer_id, message, reply_to)
                    
                    # Уведомление владельцу
                    owner_msg = f"❌ Отмена покупки\n\n"
                    owner_msg += f"👤 {get_mention(from_id, chat_id)} отменил покупку товара"
                    send_message(BOT_OWNER_ID, owner_msg)
                else:
                    send_message(peer_id, "❌ Неверный формат команды!\n💡 Используйте: /shop [номер] или /shop [номер] yes/no", reply_to)
            
            # Команда newrole - изменение названия роли
            elif cmd in ['newrole', 'новаяроль']:
                if chat_id == 0 or not check_chat(chat_id):
                    return
                    
                if get_role(from_id, chat_id) < 99:  # Только владелец проекта (Level 99+)
                    send_message(peer_id, "❌ Недостаточно прав! Команда доступна только владельцу проекта! 👑", reply_to)
                    return
                
                if len(args) < 3:
                    message = "❌ Неверный формат команды!\n"
                    message += "📝 Использование: /newrole [уровень] [новое название]\n\n"
                    message += "🎭 Уровни ролей:\n"
                    message += "0 - Хелпер/Лидер\n10 - Модератор\n20 - Старший модератор\n25 - Администратор\n30 - Старший Администратор\n40 - Заместитель Главного Следящего\n45 - Главный Следящий\n50 - Куратор Администрации\n60 - Заместитель Главного Администратора\n65 - Главный Администратор\n70 - Специальный Администратор\n75 - Заместитель Руководителя Проекта\n80 - Руководитель Проекта\n90 - Заместитель Основателя\n95 - Основатель Проекта\n99 - Владелец Проекта\n100 - Владелец Проекта\n\n"
                    message += "📝 Пример: /newrole 10 \"Модератор\""
                    send_message(peer_id, message, reply_to)
                    return
                
                try:
                    role_level = int(args[1])
                    new_name = ' '.join(args[2:])
                    
                    # Проверяем допустимые уровни ролей
                    valid_roles = [0, 10, 20, 25, 30, 40, 45, 50, 60, 65, 70, 75, 80, 90, 95, 99, 100]
                    if role_level not in valid_roles:
                        send_message(peer_id, "❌ Неверный уровень роли! Используйте допустимые уровни из списка выше.", reply_to)
                        return
                    
                    if len(new_name) > 50:
                        send_message(peer_id, "❌ Название роли слишком длинное! Максимум 50 символов.", reply_to)
                        return
                    
                    if len(new_name) < 2:
                        send_message(peer_id, "❌ Название роли слишком короткое! Минимум 2 символа.", reply_to)
                        return
                    
                    # Проверяем, не пытается ли изменить роль выше своей
                    if role_level >= get_role(from_id, chat_id) and from_id != BOT_OWNER_ID:
                        send_message(peer_id, "❌ Вы не можете изменить название роли такого же или выше уровня!", reply_to)
                        return
                    
                    # Сохраняем кастомное название
                    sql.execute("INSERT OR REPLACE INTO custom_role_names VALUES (?, ?, ?)", 
                               (chat_id, role_level, new_name))
                    
                    # Если роль была отключена - включаем её обратно
                    sql.execute("DELETE FROM disabled_roles WHERE chat_id = ? AND role_level = ?", (chat_id, role_level))
                    
                    database.commit()
                    
                    old_name = get_role_name(role_level)  # Стандартное название
                    message = f"✅ Название роли успешно изменено! 🎉\n"
                    message += f"📊 Уровень роли: {role_level}\n"
                    message += f"🔄 Было: {old_name}\n"
                    message += f"✅ Стало: {new_name}\n\n"
                    message += f"💡 Теперь во всех командах будет отображаться новое название!"
                    send_message(peer_id, message, reply_to)
                    
                except ValueError:
                    send_message(peer_id, "❌ Уровень роли должен быть числом!", reply_to)
                except Exception as e:
                    send_message(peer_id, f"❌ Ошибка изменения названия роли: {str(e)}", reply_to)
            
            # Команда delrole - снятие роли или отключение уровня
            elif cmd in ['delrole', 'resetrole', 'сброситьроль', 'удалитьроль']:
                if chat_id == 0 or not check_chat(chat_id):
                    return
                    
                if get_role(from_id, chat_id) < 99:  # Только владелец проекта (Level 99+)
                    send_message(peer_id, "❌ Недостаточно прав! Команда доступна только владельцу проекта! 👑", reply_to)
                    return
                
                # Пробуем получить пользователя из упоминания/ответа
                target_id = get_user_from_reply_or_mention(event.obj, args, 1)
                
                if target_id:
                    # Если указан пользователь - снимаем с него роль
                    set_role(target_id, chat_id, 0)
                    send_message(peer_id, f"✅ Роль успешно снята с {get_mention(target_id, chat_id)}!", reply_to)
                    return

                if len(args) < 2:
                    message = "❌ Укажите уровень роли или пользователя!\n"
                    message += "📝 Использование:\n"
                    message += "— /delrole @user (снять роль)\n"
                    message += "— /delrole [уровень] (скрыть/сбросить роль)\n"
                    send_message(peer_id, message, reply_to)
                    return
                
                try:
                    role_level = int(args[1])
                    
                    # Проверяем допустимые уровни
                    valid_roles = [0, 10, 20, 25, 30, 40, 45, 50, 60, 65, 70, 75, 80, 90, 95, 99, 100]
                    if role_level not in valid_roles:
                        send_message(peer_id, "❌ Некорректный уровень роли!", reply_to)
                        return

                    # 1. Удаляем кастомное название
                    sql.execute("DELETE FROM custom_role_names WHERE chat_id = ? AND role_level = ?", 
                               (chat_id, role_level))
                    
                    # 2. Добавляем в список отключенных ролей (чтобы "удалить" стандартную из списка)
                    sql.execute("INSERT OR IGNORE INTO disabled_roles VALUES (?, ?)", (chat_id, role_level))
                    
                    database.commit()
                    
                    message = f"✅ Роль уровня {role_level} успешно отключена и скрыта из списка! 🗑️\n"
                    message += f"💡 Чтобы вернуть её, установите новое название через /newrole"
                    send_message(peer_id, message, reply_to)
                    
                except ValueError:
                    send_message(peer_id, "❌ Укажите числовой уровень роли или пользователя!", reply_to)
                except Exception as e:
                    send_message(peer_id, f"❌ Ошибка: {str(e)}", reply_to)
            


            # Команда q (самокик)
            elif cmd in ['q']:
                if chat_id == 0 or not check_chat(chat_id):
                    return
                
                # Добавляем в список кикнутых
                sql.execute(f"CREATE TABLE IF NOT EXISTS kicked_{chat_id} (user_id INTEGER)")
                sql.execute(f"INSERT OR IGNORE INTO kicked_{chat_id} VALUES (?)", (from_id,))
                database.commit()
                
                # Кикаем пользователя
                if kick_user(chat_id, from_id):
                    user_nick = get_nick(from_id, chat_id) or get_user_info(from_id)
                    message = f"🚪 {get_mention(from_id, chat_id)} покинул беседу\n"
                    message += f"⛔ Может вернуться только по приглашению"
                    send_message(peer_id, message, reply_to)
                else:
                    send_message(peer_id, "❌ Не удалось покинуть беседу!", reply_to)
            
            # Команда getban
            elif cmd in ['getban', 'гетбан']:
                if chat_id == 0 or not check_chat(chat_id):
                    return
                    
                if get_role(from_id, chat_id) < 40:
                    send_message(peer_id, "❌ Недостаточно прав!", reply_to)
                    return
                
                target_id = get_user_from_reply_or_mention(event.obj, args, 1)
                if not target_id:
                    send_message(peer_id, "❌ Укажите пользователя или ответьте на сообщение!", reply_to)
                    return
                
                if is_banned(target_id, chat_id):
                    try:
                        sql.execute(f"SELECT moder, reason, date, ban_until FROM bans_{chat_id} WHERE user_id = {target_id}")
                        ban_info = sql.fetchone()
                        
                        if ban_info:
                            moder_id, reason, ban_date, ban_until = ban_info
                            
                            user_nick = get_nick(target_id, chat_id) or get_user_info(target_id)
                            moder_nick = get_nick(moder_id, chat_id) or get_user_info(moder_id)
                            
                            ban_date_str = datetime.fromtimestamp(ban_date).strftime('%d.%m.%Y %H:%M')
                            
                            message = f"🔴 Ник пользователя: {get_mention(target_id, chat_id)}\n"
                            message += f"📅 Дата блокировки: {ban_date_str}\n"
                            
                            if ban_until > 0:
                                unban_date_str = datetime.fromtimestamp(ban_until).strftime('%d.%m.%Y %H:%M')
                                message += f"🔓 Дата разблокировки: {unban_date_str}\n"
                            else:
                                message += f"🔓 Дата разблокировки: Перманентный бан\n"
                            
                            message += f"👤 Никнейм Администратора: {get_mention(moder_id, chat_id)}\n"
                            message += f"📝 Причина: {reason}"
                            
                            send_message(peer_id, message, reply_to)
                        else:
                            send_message(peer_id, f"✅ {get_mention(target_id, chat_id)} не заблокирован", reply_to)
                    except Exception as e:
                        print(f"Ошибка getban: {e}")
                        send_message(peer_id, f"✅ {get_mention(target_id, chat_id)} не заблокирован", reply_to)
                else:
                    user_nick = get_nick(target_id, chat_id) or get_user_info(target_id)
                    send_message(peer_id, f"✅ {get_mention(target_id, chat_id)} не заблокирован", reply_to)
            
            # Команда off_bot
            elif cmd in ['off_bot']:
                if from_id not in special_admins:
                    send_message(peer_id, "❌ Недостаточно прав! Команда доступна только спец администраторам!", reply_to)
                    return
                
                # Отправляем сообщение только в чат где была выполнена команда
                shutdown_msg = "🔴 Бот выключен спец администратором\n⚠️ Для возобновления работы обратитесь к администрации"
                send_message(peer_id, shutdown_msg, reply_to)
                
                print(f"Бот выключен командой /off_bot от спец админа {from_id}")
                database.close()
                exit(0)
            
            # Команда start_bot
            elif cmd in ['start_bot']:
                if from_id != BOT_OWNER_ID:
                    send_message(peer_id, "❌ Недостаточно прав! Команда доступна только владельцу бота!", reply_to)
                    return
                
                startup_msg = "🤖✨ Бот успешно запущен и готов к работе!\n💫 Все системы в норме\n🚀 Приятного использования!"
                
                sql.execute("SELECT peer_id FROM chats")
                all_chats = sql.fetchall()
                success_count = 0
                for chat in all_chats:
                    try:
                        send_message(chat[0], startup_msg)
                        success_count += 1
                    except:
                        pass
                
                send_message(peer_id, f"✅ Уведомление о запуске отправлено в {success_count} чатов!", reply_to)
            
            # Команда stop_bot
            elif cmd in ['stop_bot', 'остановить']:
                if from_id != BOT_OWNER_ID:
                    send_message(peer_id, "❌ Недостаточно прав! Команда доступна только владельцу бота!", reply_to)
                    return
                
                shutdown_msg = "🔴 Бот остановлен для обновления или по тех причинам. \n🔄 Ожидайте пока разработчики бота включат бота"
                
                sql.execute("SELECT peer_id FROM chats")
                all_chats = sql.fetchall()
                for chat in all_chats:
                    try:
                        send_message(chat[0], shutdown_msg)
                    except:
                        pass
                
                try:
                    send_message(from_id, shutdown_msg)
                except:
                    pass
                
                print("Бот остановлен командой /stop_bot")
                database.commit()
                exit(0)
            
            # Команда transfer
            elif cmd in ['transfer', 'перевод']:
                if chat_id == 0 or not check_chat(chat_id):
                    return
                
                target_id = get_user_from_reply_or_mention(event.obj, args, 1)
                if not target_id:
                    send_message(peer_id, "❌ Укажите пользователя или ответьте на сообщение!", reply_to)
                    return
                
                if target_id == from_id:
                    send_message(peer_id, "❌ Нельзя переводить монеты самому себе!", reply_to)
                    return
                
                # Определяем количество монет
                if 'reply_message' in event.obj.message:
                    if len(args) < 2:
                        send_message(peer_id, "❌ Укажите количество монет!\nПример: /transfer 100", reply_to)
                        return
                    try:
                        amount = int(args[1])
                    except:
                        send_message(peer_id, "❌ Укажите корректное количество!", reply_to)
                        return
                else:
                    if len(args) < 3:
                        send_message(peer_id, "❌ Укажите количество монет!\nПример: /transfer @user 100", reply_to)
                        return
                    try:
                        amount = int(args[2])
                    except:
                        send_message(peer_id, "❌ Укажите корректное количество!", reply_to)
                        return
                
                if amount <= 0:
                    send_message(peer_id, "❌ Количество должно быть больше 0!", reply_to)
                    return
                
                # Проверяем баланс отправителя
                sql.execute(f"CREATE TABLE IF NOT EXISTS bonuses_{chat_id} (user_id INTEGER, last_bonus INTEGER, streak INTEGER, coins INTEGER)")
                sql.execute(f"SELECT coins FROM bonuses_{chat_id} WHERE user_id = {from_id}")
                sender_balance = sql.fetchone()
                sender_coins = sender_balance[0] if sender_balance else 0
                
                if sender_coins < amount:
                    send_message(peer_id, f"❌ Недостаточно монет! У вас: {sender_coins} 💰", reply_to)
                    return
                
                # Создаем записи если их нет
                if not sender_balance:
                    sql.execute(f"INSERT INTO bonuses_{chat_id} VALUES (?, 0, 0, 0)", (from_id,))
                
                sql.execute(f"SELECT coins FROM bonuses_{chat_id} WHERE user_id = {target_id}")
                if not sql.fetchone():
                    sql.execute(f"INSERT INTO bonuses_{chat_id} VALUES (?, 0, 0, 0)", (target_id,))
                
                # Рассчитываем комиссию
                commission_rate = 0.1  # 10% по умолчанию
                try:
                    sql.execute(f"SELECT vip_type FROM vip_statuses WHERE user_id = {from_id} AND chat_id = {chat_id}")
                    vip_result = sql.fetchone()
                    if vip_result:
                        commission_rate = 0.05  # 5% для VIP
                except:
                    pass

                commission = int(amount * commission_rate)
                amount_to_send = amount - commission

                # Зачисляем комиссию на баланс бота
                sql.execute("INSERT OR IGNORE INTO global_coins (user_id, coins) VALUES (?, 0)", (BOT_OWNER_ID,))
                sql.execute("UPDATE global_coins SET coins = coins + ? WHERE user_id = ?", (commission, BOT_OWNER_ID))

                # Выполняем перевод
                sql.execute(f"UPDATE bonuses_{chat_id} SET coins = coins - ? WHERE user_id = ?", (amount, from_id))
                sql.execute(f"UPDATE bonuses_{chat_id} SET coins = coins + ? WHERE user_id = ?", (amount_to_send, target_id))
                database.commit()

                sender_nick = get_nick(from_id, chat_id) or get_user_info(from_id)
                target_nick = get_nick(target_id, chat_id) or get_user_info(target_id)

                message = f"💸 Перевод выполнен!\n"
                message += f"👤 От: {get_mention(from_id, chat_id)}\n"
                message += f"👤 Кому: {get_mention(target_id, chat_id)}\n"
                message += f"💰 Сумма: {amount_to_send} монет (комиссия: {commission})"
                send_message(peer_id, message, reply_to)



            # Команда givemoney
            elif cmd in ['givemoney', 'выдатьденьги']:
                if from_id != BOT_OWNER_ID:
                    send_message(peer_id, "❌ Недостаточно прав! Команда доступна только владельцу бота!", reply_to)
                    return
                
                target_id = get_user_from_reply_or_mention(event.obj, args, 1)
                if not target_id:
                    send_message(peer_id, "❌ Укажите пользователя или ответьте на сообщение!", reply_to)
                    return
                
                # Определяем количество монет
                if 'reply_message' in event.obj.message:
                    if len(args) < 2:
                        send_message(peer_id, "❌ Укажите количество монет!\nПример: /givemoney 1000", reply_to)
                        return
                    try:
                        amount = int(args[1])
                    except:
                        send_message(peer_id, "❌ Укажите корректное количество!", reply_to)
                        return
                else:
                    if len(args) < 3:
                        send_message(peer_id, "❌ Укажите количество монет!\nПример: /givemoney @user 1000", reply_to)
                        return
                    try:
                        amount = int(args[2])
                    except:
                        send_message(peer_id, "❌ Укажите корректное количество!", reply_to)
                        return
                
                if amount <= 0:
                    send_message(peer_id, "❌ Количество должно быть больше 0!", reply_to)
                    return
                
                # Выдаем монеты во всех чатах где есть пользователь
                sql.execute("SELECT chat_id FROM chats")
                all_chats = sql.fetchall()
                updated_chats = 0
                
                for (chat,) in all_chats:
                    try:
                        sql.execute(f"CREATE TABLE IF NOT EXISTS bonuses_{chat} (user_id INTEGER, last_bonus INTEGER, streak INTEGER, coins INTEGER)")
                        sql.execute(f"SELECT coins FROM bonuses_{chat} WHERE user_id = {target_id}")
                        if sql.fetchone():
                            sql.execute(f"UPDATE bonuses_{chat} SET coins = coins + ? WHERE user_id = ?", (amount, target_id))
                        else:
                            sql.execute(f"INSERT INTO bonuses_{chat} VALUES (?, 0, 0, ?)", (target_id, amount))
                        updated_chats += 1
                    except:
                        pass
                
                database.commit()
                
                target_nick = get_user_info(target_id)
                message = f"💰 Монеты выданы!\n"
                message += f"👤 Пользователь: {get_mention(target_id, chat_id)}\n"
                message += f"💸 Сумма: {amount} монет\n"
                message += f"📊 Обновлено чатов: {updated_chats}"
                send_message(peer_id, message, reply_to)
                
                # Уведомление владельцу бота
                try:
                    chat_name = "Личные сообщения"
                    if chat_id > 0:
                        try:
                            conv = vk.messages.getConversationsById(peer_ids=peer_id)
                            chat_name = conv['items'][0]['chat_settings']['title']
                        except:
                            chat_name = f"Чат {chat_id}"
                    
                    owner_msg = f"💰 Выдача монет\n\n"
                    owner_msg += f"👤 {get_mention(from_id, chat_id)} выдал монеты\n"
                    owner_msg += f"🎯 {get_mention(target_id, chat_id)} получил {amount} монет\n"
                    owner_msg += f"💬 Чат: {chat_name}"
                    send_message(BOT_OWNER_ID, owner_msg)
                except:
                    pass
            
            # Команда delmoney
            elif cmd in ['delmoney', 'удалитьденьги']:
                if from_id != BOT_OWNER_ID:
                    send_message(peer_id, "❌ Недостаточно прав! Команда доступна только владельцу бота!", reply_to)
                    return
                
                target_id = get_user_from_reply_or_mention(event.obj, args, 1)
                if not target_id:
                    send_message(peer_id, "❌ Укажите пользователя или ответьте на сообщение!", reply_to)
                    return
                
                # Определяем количество монет
                if 'reply_message' in event.obj.message:
                    if len(args) < 2:
                        send_message(peer_id, "❌ Укажите количество монет!\nПример: /delmoney 1000", reply_to)
                        return
                    try:
                        amount = int(args[1])
                    except:
                        send_message(peer_id, "❌ Укажите корректное количество!", reply_to)
                        return
                else:
                    if len(args) < 3:
                        send_message(peer_id, "❌ Укажите количество монет!\nПример: /delmoney @user 1000", reply_to)
                        return
                    try:
                        amount = int(args[2])
                    except:
                        send_message(peer_id, "❌ Укажите корректное количество!", reply_to)
                        return
                
                if amount <= 0:
                    send_message(peer_id, "❌ Количество должно быть больше 0!", reply_to)
                    return
                
                # Удаляем монеты во всех чатах где есть пользователь
                sql.execute("SELECT chat_id FROM chats")
                all_chats = sql.fetchall()
                updated_chats = 0
                
                for (chat,) in all_chats:
                    try:
                        sql.execute(f"CREATE TABLE IF NOT EXISTS bonuses_{chat} (user_id INTEGER, last_bonus INTEGER, streak INTEGER, coins INTEGER)")
                        sql.execute(f"SELECT coins FROM bonuses_{chat} WHERE user_id = {target_id}")
                        if sql.fetchone():
                            sql.execute(f"UPDATE bonuses_{chat} SET coins = CASE WHEN coins >= ? THEN coins - ? ELSE 0 END WHERE user_id = ?", (amount, amount, target_id))
                            updated_chats += 1
                    except:
                        pass
                
                database.commit()
                
                target_nick = get_user_info(target_id)
                message = f"💸 Монеты удалены!\n"
                message += f"👤 Пользователь: {get_mention(target_id, chat_id)}\n"
                message += f"💰 Удалено: {amount} монет\n"
                message += f"📊 Обновлено чатов: {updated_chats}"
                send_message(peer_id, message, reply_to)
                
                # Уведомление владельцу бота
                try:
                    chat_name = "Личные сообщения"
                    if chat_id > 0:
                        try:
                            conv = vk.messages.getConversationsById(peer_ids=peer_id)
                            chat_name = conv['items'][0]['chat_settings']['title']
                        except:
                            chat_name = f"Чат {chat_id}"
                    
                    owner_msg = f"💸 Удаление монет\n\n"
                    owner_msg += f"👤 {get_mention(from_id, chat_id)} удалил монеты\n"
                    owner_msg += f"🎯 У {get_mention(target_id, chat_id)} удалено {amount} монет\n"
                    owner_msg += f"💬 Чат: {chat_name}"
                    send_message(BOT_OWNER_ID, owner_msg)
                except:
                    pass
            
            # Команда givevip
            elif cmd in ['givevip', 'выдатьвип']:
                if from_id != BOT_OWNER_ID:
                    send_message(peer_id, "❌ Недостаточно прав! Команда доступна только владельцу бота! 👑", reply_to)
                    return
                
                target_id = get_user_from_reply_or_mention(event.obj, args, 1)
                if not target_id:
                    send_message(peer_id, "❌ Укажите пользователя или ответьте на сообщение!\n📝 Пример: /givevip @user gold 30", reply_to)
                    return
                
                # Определяем тип VIP и дни
                if 'reply_message' in event.obj.message:
                    if len(args) < 3:
                        send_message(peer_id, "❌ Укажите тип VIP и количество дней!\n📝 Пример: /givevip gold 30 или /givevip 1 30\n\n🎆 Доступные типы:\n1 - gold\n2 - elite\n3 - diamond", reply_to)
                        return
                    vip_input = args[1].lower()
                    try:
                        days = int(args[2])
                    except:
                        send_message(peer_id, "❌ Укажите корректное количество дней!", reply_to)
                        return
                else:
                    if len(args) < 4:
                        send_message(peer_id, "❌ Укажите тип VIP и количество дней!\n📝 Пример: /givevip @user gold 30 или /givevip @user 1 30\n\n🎆 Доступные типы:\n1 - gold\n2 - elite\n3 - diamond", reply_to)
                        return
                    vip_input = args[2].lower()
                    try:
                        days = int(args[3])
                    except:
                        send_message(peer_id, "❌ Укажите корректное количество дней!", reply_to)
                        return
                
                # Конвертируем ID в тип VIP
                vip_mapping = {'1': 'gold', '2': 'elite', '3': 'diamond'}
                if vip_input in vip_mapping:
                    vip_type = vip_mapping[vip_input]
                elif vip_input in ['gold', 'elite', 'diamond']:
                    vip_type = vip_input
                else:
                    send_message(peer_id, "❌ Неверный тип VIP!\n🎆 Доступные типы:\n1 - gold\n2 - elite\n3 - diamond", reply_to)
                    return
                
                if days <= 0 or days > 365:
                    send_message(peer_id, "❌ Количество дней должно быть от 1 до 365!", reply_to)
                    return
                
                # Выдаем VIP во всех чатах
                sql.execute("SELECT chat_id FROM chats")
                all_chats = sql.fetchall()
                end_time = int(time.time()) + (days * 24 * 60 * 60)
                updated_chats = 0
                
                for (chat,) in all_chats:
                    try:
                        sql.execute("INSERT OR REPLACE INTO vip_statuses VALUES (?, ?, ?, ?)", (target_id, chat, vip_type, end_time))
                        updated_chats += 1
                    except:
                        pass
                
                database.commit()
                
                vip_names = {'gold': '🥇 GOLD VIP', 'elite': '📎 ELITE VIP', 'diamond': '💎 DIAMOND VIP'}
                target_nick = get_user_info(target_id)
                message = f"🎉 VIP статус выдан!\n"
                message += f"👤 Пользователь: {get_mention(target_id, chat_id)}\n"
                message += f"👑 Тип: {vip_names.get(vip_type, vip_type)}\n"
                message += f"⏰ Срок: {days} дней\n"
                message += f"📊 Обновлено чатов: {updated_chats}"
                send_message(peer_id, message, reply_to)
                
                # Уведомление владельцу бота
                try:
                    chat_name = "Личные сообщения"
                    if chat_id > 0:
                        try:
                            conv = vk.messages.getConversationsById(peer_ids=peer_id)
                            chat_name = conv['items'][0]['chat_settings']['title']
                        except:
                            chat_name = f"Чат {chat_id}"
                    
                    owner_msg = f"🎆 Выдача VIP статуса\n\n"
                    owner_msg += f"👤 {get_mention(from_id, chat_id)} выдал VIP\n"
                    owner_msg += f"🎯 {get_mention(target_id, chat_id)} получил {vip_names.get(vip_type, vip_type)}\n"
                    owner_msg += f"⏰ На {days} дней\n"
                    owner_msg += f"💬 Чат: {chat_name}"
                    send_message(BOT_OWNER_ID, owner_msg)
                except:
                    pass
            
            # Команда delvip
            elif cmd in ['delvip', 'удалитьвип']:
                if from_id != BOT_OWNER_ID:
                    send_message(peer_id, "❌ Недостаточно прав! Команда доступна только владельцу бота! 👑", reply_to)
                    return
                
                target_id = get_user_from_reply_or_mention(event.obj, args, 1)
                if not target_id:
                    send_message(peer_id, "❌ Укажите пользователя или ответьте на сообщение!\n📝 Пример: /delvip @user", reply_to)
                    return
                
                # Удаляем VIP статус во всех чатах
                sql.execute("DELETE FROM vip_statuses WHERE user_id = ?", (target_id,))
                deleted_count = sql.rowcount
                database.commit()
                
                target_nick = get_user_info(target_id)
                if deleted_count > 0:
                    message = f"❌ VIP статус удалён!\n"
                    message += f"👤 Пользователь: {get_mention(target_id, chat_id)}\n"
                    message += f"📊 Удалено из {deleted_count} чатов"
                    
                    # Уведомление владельцу бота
                    try:
                        chat_name = "Личные сообщения"
                        if chat_id > 0:
                            try:
                                conv = vk.messages.getConversationsById(peer_ids=peer_id)
                                chat_name = conv['items'][0]['chat_settings']['title']
                            except:
                                chat_name = f"Чат {chat_id}"
                        
                        owner_msg = f"❌ Удаление VIP статуса\n\n"
                        owner_msg += f"👤 {get_mention(from_id, chat_id)} удалил VIP\n"
                        owner_msg += f"🎯 У {get_mention(target_id, chat_id)} удален VIP статус\n"
                        owner_msg += f"💬 Чат: {chat_name}"
                        send_message(BOT_OWNER_ID, owner_msg)
                    except:
                        pass
                else:
                    message = f"ℹ️ У {get_mention(target_id, chat_id)} нет VIP статуса"
                
                send_message(peer_id, message, reply_to)
            
            # Команда del
            elif cmd in ['del', 'удалить']:
                if chat_id == 0 or not check_chat(chat_id):
                    return
                
                # Владелец бота может удалять всё
                if from_id != BOT_OWNER_ID and get_role(from_id, chat_id) < 60:
                    send_message(peer_id, "❌ Недостаточно прав!", reply_to)
                    return
                
                if 'reply_message' not in event.obj.message:
                    send_message(peer_id, "❌ Ответьте на сообщение!", reply_to)
                    return
                
                try:
                    reply_msg_id = event.obj.message['reply_message']['conversation_message_id']
                    # Удаляем команду
                    vk.messages.delete(cmids=conversation_message_id, delete_for_all=1, peer_id=peer_id)
                    # Удаляем целевое сообщение
                    vk.messages.delete(cmids=reply_msg_id, delete_for_all=1, peer_id=peer_id)
                except Exception as e:
                    print(f"[DEL ERROR] {e}")
            
            # Команда mutelist
            elif cmd in ['mutelist', 'мутлист']:
                if chat_id == 0 or not check_chat(chat_id):
                    return
                    
                if get_new_role_level(from_id, chat_id) < 60:
                    send_message(peer_id, "❌ Недостаточно прав!", reply_to)
                    return
                
                try:
                    sql.execute(f"CREATE TABLE IF NOT EXISTS mutes_{chat_id} (user_id INTEGER, moder INTEGER, reason TEXT, end_time INTEGER)")
                    sql.execute(f"SELECT user_id, reason, end_time FROM mutes_{chat_id}")
                    mutes = sql.fetchall()
                    
                    active_mutes = []
                    for user_id, reason, end_time in mutes:
                        if int(time.time()) < end_time:
                            active_mutes.append((user_id, reason, end_time))
                    
                    if not active_mutes:
                        send_message(peer_id, "🔇 Замученные пользователи: отсутствуют", reply_to)
                    else:
                        mute_text = "🔇 Замученные пользователи:\n"
                        for i, (user_id, reason, end_time) in enumerate(active_mutes, 1):
                            user_nick = get_nick(user_id, chat_id) or get_user_info(user_id)
                            end_str = datetime.fromtimestamp(end_time).strftime('%H:%M %d.%m')
                            mute_text += f"{i}. {get_mention(user_id, chat_id)} до {end_str}\n"
                        send_message(peer_id, mute_text, reply_to)
                except Exception as e:
                    send_message(peer_id, "❌ Ошибка получения списка!", reply_to)
            
            # Команда stats
            elif cmd in ['stats', 'стата']:
                print(f"[DEBUG] STATS команда обрабатывается в main_full.py строка ~2800")
                handle_stats(event.obj, args, chat_id, from_id, peer_id, reply_to, get_user_from_reply_or_mention, get_new_role_level, get_user_info, get_nick, get_role, get_role_name, get_warn_count, get_user_stats, get_marriage_partner, sql, database, send_message)
            
            # Команда mtop
            elif cmd in ['mtop', 'мтоп']:
                if chat_id == 0 or not check_chat(chat_id):
                    return
                # Команда доступна всем (0+)

                # Сбрасываем предыдущую сессию и начинаем новую
                from commands.mtop_command import mtop_sessions
                if chat_id in mtop_sessions:
                    del mtop_sessions[chat_id]
                handle_mtop(chat_id, from_id, peer_id, 1, sql, vk, send_message, get_user_info, get_nick)
            
            # Команда test
            elif cmd in ['test', 'тест']:
                if chat_id > 0 and get_role(from_id, chat_id) < 20:
                    send_message(peer_id, "❌ Недостаточно прав! Команда доступна с старшего модератора!", reply_to)
                    return
                try:
                    print(f"[TEST LOG] Команда /test от пользователя {from_id}")
                    
                    # Тест базовых функций бота
                    test_results = []
                    
                    # Тест отправки сообщений
                    try:
                        send_message(peer_id, "🔄 Тестирование функций бота...")
                        test_results.append("✅ Отправка сообщений: работает")
                        print(f"[TEST LOG] Отправка сообщений - OK")
                    except Exception as e:
                        test_results.append(f"❌ Отправка сообщений: ошибка - {e}")
                        print(f"[TEST ERROR] Отправка сообщений: {e}")
                    
                    # Тест базы данных
                    try:
                        sql.execute("SELECT name FROM sqlite_master WHERE type='table'")
                        tables = sql.fetchall()
                        test_results.append(f"✅ База данных: {len(tables)} таблиц")
                        print(f"[TEST LOG] База данных - OK, таблиц: {len(tables)}")
                    except Exception as e:
                        test_results.append(f"❌ База данных: ошибка - {e}")
                        print(f"[TEST ERROR] База данных: {e}")
                    
                    # Тест получения информации о пользователе
                    try:
                        user_info = get_user_info(from_id)
                        test_results.append(f"✅ Получение данных пользователя: {user_info}")
                        print(f"[TEST LOG] Данные пользователя - OK: {user_info}")
                    except Exception as e:
                        test_results.append(f"❌ Получение данных пользователя: ошибка - {e}")
                        print(f"[TEST ERROR] Данные пользователя: {e}")
                    
                    # Тест системы ролей
                    if chat_id > 0:
                        try:
                            user_role = get_role(from_id, chat_id)
                            role_name = get_role_name(user_role)
                            test_results.append(f"✅ Система ролей: {role_name} ({user_role})")
                            print(f"[TEST LOG] Система ролей - OK: {role_name}")
                        except Exception as e:
                            test_results.append(f"❌ Система ролей: ошибка - {e}")
                            print(f"[TEST ERROR] Система ролей: {e}")
                    
                    # Тест системы монет
                    if chat_id > 0:
                        try:
                            sql.execute(f"SELECT coins FROM bonuses_{chat_id} WHERE user_id = {from_id}")
                            coins_result = sql.fetchone()
                            coins = coins_result[0] if coins_result else 0
                            test_results.append(f"✅ Система монет: {coins} монет")
                            print(f"[TEST LOG] Система монет - OK: {coins}")
                        except Exception as e:
                            test_results.append(f"❌ Система монет: ошибка - {e}")
                            print(f"[TEST ERROR] Система монет: {e}")
                    
                    # Тест VK API
                    try:
                        group_info = vk.groups.getById()
                        test_results.append(f"✅ VK API: подключение активно")
                        print(f"[TEST LOG] VK API - OK")
                    except Exception as e:
                        test_results.append(f"❌ VK API: ошибка - {e}")
                        print(f"[TEST ERROR] VK API: {e}")
                    
                    # Тест отправки обычного сообщения
                    try:
                        test_msg = vk.messages.send(
                            peer_id=peer_id,
                            message="Тестовое сообщение от бота",
                            random_id=random.randint(1, 1000000)
                        )
                        test_results.append(f"✅ Отправка сообщений: работает")
                        print(f"[TEST LOG] Отправка сообщений - OK")
                    except Exception as e:
                        test_results.append(f"❌ Отправка сообщений: ошибка - {e}")
                        print(f"[TEST ERROR] Отправка сообщений: {e}")
                    
                    # Тест системы кэширования
                    try:
                        cache_size = len(processed_messages)
                        test_results.append(f"✅ Кэш сообщений: {cache_size} записей")
                        print(f"[TEST LOG] Кэш - OK: {cache_size} записей")
                    except Exception as e:
                        test_results.append(f"❌ Кэш сообщений: ошибка - {e}")
                        print(f"[TEST ERROR] Кэш: {e}")
                    
                    # Формируем итоговый отчет
                    report = "Результаты тестирования:\n\n" + "\n".join(test_results)
                    report += "\n\nТестирование завершено!"
                    report += "\nПроверьте консоль для подробных логов."
                    
                    print(f"[TEST LOG] Отправляем отчет о тестировании")
                    send_message(peer_id, report, reply_to)
                    print(f"[TEST LOG] Тестирование завершено для пользователя {from_id}")
                    
                except Exception as e:
                    print(f"[TEST ERROR] Общая ошибка команды /test: {e}")
                    error_msg = f"❌ Ошибка при тестировании: {str(e)[:100]}..."
                    send_message(peer_id, error_msg, reply_to)
            
            # Команда yes (только для передачи прав)
            elif cmd in ['yes', 'да']:
                if chat_id == 0 or not check_chat(chat_id):
                    return
                
                # Проверяем передачу прав
                try:
                    sql.execute(f"CREATE TABLE IF NOT EXISTS transfer_pending_{chat_id} (from_user INTEGER, to_user INTEGER, timestamp INTEGER)")
                    sql.execute(f"SELECT from_user, to_user, timestamp FROM transfer_pending_{chat_id} WHERE to_user = {from_id}")
                    pending = sql.fetchone()
                    
                    if pending and (int(time.time()) - pending[2]) < 300:
                        from_user, to_user, _ = pending
                        
                        sql.execute(f"UPDATE chats SET owner_id = ? WHERE chat_id = ?", (to_user, chat_id))
                        set_role(from_user, chat_id, 4)
                        sql.execute(f"DELETE FROM transfer_pending_{chat_id} WHERE from_user = {from_user}")
                        database.commit()
                        
                        message = f"✅ Удачно! Вы передали права главного владельца пользователю:\n"
                        message += f"{get_mention(to_user, chat_id)}"
                        send_message(peer_id, message, reply_to)
                        return
                except Exception as e:
                    print(f"Ошибка передачи прав: {e}")
                
                # Если ничего не найдено
                user_nick = get_nick(from_id, chat_id) or get_user_info(from_id)
                send_message(peer_id, f"🤷 {get_mention(from_id, chat_id)}, вам ничего не предлагали!", reply_to)
            
            # Команда no (только для передачи прав)
            elif cmd in ['no', 'нет']:
                if chat_id == 0 or not check_chat(chat_id):
                    return
                
                # Проверяем передачу прав
                try:
                    sql.execute(f"CREATE TABLE IF NOT EXISTS transfer_pending_{chat_id} (from_user INTEGER, to_user INTEGER, timestamp INTEGER)")
                    sql.execute(f"SELECT from_user, timestamp FROM transfer_pending_{chat_id} WHERE to_user = {from_id}")
                    pending = sql.fetchone()
                    if pending and (int(time.time()) - pending[1]) < 300:
                        sql.execute(f"DELETE FROM transfer_pending_{chat_id} WHERE to_user = {from_id}")
                        database.commit()
                        send_message(peer_id, "✅ Хорошо, передача прав главного владельца отменена!", reply_to)
                        return
                except Exception as e:
                    print(f"Ошибка отмены передачи прав: {e}")
                
                # Если ничего не найдено
                user_nick = get_nick(from_id, chat_id) or get_user_info(from_id)
                send_message(peer_id, f"🤷 {get_mention(from_id, chat_id)}, вам ничего не предлагали!", reply_to)
            
            # Команда asu_cmd (выдача доступа)
            elif cmd in ['asu_cmd']:
                if not has_command_access(from_id, 'asu_cmd'):
                    send_message(peer_id, "❌ Недостаточно прав! Команда доступна только владельцу бота!", reply_to)
                    return
                
                target_id = get_user_from_reply_or_mention(event.obj, args, 1)
                if not target_id:
                    send_message(peer_id, "❌ Укажите пользователя или ответьте на сообщение!", reply_to)
                    return
                
                # Определяем команду
                if 'reply_message' in event.obj.message:
                    if len(args) < 2:
                        send_message(peer_id, "❌ Укажите команду!\nПример: /asu_cmd kick", reply_to)
                        return
                    command_to_allow = args[1].lower().replace('/', '')
                else:
                    if len(args) < 3:
                        send_message(peer_id, "❌ Укажите команду!\nПример: /asu_cmd @user kick", reply_to)
                        return
                    command_to_allow = args[2].lower().replace('/', '')
                
                # Проверяем ограничения для не-владельцев
                if from_id != BOT_OWNER_ID:
                    # Нельзя выдавать доступ к /asu_cmd, /addmoder, /addadmin, /givevip, /delvip
                    if command_to_allow in ['asu_cmd', 'addmoder', 'addadmin', 'givevip', 'delvip']:
                        send_message(peer_id, "❌ Вы не можете выдать доступ к этой команде!", reply_to)
                        return
                    # Нельзя выдавать доступ самому себе
                    if target_id == from_id:
                        send_message(peer_id, "❌ Нельзя выдать доступ самому себе!", reply_to)
                        return
                
                sql.execute("CREATE TABLE IF NOT EXISTS allowed_commands (user_id INTEGER, command TEXT)")
                
                # Используем has_command_access для всех команд
                already_has_access = has_command_access(target_id, command_to_allow)
                
                if already_has_access:
                    message = f"ℹ️ Пользователь уже имеет доступ к этой команде!\n"
                    message += f"👤 Пользователь: {get_mention(target_id, chat_id)}\n"
                    message += f"📝 Команда: /{command_to_allow}"
                else:
                    sql.execute("INSERT INTO allowed_commands VALUES (?, ?)", (target_id, command_to_allow))
                    database.commit()
                    message = f"✅ Доступ к команде выдан!\n"
                    message += f"👤 Пользователь: {get_mention(target_id, chat_id)}\n"
                    message += f"📝 Команда: /{command_to_allow}"
                
                send_message(peer_id, message, reply_to)
            
            # Команда givebot
            elif cmd in ['givebot']:
                if not has_command_access(from_id, 'givebot'):
                    send_message(peer_id, "❌ Недостаточно прав!", reply_to)
                    returnс
                
                target_id = get_user_from_reply_or_mention(event.obj, args, 1)
                if not target_id:
                    send_message(peer_id, "❌ Укажите пользователя!", reply_to)
                    return
                
                # Добавляем в таблицу ботов
                sql.execute("CREATE TABLE IF NOT EXISTS bot_users (user_id INTEGER PRIMARY KEY, original_role INTEGER DEFAULT 0)")
                current_role = get_role(target_id, chat_id) if chat_id > 0 else 0
                sql.execute("INSERT OR REPLACE INTO bot_users VALUES (?, ?)", (target_id, current_role))
                
                # Выдаем роль выше владельца
                if chat_id > 0:
                    set_role(target_id, chat_id, 1500)
                
                # Запрещаем все команды
                all_commands = ['kick', 'ban', 'warn', 'mute', 'roles', 'help', 'stats', 'bonus', 'transfer', 'shop', 'duel']
                for cmd_name in all_commands:
                    sql.execute("INSERT OR IGNORE INTO restricted_commands VALUES (?, ?)", (target_id, cmd_name))
                
                database.commit()
                send_message(peer_id, f"🤖 {get_mention(target_id, chat_id)} получил статус БОТА!", reply_to)
            
            # Команда delbot
            elif cmd in ['delbot']:
                if not has_command_access(from_id, 'delbot'):
                    send_message(peer_id, "❌ Недостаточно прав!", reply_to)
                    return
                
                target_id = get_user_from_reply_or_mention(event.obj, args, 1)
                if not target_id:
                    send_message(peer_id, "❌ Укажите пользователя!", reply_to)
                    return
                
                # Получаем оригинальную роль
                sql.execute("SELECT original_role FROM bot_users WHERE user_id = ?", (target_id,))
                original = sql.fetchone()
                original_role = original[0] if original else 0
                
                # Возвращаем роль
                if chat_id > 0:
                    set_role(target_id, chat_id, original_role)
                
                # Удаляем из ботов
                sql.execute("DELETE FROM bot_users WHERE user_id = ?", (target_id,))
                database.commit()
                
                send_message(peer_id, f"👤 {get_mention(target_id, chat_id)} больше не БОТ!", reply_to)
            
            # Команда asu_giveallcmd
            elif cmd in ['asu_giveallcmd']:
                if not has_command_access(from_id, 'asu_giveallcmd'):
                    send_message(peer_id, "❌ Недостаточно прав!", reply_to)
                    return
                
                target_id = get_user_from_reply_or_mention(event.obj, args, 1)
                if not target_id:
                    send_message(peer_id, "❌ Укажите пользователя!", reply_to)
                    return
                
                # Выдаем доступ ко всем командам владельца
                owner_commands = ['bot_info', 'info', 'dell_chat_db', 'asu_cmd', 'asu_delcmd', 'asu_cmdinfo', 'givemoney', 'delmoney', 'givevip', 'delvip', 'addmoder', 'addadmin', 'addcurator', 'start_bot', 'stop_bot', 'off_bot', 'notif', 'addma', 'givebot', 'delbot', 'asu_giveallcmd', 'asu_delallcmd']
                for cmd_name in owner_commands:
                    sql.execute("INSERT OR IGNORE INTO allowed_commands VALUES (?, ?)", (target_id, cmd_name))
                
                # Удаляем все ограничения
                sql.execute("DELETE FROM restricted_commands WHERE user_id = ?", (target_id,))
                database.commit()
                
                send_message(peer_id, f"✅ {get_mention(target_id, chat_id)} получил доступ ко всем командам!", reply_to)
            
            # Команда asu_delallcmd
            elif cmd in ['asu_delallcmd']:
                if not has_command_access(from_id, 'asu_delallcmd'):
                    send_message(peer_id, "❌ Недостаточно прав!", reply_to)
                    return
                
                target_id = get_user_from_reply_or_mention(event.obj, args, 1)
                if not target_id:
                    send_message(peer_id, "❌ Укажите пользователя!", reply_to)
                    return
                
                # Удаляем все разрешения
                sql.execute("DELETE FROM allowed_commands WHERE user_id = ?", (target_id,))
                database.commit()
                
                send_message(peer_id, f"❌ У {get_mention(target_id, chat_id)} удален доступ ко всем командам!", reply_to)
            
            # Команда give_mes
            elif cmd in ['give_mes']:
                if not has_command_access(from_id, 'give_mes'):
                    send_message(peer_id, "❌ Недостаточно прав!", reply_to)
                    return
                
                if chat_id == 0 or not check_chat(chat_id):
                    return
                
                target_id = get_user_from_reply_or_mention(event.obj, args, 1)
                if not target_id:
                    send_message(peer_id, "❌ Укажите пользователя!", reply_to)
                    return
                
                # Определяем количество сообщений
                if 'reply_message' in event.obj.message:
                    if len(args) < 2:
                        send_message(peer_id, "❌ Укажите количество сообщений!\nПример: /give_mes 1600", reply_to)
                        return
                    try:
                        messages_count = int(args[1])
                    except:
                        send_message(peer_id, "❌ Укажите корректное количество!", reply_to)
                        return
                else:
                    if len(args) < 3:
                        send_message(peer_id, "❌ Укажите количество сообщений!\nПример: /give_mes @user 1600", reply_to)
                        return
                    try:
                        messages_count = int(args[2])
                    except:
                        send_message(peer_id, "❌ Укажите корректное количество!", reply_to)
                        return
                
                if messages_count < 0:
                    send_message(peer_id, "❌ Количество сообщений не может быть отрицательным!", reply_to)
                    return
                
                # Получаем текущее количество сообщений
                sql.execute(f"SELECT messages FROM user_stats_{chat_id} WHERE user_id = {target_id}")
                current = sql.fetchone()
                old_messages = current[0] if current else 0
                
                # Обновляем количество сообщений
                if current:
                    sql.execute(f"UPDATE user_stats_{chat_id} SET messages = ? WHERE user_id = ?", (messages_count, target_id))
                else:
                    sql.execute(f"INSERT INTO user_stats_{chat_id} VALUES (?, ?, 0, ?)", (target_id, int(time.time()), messages_count))
                
                database.commit()
                
                target_nick = get_nick(target_id, chat_id) or get_user_info(target_id)
                message = f"💬 Количество сообщений установлено!\n"
                message += f"👤 Пользователь: {get_mention(target_id, chat_id)}\n"
                message += f"🔄 Было: {old_messages} сообщений\n"
                message += f"✅ Стало: {messages_count} сообщений"
                send_message(peer_id, message, reply_to)
            
            # Команда asu_delcmd (запрет команды)
            elif cmd in ['asu_delcmd', 'asu_dellcmd']:
                if not has_command_access(from_id, 'asu_delcmd'):
                    send_message(peer_id, "❌ Недостаточно прав! Команда доступна только владельцу бота!", reply_to)
                    return
                
                target_id = get_user_from_reply_or_mention(event.obj, args, 1)
                if not target_id:
                    send_message(peer_id, "❌ Укажите пользователя или ответьте на сообщение!", reply_to)
                    return
                
                # Определяем команду
                if 'reply_message' in event.obj.message:
                    if len(args) < 2:
                        send_message(peer_id, "❌ Укажите команду!\nПример: /asu_delcmd kick", reply_to)
                        return
                    command_to_restrict = args[1].lower().replace('/', '')
                else:
                    if len(args) < 3:
                        send_message(peer_id, "❌ Укажите команду!\nПример: /asu_delcmd @user kick", reply_to)
                        return
                    command_to_restrict = args[2].lower().replace('/', '')
                
                sql.execute("CREATE TABLE IF NOT EXISTS restricted_commands (user_id INTEGER, command TEXT)")
                
                # Используем has_command_access для всех команд
                owner_commands = ['bot_info', 'info', 'dell_chat_db', 'asu_cmd', 'asu_delcmd', 'asu_cmdinfo', 'givemoney', 'delmoney', 'givevip', 'delvip', 'addmoder', 'addadmin', 'addcurator', 'start_bot', 'stop_bot', 'off_bot', 'notif', 'addma', 'givebot', 'delbot', 'asu_giveallcmd', 'asu_delallcmd', 'give_mes']
                already_restricted = not has_command_access(target_id, command_to_restrict)
                
                if already_restricted:
                    message = f"ℹ️ Команда уже запрещена!\n"
                    message += f"👤 Пользователь: {get_mention(target_id, chat_id)}\n"
                    message += f"📝 Команда: /{command_to_restrict}"
                else:
                    if command_to_restrict in owner_commands:
                        # Для команд владельца удаляем из allowed_commands
                        sql.execute("DELETE FROM allowed_commands WHERE user_id = ? AND command = ?", (target_id, command_to_restrict))
                    else:
                        # Для обычных команд добавляем в restricted_commands
                        sql.execute("INSERT INTO restricted_commands VALUES (?, ?)", (target_id, command_to_restrict))
                    database.commit()
                    message = f"❌ Команда запрещена!\n"
                    message += f"👤 Пользователь: {get_mention(target_id, chat_id)}\n"
                    message += f"📝 Команда: /{command_to_restrict}"
                
                send_message(peer_id, message, reply_to)
            
            # Команда asu_cmdinfo (просмотр разрешений)
            elif cmd in ['asu_cmdinfo']:
                # Проверяем доступ
                if from_id != BOT_OWNER_ID and not has_command_access(from_id, 'asu_cmdinfo'):
                    send_message(peer_id, f"❌ Извините, у вас нет доступа к этой команде!\n\n🔧 Если это ошибка, обратитесь к Владелец {get_mention(BOT_OWNER_ID, chat_id)}!", reply_to)
                    return
                
                target_id = get_user_from_reply_or_mention(event.obj, args, 1)
                if not target_id:
                    target_id = from_id
                
                # Получаем список всех команд
                all_commands = [
                    'help', 'start', 'stats', 'id', 'bonus', 'transfer', 'givemoney', 'delmoney', 'givevip', 'delvip', 'kick', 'warn', 'unwarn',
                    'mute', 'unmute', 'ban', 'unban', 'nick', 'getnick', 'staff', 'warnlist', 'online', 'getban', 'shop',
                    'addmoder', 'addadmin', 'removerole', 'banlist', 'roles', 'games', 'ping', 'mutelist',
                    'gmute', 'gban', 'gwarn', 'gkick', 'grole', 'gnick', 'gunmute', 'gunwarn', 'gunban', 'gdelnick', 'grnick', 'grr',
                    'pullinfo', 'pull', 'transfervl', 'bot_info', 'info', 'dell_chat_db', 'asu_cmd', 'asu_delcmd', 'cmd_info',
                    'off_bot', 'start_bot', 'stop_bot', 'notif'
                ]
                
                # Получаем разрешенные команды
                sql.execute("CREATE TABLE IF NOT EXISTS allowed_commands (user_id INTEGER, command TEXT)")
                sql.execute("SELECT command FROM allowed_commands WHERE user_id = ?", (target_id,))
                allowed = [row[0] for row in sql.fetchall()]
                
                info_text = f"📊 Разрешения команд для {get_mention(target_id, chat_id)}\n\n"
                
                # Получаем запрещенные команды
                sql.execute("CREATE TABLE IF NOT EXISTS restricted_commands (user_id INTEGER, command TEXT)")
                sql.execute("SELECT command FROM restricted_commands WHERE user_id = ?", (target_id,))
                restricted = [row[0] for row in sql.fetchall()]
                
                owner_commands = ['bot_info', 'info', 'dell_chat_db', 'asu_cmd', 'asu_delcmd', 'asu_cmdinfo', 'givemoney', 'delmoney', 'givevip', 'delvip', 'addmoder', 'addadmin', 'addcurator', 'start_bot', 'stop_bot', 'off_bot', 'notif', 'addma', 'givebot', 'delbot', 'asu_giveallcmd', 'asu_delallcmd', 'give_mes']
                
                for command in sorted(all_commands):
                    if target_id == BOT_OWNER_ID:
                        status = "✅ есть доступ"
                    else:
                        # Используем ту же логику, что и в has_command_access
                        if has_command_access(target_id, command):
                            status = "✅ есть доступ"
                        else:
                            status = "❌ нету доступа"
                    info_text += f"/{command} - {status}\n"
                
                send_message(peer_id, info_text, reply_to)
            
            # Команда bot_info
            elif cmd in ['bot_info']:
                if not has_command_access(from_id, 'bot_info'):
                    send_message(peer_id, f"❌ Извините, у вас нет доступа к этой команде!\n\n🔧 Если это ошибка, обратитесь к Владелец {get_mention(BOT_OWNER_ID, chat_id)}!", reply_to)
                    return
                
                # Отправляем сообщение о загрузке
                loading_msg_id = vk.messages.send(peer_id=peer_id, message="⏳ Подождите идет загрузка....", random_id=random.randint(1, 1000000))
                
                try:
                    # Получаем все чаты
                    sql.execute("SELECT chat_id, peer_id, pull_id FROM chats")
                    all_chats = sql.fetchall()
                    
                    # Разделяем на объединенные и необъединенные
                    united_chats = {}
                    single_chats = []
                    
                    for chat_id, peer_id, pull_id in all_chats:
                        if pull_id:
                            if pull_id not in united_chats:
                                united_chats[pull_id] = []
                            united_chats[pull_id].append((chat_id, peer_id))
                        else:
                            single_chats.append((chat_id, peer_id))
                    
                    # Получаем названия чатов
                    def get_chat_title(peer_id):
                        try:
                            conv = vk.messages.getConversationsById(peer_ids=peer_id)
                            return conv['items'][0]['chat_settings']['title']
                        except:
                            return f"Чат {peer_id - 2000000000}"
                    
                    # Подсчитываем деньги в чате (исключая владельца бота)
                    def get_chat_money(chat_id):
                        try:
                            sql.execute(f"CREATE TABLE IF NOT EXISTS bonuses_{chat_id} (user_id INTEGER, last_bonus INTEGER, streak INTEGER, coins INTEGER)")
                            
                            # Получаем всех пользователей с монетами
                            sql.execute(f"SELECT user_id, coins FROM bonuses_{chat_id} WHERE user_id != {BOT_OWNER_ID}")
                            users_with_coins = sql.fetchall()
                            
                            total_coins = 0
                            peer_id = chat_id + 2000000000
                            
                            # Проверяем каждого пользователя
                            for user_id, coins in users_with_coins:
                                try:
                                    # Проверяем есть ли пользователь в чате
                                    members = vk.messages.getConversationMembers(peer_id=peer_id)
                                    user_in_chat = any(m['member_id'] == user_id for m in members['items'])
                                    
                                    # Проверяем есть ли только бот в чате
                                    human_members = [m['member_id'] for m in members['items'] if m['member_id'] > 0]
                                    if len(human_members) == 0:
                                        # Удаляем чат из БД если только бот
                                        sql.execute(f"DELETE FROM chats WHERE chat_id = {chat_id}")
                                        return 0
                                    
                                    if user_in_chat:
                                        total_coins += coins
                                    else:
                                        # Проверяем забанен ли пользователь
                                        sql.execute(f"SELECT user_id FROM bans_{chat_id} WHERE user_id = {user_id}")
                                        is_banned = sql.fetchone() is not None
                                        
                                        if not is_banned:
                                            # Сохраняем монеты в глобальную таблицу
                                            sql.execute(f"INSERT OR REPLACE INTO global_coins (user_id, coins) VALUES ({user_id}, {coins})")
                                            # Удаляем пользователя из всех таблиц кроме банов
                                            sql.execute(f"DELETE FROM bonuses_{chat_id} WHERE user_id = {user_id}")
                                            sql.execute(f"DELETE FROM nicks_{chat_id} WHERE user_id = {user_id}")
                                            sql.execute(f"DELETE FROM warns_{chat_id} WHERE user_id = {user_id}")
                                            sql.execute(f"DELETE FROM permissions_{chat_id} WHERE user_id = {user_id}")
                                            sql.execute(f"DELETE FROM marriages_{chat_id} WHERE user1 = {user_id} OR user2 = {user_id}")
                                            sql.execute(f"DELETE FROM user_stats_{chat_id} WHERE user_id = {user_id}")
                                            sql.execute(f"DELETE FROM mutes_{chat_id} WHERE user_id = {user_id}")
                                        else:
                                            # Забаненный пользователь - считаем его деньги
                                            total_coins += coins
                                except:
                                    # Если ошибка при проверке - считаем деньги
                                    total_coins += coins
                            
                            database.commit()
                            return total_coins
                        except:
                            return 0
                    
                    # Формируем ответ
                    info_text = "📊 Информация бота\n"
                    info_text += f"🔗 Объединенных чатов: {len(united_chats)}\n"
                    info_text += f"💬 Необъединенных чатов: {len(single_chats)}\n\n"
                    
                    if united_chats:
                        info_text += "🔗 Объединенные чаты:\n"
                        for pull_id, chats in united_chats.items():
                            total_money = sum(get_chat_money(chat_id) for chat_id, _ in chats)
                            info_text += f"🆔 {pull_id} -- {total_money} монет\n"
                            for chat_id, peer_id in chats:
                                title = get_chat_title(peer_id)
                                info_text += f"  • id {chat_id} {title}\n"
                        info_text += "\n"
                    
                    if single_chats:
                        info_text += "💬 Необъединенные чаты:\n"
                        for chat_id, peer_id in single_chats:
                            title = get_chat_title(peer_id)
                            money = get_chat_money(chat_id)
                            info_text += f"id {chat_id} {title} - {money} монет\n"
                    
                    # Редактируем сообщение
                    try:
                        vk.messages.edit(peer_id=peer_id, message=info_text, message_id=loading_msg_id)
                    except:
                        send_message(peer_id, info_text)
                except Exception as e:
                    try:
                        vk.messages.edit(peer_id=peer_id, message=f"❌ Ошибка получения информации: {str(e)}", message_id=loading_msg_id)
                    except:
                        send_message(peer_id, f"❌ Ошибка получения информации: {str(e)}")
            
            # Команда dell_chat_db
            elif cmd in ['dell_chat_db']:
                if from_id != BOT_OWNER_ID:
                    send_message(peer_id, "❌ Недостаточно прав! Команда доступна только владельцу бота!", reply_to)
                    return
                
                if len(args) < 2:
                    send_message(peer_id, "❌ Укажите ID чата!\n📝 Пример: /dell_chat_db 123", reply_to)
                    return
                
                try:
                    target_chat_id = int(args[1])
                except:
                    send_message(peer_id, "❌ Неверный ID чата!", reply_to)
                    return
                
                # Проверяем существование чата
                sql.execute("SELECT peer_id FROM chats WHERE chat_id = ?", (target_chat_id,))
                chat_data = sql.fetchone()
                if not chat_data:
                    send_message(peer_id, f"❌ Чат с ID {target_chat_id} не найден в базе данных!", reply_to)
                    return
                
                target_peer_id = chat_data[0]
                
                # Удаляем чат из БД
                try:
                    tables_to_drop = [
                        f"permissions_{target_chat_id}", f"nicks_{target_chat_id}", f"warns_{target_chat_id}",
                        f"bans_{target_chat_id}", f"games_{target_chat_id}", f"bonuses_{target_chat_id}",
                        f"marriages_{target_chat_id}", f"user_stats_{target_chat_id}", f"mutes_{target_chat_id}",
                        f"kicked_{target_chat_id}", f"marriage_proposals_{target_chat_id}", f"transfer_pending_{target_chat_id}"
                    ]
                    for table in tables_to_drop:
                        try:
                            sql.execute(f"DROP TABLE IF EXISTS {table}")
                        except:
                            pass
                    
                    sql.execute(f"DELETE FROM chats WHERE chat_id = {target_chat_id}")
                    database.commit()
                    
                    # Сообщение владельцу
                    send_message(peer_id, f"✅ Успешно! Чат с ID {target_chat_id} удален из базы данных! 🗑️", reply_to)
                    
                    # Сообщение в удаленный чат
                    notification_msg = f"🚨 Ваш чат был удален из базы данных!\n\n"
                    notification_msg += f"❓ Если это была ошибка, напишите Владелец {get_mention(BOT_OWNER_ID, chat_id)}\n\n"
                    notification_msg += f"🔄 Для повторной активации используйте команду /start"
                    
                    try:
                        send_message(target_peer_id, notification_msg)
                    except:
                        pass
                        
                except Exception as e:
                    send_message(peer_id, f"❌ Ошибка удаления: {str(e)}", reply_to)
            
            # Команда info
            elif cmd in ['info']:
                if not has_command_access(from_id, 'info'):
                    send_message(peer_id, f"❌ Извините, у вас нет доступа к этой команде!\n\n🔧 Если это ошибка, обратитесь к Владелец {get_mention(BOT_OWNER_ID, chat_id)}!", reply_to)
                    return
                
                if len(args) < 2:
                    send_message(peer_id, "❌ Укажите ID чата!\nПример: /info 123", reply_to)
                    return
                
                try:
                    target_chat_id = int(args[1])
                except:
                    send_message(peer_id, "❌ Неверный ID чата!", reply_to)
                    return
                
                # Проверяем существование чата
                sql.execute("SELECT peer_id FROM chats WHERE chat_id = ?", (target_chat_id,))
                chat_data = sql.fetchone()
                if not chat_data:
                    send_message(peer_id, f"❌ Чат с ID {target_chat_id} не найден в базе данных!", reply_to)
                    return
                
                target_peer_id = chat_data[0]
                
                try:
                    # Получаем информацию о чате и участниках
                    try:
                        conv = vk.messages.getConversationsById(peer_ids=target_peer_id)
                        chat_title = conv['items'][0]['chat_settings']['title'] if conv['items'] else f"Чат {target_chat_id}"
                    except:
                        chat_title = f"Чат {target_chat_id}"
                    
                    members = vk.messages.getConversationMembers(peer_id=target_peer_id)
                    user_ids = [m['member_id'] for m in members['items'] if m['member_id'] > 0]
                    
                    info_text = f"📋 Информация о чате id {target_chat_id}\n"
                    info_text += f"📝 Название: {chat_title}\n"
                    info_text += f"👥 Количество пользователей: {len(user_ids)}\n\n"
                    info_text += "👤 Никнеймы пользователей:\n"
                    
                    # Получаем информацию о пользователях порциями
                    for i in range(0, len(user_ids), 100):
                        batch = user_ids[i:i+100]
                        try:
                            users_info = vk.users.get(user_ids=batch)
                            for user in users_info:
                                user_id = user['id']
                                name = f"{user['first_name']} {user['last_name']}"
                                # Получаем монеты пользователя
                                try:
                                    sql.execute(f"SELECT coins FROM bonuses_{target_chat_id} WHERE user_id = {user_id}")
                                    coins_result = sql.fetchone()
                                    coins = coins_result[0] if coins_result else 0
                                except:
                                    coins = 0
                                info_text += f"• {get_mention(user_id, chat_id)} -- {coins} монет\n"
                        except:
                            # Если не удалось получить информацию о пользователях
                            for user_id in batch:
                                try:
                                    sql.execute(f"SELECT coins FROM bonuses_{target_chat_id} WHERE user_id = {user_id}")
                                    coins_result = sql.fetchone()
                                    coins = coins_result[0] if coins_result else 0
                                except:
                                    coins = 0
                                info_text += f"• {get_mention(user_id, chat_id)} -- {coins} монет\n"
                    
                    # Получаем ссылку-приглашение
                    try:
                        invite_link = vk.messages.getInviteLink(peer_id=target_peer_id)['link']
                        info_text += f"\n🔗 Ссылка на вступление в данный чат: {invite_link}"
                    except:
                        info_text += f"\n🔗 Ссылка на вступление: Не удалось получить (нужны права админа)"
                    
                    send_message(peer_id, info_text, reply_to)
                except Exception as e:
                    send_message(peer_id, f"❌ Ошибка получения информации о чате: {str(e)}", reply_to)
            
            # Команда transfervl
            elif cmd in ['transfervl', 'передать']:
                if chat_id == 0 or not check_chat(chat_id):
                    return
                    
                # Передавать права главного владельца может только главный владелец (в таблице chats)
                sql.execute(f"SELECT owner_id FROM chats WHERE chat_id = {chat_id}")
                main_owner = sql.fetchone()[0]
                
                if from_id != main_owner:
                    send_message(peer_id, "❌ Передавать права главного владельца может только главный владелец!", reply_to)
                    return
                
                target_id = get_user_from_reply_or_mention(event.obj, args, 1)
                if not target_id:
                    send_message(peer_id, "Укажите пользователя для передачи прав!", reply_to)
                    return
                
                if target_id == from_id:
                    send_message(peer_id, "❌ Нельзя передать права самому себе!", reply_to)
                    return
                
                # Сохраняем информацию о передаче
                sql.execute(f"CREATE TABLE IF NOT EXISTS transfer_pending_{chat_id} (from_user INTEGER, to_user INTEGER, timestamp INTEGER)")
                sql.execute(f"DELETE FROM transfer_pending_{chat_id} WHERE from_user = {from_id}")
                sql.execute(f"INSERT INTO transfer_pending_{chat_id} VALUES (?, ?, ?)", (from_id, target_id, int(time.time())))
                database.commit()
                
                message = f"👑 Вы точно хотите передать права главного владельца пользователю:\n"
                message += f"{get_mention(target_id, chat_id)}\n\n"
                message += f"💬 Напишите в чат: /yes | /no"
                
                send_message(peer_id, message, reply_to)
            
            else:
                if chat_id > 0 and check_chat(chat_id):
                    # Список всех команд
                    all_commands = [
                        'help', 'помощь', 'start', 'старт', 'stats', 'стата', 'id', 'ид',
                        'bonus', 'бонус', 'transfer', 'перевод', 'givemoney', 'выдатьденьги', 'delmoney', 'удалитьденьги', 
                        'givevip', 'выдатьвип', 'delvip', 'удалитьвип', 'брак', 'marry', 'duel', 'дуэль',
                        'kick', 'кик', 'warn', 'варн', 'пред', 'unwarn', 'унварн', 'снятьпред',
                        'mute', 'мут', 'unmute', 'унмут', 'размут', 'ник', 'nick', 'setnick',
                        'getnick', 'gnick', 'понику', 'staff', 'стафф', 'warnlist', 'варнлист',
                        'online', 'онлайн', 'getban', 'гетбан', 'shop', 'магазин',
                        'ban', 'бан', 'unban', 'унбан', 'разбан', 'addmoder', 'moder', 'модер',
                        'removerole', 'rrole', 'снять', 'banlist', 'банлист',
                        'тишина', 'quiet', 'gmute', 'гмут', 'gban', 'гбан', 'gwarn', 'гварн',
                        'gkick', 'гкик', 'grole', 'гроль', 'gnick', 'гник', 'gdelnick', 'гделник',
                        'gunmute', 'гунмут', 'gunwarn', 'гунварн', 'gunban', 'гразбан', 'grnick', 'грник', 'grr', 'грр',
                        'addadmin', 'admin', 'админ', 'pullinfo', 'pull_info', 'delpull', 'removepull', 'пулинфо', 'bot_info', 'info',
                        'roles', 'роль', 'role', 'pull', 'пул', 'transfervl', 'передать', 'asu_cmd', 'asu_delcmd', 'mutelist', 'мутлист',
                        'ping', 'пинг', 'games', 'игры', 'notif', 'уведомление'
                    ]
                    
                    # Ищем похожие команды
                    from difflib import get_close_matches
                    similar = get_close_matches(cmd, all_commands, n=3, cutoff=0.6)
                    
                    msg = f"❓ Неизвестная команда: /{cmd}\n"
                    if similar:
                        msg += f"\n💡 Возможно вы имели ввиду:\n"
                        for s in similar:
                            msg += f"• /{s}\n"
                    else:
                        msg += "\nИспользуйте /help для списка команд"
                    
                    send_message(peer_id, msg, reply_to)
        
        # Проверяем мут пользователя
        if chat_id > 0 and check_chat(chat_id) and is_muted(from_id, chat_id):
            try:
                vk.messages.delete(peer_id=peer_id, delete_for_all=1, cmids=event.obj.message['conversation_message_id'])
            except:
                pass
    except Exception as e:
        print(f"Ошибка обработки события: {e}")

if __name__ == "__main__":
    main_loop()