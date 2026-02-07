#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скрипт мониторинга бота
"""

import time
import json
import sqlite3
from datetime import datetime

def check_bot_status():
    """Проверяет статус бота"""
    try:
        # Проверяем конфигурацию
        with open("config.json", "r") as f:
            config = json.load(f)
        
        print("✅ Конфигурация загружена")
        
        # Проверяем базу данных
        database = sqlite3.connect('database.db', check_same_thread=False)
        sql = database.cursor()
        
        sql.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = sql.fetchall()
        print(f"✅ База данных: {len(tables)} таблиц")
        
        # Проверяем количество чатов
        sql.execute("SELECT COUNT(*) FROM chats")
        chat_count = sql.fetchone()[0]
        print(f"📊 Активных чатов: {chat_count}")
        
        # Проверяем последнюю активность (если есть таблица логов)
        try:
            sql.execute("SELECT MAX(date) FROM warns_1")  # Пример проверки активности
            last_activity = sql.fetchone()[0]
            if last_activity:
                last_time = datetime.fromtimestamp(last_activity)
                print(f"🕒 Последняя активность: {last_time.strftime('%d.%m.%Y %H:%M:%S')}")
        except:
            print("ℹ️ Данные о последней активности недоступны")
        
        database.close()
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка проверки статуса: {e}")
        return False

def main():
    """Основная функция мониторинга"""
    print("🔍 Мониторинг бота KING MANAGER")
    print("=" * 40)
    
    while True:
        try:
            current_time = datetime.now().strftime('%H:%M:%S')
            print(f"\n[{current_time}] Проверка статуса...")
            
            if check_bot_status():
                print("✅ Бот работает нормально")
            else:
                print("⚠️ Обнаружены проблемы")
            
            print("-" * 40)
            time.sleep(30)  # Проверка каждые 30 секунд
            
        except KeyboardInterrupt:
            print("\n👋 Мониторинг остановлен")
            break
        except Exception as e:
            print(f"❌ Ошибка мониторинга: {e}")
            time.sleep(10)

if __name__ == "__main__":
    main()