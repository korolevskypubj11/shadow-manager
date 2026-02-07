import json
import random
import time

# Глобальная переменная для хранения текущей страницы и ID последнего сообщения
mtop_sessions = {}
mtop_timers = {}  # Хранение таймеров для каждого чата

def handle_mtop(chat_id, from_id, peer_id, page, sql, vk, send_message, get_user_info, get_nick):
    # Получаем список участников чата
    try:
        members = vk.messages.getConversationMembers(peer_id=peer_id)
        active_users = [m['member_id'] for m in members['items'] if m['member_id'] > 0]
    except:
        active_users = []
    """Команда /mtop - топ по сообщениям с пагинацией"""
    global mtop_sessions
    
    try:
        # Удаляем предыдущее сообщение топа если есть
        if chat_id in mtop_sessions and 'last_cmid' in mtop_sessions[chat_id]:
            try:
                vk.messages.delete(
                    cmids=mtop_sessions[chat_id]['last_cmid'],
                    delete_for_all=1,
                    peer_id=peer_id
                )
            except:
                pass
        
        sql.execute(f"SELECT user_id, messages FROM user_stats_{chat_id} WHERE messages > 0 ORDER BY messages DESC")
        all_stats = sql.fetchall()
        # Фильтруем только активных участников
        stats = [(uid, msgs) for uid, msgs in all_stats if uid in active_users]
        
        if not stats:
            send_message(peer_id, "📊 Статистика сообщений пуста")
            return
        
        per_page = 10
        total_pages = max(1, (len(stats) + per_page - 1) // per_page)
        page = max(1, min(page, total_pages))
        
        # Сохраняем текущую страницу
        if chat_id not in mtop_sessions:
            mtop_sessions[chat_id] = {}
        mtop_sessions[chat_id]['current_page'] = page
        mtop_sessions[chat_id]['total_pages'] = total_pages
        
        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page
        page_stats = stats[start_idx:end_idx]
        
        # Добавляем информацию о том кто выполнил команду
        executor_mention = f"[id{from_id}|{get_nick(from_id, chat_id) or get_user_info(from_id)}]"
        message = f"📊 Топ по сообщениям (страница {page}/{total_pages})\n"
        message += f"👤 Запросил: {executor_mention}\n\n"
        
        for i, (user_id, messages) in enumerate(page_stats, start_idx + 1):
            user_mention = f"[id{user_id}|{get_nick(user_id, chat_id) or get_user_info(user_id)}]"
            message += f"{i}. {user_mention} - {messages} сообщений\n"
        
        # Создаем клавиатуру только если больше одной страницы
        keyboard = None
        if total_pages > 1:
            buttons = []
            
            # Кнопка "Назад" если не первая страница
            if page > 1:
                buttons.append({
                    "action": {
                        "type": "text",
                        "label": "◀ Назад"
                    },
                    "color": "secondary"
                })
            
            # Кнопка "Вперед" если не последняя страница
            if page < total_pages:
                buttons.append({
                    "action": {
                        "type": "text", 
                        "label": "Вперед ▶"
                    },
                    "color": "secondary"
                })
            
            if buttons:
                keyboard = {
                    "one_time": False,
                    "buttons": [buttons]
                }
        
        # Отправляем сообщение
        try:
            random_id = int(time.time() * 1000) + random.randint(1, 1000)
            
            if keyboard:
                result = vk.messages.send(
                    peer_id=peer_id,
                    message=message,
                    keyboard=json.dumps(keyboard),
                    random_id=random_id
                )
                
                # Запускаем таймер на 40 секунд
                start_keyboard_timer(chat_id, peer_id, result, message, vk, 40)
            else:
                result = vk.messages.send(
                    peer_id=peer_id,
                    message=message,
                    random_id=random_id
                )
            
            # Получаем conversation_message_id через запрос последних сообщений
            try:
                messages = vk.messages.getHistory(peer_id=peer_id, count=1)
                if messages['items']:
                    mtop_sessions[chat_id]['last_cmid'] = messages['items'][0]['conversation_message_id']
            except:
                pass
            
        except Exception as e:
            send_message(peer_id, message)
            
    except Exception as e:
        send_message(peer_id, f"❌ Ошибка получения статистики: {str(e)}")

def handle_mtop_navigation(message_text, chat_id, from_id, peer_id, message_id, sql, vk, send_message, get_user_info, get_nick):
    """Обработка навигации по mtop через текстовые команды"""
    global mtop_sessions
    
    try:
        # Проверяем есть ли активная сессия mtop
        if chat_id not in mtop_sessions:
            return False
        
        # Удаляем сообщение пользователя с кнопкой
        try:
            vk.messages.delete(cmids=message_id, delete_for_all=1, peer_id=peer_id)
        except:
            pass
        
        # Получаем текущую страницу и общее количество
        current_page = mtop_sessions[chat_id].get('current_page', 1)
        total_pages = mtop_sessions[chat_id].get('total_pages', 1)
        
        # Определяем новую страницу
        new_page = current_page
        if "◀" in message_text or "назад" in message_text.lower():
            new_page = max(1, current_page - 1)
        elif "▶" in message_text or "вперед" in message_text.lower():
            new_page = min(current_page + 1, total_pages)
        else:
            return False
        
        # Если страница не изменилась, не делаем ничего
        if new_page == current_page:
            return True
        
        # Отправляем новую страницу (таймер сбросится автоматически)
        handle_mtop(chat_id, from_id, peer_id, new_page, sql, vk, send_message, get_user_info, get_nick)
        
        # Устанавливаем таймер на 40 секунд для навигации
        if chat_id in mtop_sessions and 'last_cmid' in mtop_sessions[chat_id]:
            start_keyboard_timer(chat_id, peer_id, mtop_sessions[chat_id]['last_cmid'], message, vk, 40)
        

        
        return True
        
    except Exception as e:
        return False

def start_keyboard_timer(chat_id, peer_id, message_id, message_text, vk, timeout=30):
    """Запускает таймер для скрытия клавиатуры"""
    global mtop_timers
    import threading
    
    def remove_keyboard():
        try:
            vk.messages.edit(
                peer_id=peer_id,
                message_id=message_id,
                message=message_text,
                keyboard=json.dumps({"buttons": [], "one_time": True})
            )
        except:
            pass
        if chat_id in mtop_timers:
            del mtop_timers[chat_id]
    
    if chat_id in mtop_timers:
        mtop_timers[chat_id].cancel()
    
    timer = threading.Timer(timeout, remove_keyboard)
    mtop_timers[chat_id] = timer
    timer.start()

def hide_all_keyboards(vk, sql):
    """Скрывает все инлайн кнопки при запуске бота"""
    pass  # Не отправляем ничего