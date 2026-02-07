import sqlite3
import os

def clean_durov_from_db():
    if not os.path.exists('database.db'):
        print("База данных не найдена!")
        return
    
    database = sqlite3.connect('database.db')
    sql = database.cursor()
    
    durov_id = 41858482
    print(f"Удаляем Павла Дурова (ID: {durov_id}) из всех таблиц...")
    
    # Получаем все таблицы
    sql.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = sql.fetchall()
    
    removed_count = 0
    
    for (table_name,) in tables:
        try:
            # Проверяем есть ли колонка user_id
            sql.execute(f"PRAGMA table_info({table_name})")
            columns = sql.fetchall()
            column_names = [col[1] for col in columns]
            
            if 'user_id' in column_names:
                # Проверяем есть ли Дуров в таблице
                sql.execute(f"SELECT COUNT(*) FROM {table_name} WHERE user_id = ?", (durov_id,))
                count = sql.fetchone()[0]
                
                if count > 0:
                    # Удаляем записи
                    sql.execute(f"DELETE FROM {table_name} WHERE user_id = ?", (durov_id,))
                    print(f"  Удалено {count} записей из {table_name}")
                    removed_count += count
        except Exception as e:
            print(f"  Ошибка в таблице {table_name}: {e}")
    
    database.commit()
    database.close()
    
    print(f"Всего удалено {removed_count} записей Павла Дурова")
    print("Очистка завершена!")

if __name__ == "__main__":
    clean_durov_from_db()