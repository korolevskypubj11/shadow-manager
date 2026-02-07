# -*- coding: utf-8 -*-
"""
Конфигурация подключения для улучшения стабильности
"""

# Настройки подключения
CONNECTION_SETTINGS = {
    'wait_time': 15,  # Время ожидания LongPoll (уменьшено с 25)
    'max_reconnect_attempts': 5,  # Максимальное количество попыток переподключения
    'base_reconnect_delay': 10,  # Базовая задержка переподключения в секундах
    'max_reconnect_delay': 60,  # Максимальная задержка переподключения
    'message_cache_size': 1000,  # Размер кэша сообщений
    'command_cooldown': 2,  # Кулдаун команд в секундах
    'cache_cleanup_interval': 60,  # Интервал очистки кэша в секундах
}

# Настройки для обработки ошибок
ERROR_HANDLING = {
    'proxy_errors': ['ProxyError', 'RemoteDisconnected', 'ConnectionError'],
    'retry_errors': ['Max retries exceeded', 'Connection timeout', 'Read timeout'],
    'critical_errors': ['Invalid token', 'Access denied'],
}

# Настройки логирования
LOGGING_SETTINGS = {
    'log_commands_only': True,  # Логировать только команды, не обычные сообщения
    'log_duplicates': False,  # Не логировать дубликаты
    'log_reconnections': True,  # Логировать переподключения
    'verbose_errors': True,  # Подробные ошибки
}