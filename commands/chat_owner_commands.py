import time

def handle_pull(args, chat_id, from_id, peer_id, reply_to, get_role, generate_pull_id, get_chat_pull_id, get_pull_by_id, set_pull_id, sql, database, send_message):
    """Команда /pull - объединение чатов (владелец беседы+)"""
    if chat_id == 0:
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
            message += f"• /pull {current_pull_id} - подключить другой чат\n"
            message += f"• /pull off - отключить объединение"
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

    # Подключение к существующему объединению
    existing_chats = get_pull_by_id(pull_arg)
    if not existing_chats:
        send_message(peer_id, "❌ Объединение с таким ID не найдено!", reply_to)
        return

    set_pull_id(chat_id, pull_arg)
    message = f"✅ Чат успешно подключен к объединению!\n"
    message += f"🆔 ID объединения: {pull_arg}\n"
    message += f"📊 Всего чатов в объединении: {len(existing_chats) + 1}"
    send_message(peer_id, message, reply_to)

def handle_pullinfo(chat_id, from_id, peer_id, reply_to, get_role, get_chat_pull_id, get_pull_chats, vk, send_message):
    """Команда /pullinfo - информация об объединении (владелец беседы+)"""
    if chat_id == 0:
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

def handle_transfer_ownership(event, args, chat_id, from_id, peer_id, reply_to, get_role, get_user_from_reply_or_mention, get_user_info, sql, database, send_message):
    """Команда /transfervl - передача прав владельца (владелец беседы)"""
    if chat_id == 0:
        return
    
    # Проверяем, что пользователь владелец беседы
    sql.execute(f"SELECT owner_id FROM chats WHERE chat_id = {chat_id}")
    owner = sql.fetchone()
    if not owner or owner[0] != from_id:
        send_message(peer_id, "❌ Недостаточно прав! Команда доступна только владельцу беседы!", reply_to)
        return
    
    target_id = get_user_from_reply_or_mention(event, args, 1)
    if not target_id:
        send_message(peer_id, "❌ Укажите пользователя или ответьте на сообщение!", reply_to)
        return
    
    if target_id == from_id:
        send_message(peer_id, "❌ Нельзя передать права самому себе!", reply_to)
        return
    
    # Создаем запрос на передачу прав
    sql.execute(f"CREATE TABLE IF NOT EXISTS transfer_pending_{chat_id} (from_user INTEGER, to_user INTEGER, timestamp INTEGER)")
    sql.execute(f"DELETE FROM transfer_pending_{chat_id} WHERE from_user = {from_id}")
    sql.execute(f"INSERT INTO transfer_pending_{chat_id} VALUES (?, ?, ?)", (from_id, target_id, int(time.time())))
    database.commit()
    
    target_mention = f"[id{target_id}|{get_user_info(target_id)}]"
    message = f"⚠️ Передача прав владельца беседы\n\n"
    message += f"👤 {target_mention}, вам предлагают стать владельцем беседы!\n\n"
    message += f"✅ Для согласия напишите: /yes\n"
    message += f"❌ Для отказа напишите: /no\n\n"
    message += f"⏰ У вас есть 5 минут для ответа"
    send_message(peer_id, message, reply_to)