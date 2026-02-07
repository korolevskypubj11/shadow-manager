import sqlite3
import os

def fix_database():
    if not os.path.exists('database.db'):
        print("База данных не найдена!")
        return
    
    database = sqlite3.connect('database.db')
    sql = database.cursor()
    
    print("Проверка и исправление структуры базы данных...")
    
    # Получаем все таблицы
    sql.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = sql.fetchall()
    
    for (table_name,) in tables:
        print(f"Проверяем таблицу: {table_name}")
        
        # Проверяем структуру таблиц банов
        if table_name.startswith('bans_'):
            sql.execute(f"PRAGMA table_info({table_name})")
            columns = sql.fetchall()
            column_names = [col[1] for col in columns]
            
            if 'ban_until' not in column_names:
                print(f"  Добавляем колонку ban_until в {table_name}")
                sql.execute(f"ALTER TABLE {table_name} ADD COLUMN ban_until INTEGER DEFAULT 0")
            
            # Если есть лишняя колонка, пересоздаем таблицу
            if len(columns) > 5:
                print(f"  Пересоздаем таблицу {table_name}")
                sql.execute(f"CREATE TABLE {table_name}_new (user_id INTEGER, moder INTEGER, reason TEXT, date INTEGER, ban_until INTEGER DEFAULT 0)")
                sql.execute(f"INSERT INTO {table_name}_new SELECT user_id, moder, reason, date, ban_until FROM {table_name}")
                sql.execute(f"DROP TABLE {table_name}")
                sql.execute(f"ALTER TABLE {table_name}_new RENAME TO {table_name}")
        
        # Проверяем таблицы мутов
        elif table_name.startswith('mutes_'):
            sql.execute(f"PRAGMA table_info({table_name})")
            columns = sql.fetchall()
            column_names = [col[1] for col in columns]
            
            if 'end_time' not in column_names:
                print(f"  Добавляем колонку end_time в {table_name}")
                sql.execute(f"ALTER TABLE {table_name} ADD COLUMN end_time INTEGER DEFAULT 0")
        
        # Проверяем таблицы статистики
        elif table_name.startswith('user_stats_'):
            sql.execute(f"PRAGMA table_info({table_name})")
            columns = sql.fetchall()
            column_names = [col[1] for col in columns]
            
            if 'messages' not in column_names:
                print(f"  Добавляем колонку messages в {table_name}")
                sql.execute(f"ALTER TABLE {table_name} ADD COLUMN messages INTEGER DEFAULT 0")
    
    database.commit()
    database.close()
    print("Проверка завершена!")

if __name__ == "__main__":
    fix_database()