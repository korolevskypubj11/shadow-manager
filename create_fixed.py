# Читаем резервную копию до строки с def main_loop
with open('main_full_backup.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Находим где начинается def main_loop
main_loop_line = None
for i, line in enumerate(lines):
    if line.strip().startswith('def main_loop():'):
        main_loop_line = i
        break

# Берем все до main_loop
result = lines[:main_loop_line] if main_loop_line else lines

# Добавляем правильную функцию main_loop
result.append('\ndef main_loop():\n')
result.append('    longpoll = VkBotLongPoll(vk_session, group_id, wait=25)\n')
result.append('    while True:\n')
result.append('        try:\n')

# Копируем весь код обработки событий из резервной копии
# Ищем начало обработки
event_start = None
for i, line in enumerate(lines):
    if 'for event in longpoll.listen():' in line:
        event_start = i + 1  # Начинаем со следующей строки
        break

# Ищем конец (строку с except Exception)
event_end = None
if event_start:
    for i in range(event_start, len(lines)):
        if lines[i].strip().startswith('except Exception as e:'):
            # Проверяем что это именно наш except
            if i + 1 < len(lines) and 'подключения' in lines[i+1]:
                event_end = i
                break

# Копируем код с правильными отступами
if event_start and event_end:
    for i in range(event_start, event_end):
        line = lines[i]
        # Добавляем 3 уровня отступа (12 пробелов)
        if line.strip():
            result.append('            ' + line.lstrip())
        else:
            result.append('\n')

# Добавляем обработку ошибок
result.append('        except Exception as e:\n')
result.append('            print(f"Ошибка: {e}")\n')
result.append('            print("Переподключение через 5 секунд...")\n')
result.append('            time.sleep(5)\n')
result.append('            try:\n')
result.append('                longpoll = VkBotLongPoll(vk_session, group_id, wait=25)\n')
result.append('                print("Переподключение успешно!")\n')
result.append('            except:\n')
result.append('                print("Повтор через 10 секунд...")\n')
result.append('                time.sleep(10)\n')
result.append('\n')
result.append('if __name__ == "__main__":\n')
result.append('    main_loop()\n')

# Записываем
with open('main_full.py', 'w', encoding='utf-8') as f:
    f.writelines(result)

print(f"OK: {len(result)} lines")
