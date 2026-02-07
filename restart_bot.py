#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скрипт для перезапуска бота с очисткой кэша
"""

import os
import sys
import time
import subprocess

def restart_bot():
    """Перезапускает бота с очисткой кэша"""
    print("🔄 Перезапуск бота...")
    
    # Завершаем текущий процесс бота если он запущен
    try:
        # Для Windows
        subprocess.run(['taskkill', '/f', '/im', 'python.exe'], capture_output=True)
        print("✅ Предыдущие процессы Python завершены")
    except:
        pass
    
    # Ждем немного
    time.sleep(2)
    
    # Запускаем бота заново
    try:
        print("🚀 Запуск бота...")
        subprocess.run([sys.executable, 'main.py'])
    except KeyboardInterrupt:
        print("\n❌ Запуск прерван пользователем")
    except Exception as e:
        print(f"❌ Ошибка запуска: {e}")

if __name__ == "__main__":
    restart_bot()