def handle_kick(args, chat_id, from_id, peer_id, reply_to, get_new_role_level, get_role, get_user_info, kick_user, send_message, parse_user_mention):
    if chat_id == 0:
        send_message(peer_id, "Команда работает только в беседах!", reply_to)
        return
    
    user_role = get_new_role_level(from_id, chat_id)
    if user_role < 20:
        send_message(peer_id, "❌ Недостаточно прав!", reply_to)
        return
    
    if len(args) < 2:
        send_message(peer_id, "Укажите пользователя: /kick @пользователь", reply_to)
        return
    
    mention = args[1]
    if mention.startswith('[id') and '|' in mention:
        try:
            target_id = int(mention.split('|')[0][3:])
            target_role = get_role(target_id, chat_id)
            
            if user_role <= target_role:
                send_message(peer_id, "❌ Нельзя исключить пользователя с равной или выше ролью!", reply_to)
                return
            
            if kick_user(chat_id, target_id):
                reason = ' '.join(args[2:]) if len(args) > 2 else "Не указана"
                target_mention = f"[id{target_id}|{get_user_info(target_id)}]"
                from_mention = f"[id{from_id}|{get_user_info(from_id)}]"
                send_message(peer_id, f"✅ {from_mention} исключил {target_mention}\nПричина: {reason}", reply_to)
            else:
                send_message(peer_id, "❌ Не удалось исключить пользователя!", reply_to)
        except Exception as e:
            send_message(peer_id, "❌ Ошибка обработки упоминания!", reply_to)
    else:
        send_message(peer_id, "Неверный формат! Используйте: /kick @пользователь", reply_to)

def handle_warn(event, args, chat_id, from_id, peer_id, reply_to, get_role, get_user_from_reply_or_mention, get_user_info, get_nick, warn_user, kick_user, send_message):
    if chat_id == 0:
        return
    
    if get_role(from_id, chat_id) < 20:
        send_message(peer_id, "❌ Недостаточно прав!", reply_to)
        return
    
    target_id = get_user_from_reply_or_mention(event, args, 1)
    if not target_id:
        send_message(peer_id, "Укажите пользователя или ответьте на сообщение!", reply_to)
        return
    
    if get_role(from_id, chat_id) <= get_role(target_id, chat_id):
        send_message(peer_id, "❌ Нельзя выдать предупреждение пользователю с равной или выше ролью!", reply_to)
        return
    
    # Определяем причину
    if 'reply_message' in event.message:
        reason = ' '.join(args[1:]) if len(args) > 1 else "Не указана"
    else:
        reason = ' '.join(args[2:]) if len(args) > 2 else "Не указана"
    
    warns = warn_user(target_id, chat_id, from_id, reason)
    
    target_mention = f"[id{target_id}|{get_nick(target_id, chat_id) or get_user_info(target_id)}]"
    moder_mention = f"[id{from_id}|{get_nick(from_id, chat_id) or get_user_info(from_id)}]"
    if warns >= 3:
        if kick_user(chat_id, target_id):
            message = f"⚠️ Предупреждение выдано!\n"
            message += f"👤 Пользователь: {target_mention}\n"
            message += f"👮 Администратор: {moder_mention}\n"
            message += f"💥 Пользователь исключен за 3 предупреждения!\n"
            message += f"📝 Причина: {reason}"
        else:
            message = f"⚠️ Предупреждение выдано!\n"
            message += f"👤 Пользователь: {target_mention}\n"
            message += f"👮 Администратор: {moder_mention}\n"
            message += f"📝 Причина: {reason}\n"
            message += f"⚠️ {target_mention} не удалось кикнуть. У пользователя имеется звезда в чате или тех причины."
        send_message(peer_id, message, reply_to)
    else:
        message = f"⚠️ Предупреждение выдано!\n"
        message += f"👤 Пользователь: {target_mention}\n"
        message += f"👮 Администратор: {moder_mention}\n"
        message += f"📊 Количество: {warns}/3\n"
        message += f"📝 Причина: {reason}"
        send_message(peer_id, message, reply_to)

def handle_mute(event, args, chat_id, from_id, peer_id, reply_to, get_role, get_user_from_reply_or_mention, get_user_info, get_nick, is_muted, mute_user, send_message):
    if chat_id == 0:
        return
    
    if get_role(from_id, chat_id) < 20:
        send_message(peer_id, "❌ Недостаточно прав!", reply_to)
        return
    
    target_id = get_user_from_reply_or_mention(event, args, 1)
    if not target_id:
        send_message(peer_id, "Укажите пользователя или ответьте на сообщение!", reply_to)
        return
    
    if get_role(from_id, chat_id) <= get_role(target_id, chat_id):
        send_message(peer_id, "❌ Нельзя замутить пользователя с равной или выше ролью!", reply_to)
        return
    
    # Определяем время и причину
    if 'reply_message' in event.message:
        if len(args) < 2:
            send_message(peer_id, "Укажите время в минутах!", reply_to)
            return
        try:
            minutes = int(args[1])
            reason = ' '.join(args[2:]) if len(args) > 2 else "Причина не указана"
        except:
            send_message(peer_id, "Неверное время!", reply_to)
            return
    else:
        if len(args) < 3:
            send_message(peer_id, "Использование: /mute @пользователь минуты [причина]", reply_to)
            return
        try:
            minutes = int(args[2])
            reason = ' '.join(args[3:]) if len(args) > 3 else "Причина не указана"
        except:
            send_message(peer_id, "Неверное время!", reply_to)
            return
    
    if minutes < 1 or minutes > 10080:
        send_message(peer_id, "Время должно быть от 1 до 10080 минут (неделя)!", reply_to)
        return
    
    if is_muted(target_id, chat_id):
        send_message(peer_id, f"ℹ️ {get_user_info(target_id)} уже замучен!", reply_to)
        return
    
    mute_user(target_id, chat_id, from_id, reason, minutes)
    
    target_mention = f"[id{target_id}|{get_nick(target_id, chat_id) or get_user_info(target_id)}]"
    moder_mention = f"[id{from_id}|{get_nick(from_id, chat_id) or get_user_info(from_id)}]"
    message = f"🔇 Мут выдан!\n"
    message += f"👤 Пользователь: {target_mention}\n"
    message += f"👮 Администратор: {moder_mention}\n"
    message += f"⏰ Время: {minutes} минут\n"
    message += f"📝 Причина: {reason}"
    send_message(peer_id, message, reply_to)