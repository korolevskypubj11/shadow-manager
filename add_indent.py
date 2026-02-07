with open('main_full.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Находим строку с if event.type
start_line = None
for i, line in enumerate(lines):
    if 'if event.type == VkBotEventType.MESSAGE_NEW:' in line:
        start_line = i + 1
        break

# Находим ПОСЛЕДНИЙ except Exception (это наш обработчик ошибок подключения)
end_line = None
if start_line:
    for i in range(len(lines)-1, start_line, -1):
        if 'except Exception as e:' in lines[i] and i > 2000:
            end_line = i
            break

# Добавляем 4 пробела ко всем строкам между start и end
if start_line and end_line:
    for i in range(start_line, end_line):
        if lines[i].strip():  # Если строка не пустая
            lines[i] = '    ' + lines[i]

    with open('main_full.py', 'w', encoding='utf-8') as f:
        f.writelines(lines)
    
    print(f"OK: added indent to {end_line - start_line} lines")
else:
    print("ERROR")
