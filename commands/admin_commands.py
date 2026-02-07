

def handle_roles(event, args, chat_id, from_id, peer_id, reply_to, get_role, get_user_from_reply_or_mention, get_user_info, set_role, get_role_name, is_bot_admin, BOT_OWNER_ID, sql, send_message):
    if chat_id == 0:
        return
    
    
    user_role = get_role(from_id, chat_id)
    if user_role < 40:
        send_message(peer_id, "❌ Недостаточно прав! Команда доступна с администратора беседы!", reply_to)
        return
    
    target_id = get_user_from_reply_or_mention(event, args, 1)
    if not target_id:
        send_message(peer_id, "❌ Укажите пользователя или ответьте на сообщение!\n📝 Пример: /role @user 1 или ответ на сообщение + /role 1", reply_to)
        return
    
    if target_id == from_id:
        send_message(peer_id, "❌ Вы не можете выдать роль самому себе! 😅", reply_to)
        return
    
    # Определяем уровень роли
    if 'reply_message' in event.message:
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
    
    if role_level < 0 or role_level > 7:
        send_message(peer_id, "❌ Уровень роли должен быть от 0 до 7!\n\n🎭 Уровни ролей:\n0 - Пользователь\n1 - Модератор\n2 - Старший модератор\n3 - Администратор\n4 - Старший администратор\n5 - Главный администратор\n6 - Спец админ\n7 - Владелец Проекта", reply_to)
        return
    
    # Конвертируем уровни в новые значения
    role_mapping = {0: 0, 1: 20, 2: 30, 3: 40, 4: 45, 5: 80, 6: 95, 7: 100}
    actual_role = role_mapping[role_level]
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
    
    role_names = {0: "Пользователь", 1: "Модератор", 2: "Ст. Модератор", 
                 3: "Администратор", 4: "Ст. Администратор", 5: "Главный администратор", 6: "Спец админ", 7: "Владелец Проекта"}
    
    set_role(target_id, chat_id, actual_role)
    
    target_mention = f"[id{target_id}|{get_user_info(target_id)}]"
    message = f"✅ Роль успешно выдана! 🎉\n"
    message += f"👤 Пользователь: {target_mention}\n"
    message += f"🎭 Новая роль: {role_names[role_level]}"
    send_message(peer_id, message, reply_to)