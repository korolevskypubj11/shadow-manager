from datetime import datetime

def handle_ban(event, args, chat_id, from_id, peer_id, reply_to, get_role, get_user_from_reply_or_mention, get_user_info, get_nick, ban_user, kick_user, send_message):
    """Команда /ban - блокировка пользователя (старший модератор+)"""
    if chat_id == 0:
        return
    
    if get_role(from_id, chat_id) < 30:
        send_message(peer_id, "❌ Недостаточно прав!", reply_to)
        return
    
    target_id = get_user_from_reply_or_mention(event, args, 1)
    if not target_id:
        send_message(peer_id, "❌ Укажите пользователя или ответьте на сообщение!", reply_to)
        return
    
    if get_role(from_id, chat_id) <= get_role(target_id, chat_id):
        send_message(peer_id, "❌ Нельзя заблокировать пользователя с равной или выше ролью!", reply_to)
        return
    
    # Определяем время и причину
    if 'reply_message' in event.message:
        if len(args) < 2:
            send_message(peer_id, "❌ Укажите причину!\nИспользование: /ban причина или /ban дни причина", reply_to)
            return
        
        try:
            days = int(args[1])
            if days < 3 or days > 9999:
                send_message(peer_id, "❌ Время бана должно быть от 3 до 9999 дней!", reply_to)
                return
            reason = ' '.join(args[2:]) if len(args) > 2 else "Не указана"
            duration = days * 1440
        except:
            days = 0
            duration = 0
            reason = ' '.join(args[1:])
    else:
        if len(args) < 3:
            send_message(peer_id, "❌ Укажите причину!\nИспользование: /ban @user причина или /ban @user дни причина", reply_to)
            return
        
        try:
            days = int(args[2])
            if days < 3 or days > 9999:
                send_message(peer_id, "❌ Время бана должно быть от 3 до 9999 дней!", reply_to)
                return
            reason = ' '.join(args[3:]) if len(args) > 3 else "Не указана"
            duration = days * 1440
        except:
            days = 0
            duration = 0
            reason = ' '.join(args[2:])
    
    if reason == "Не указана" or not reason:
        send_message(peer_id, "❌ Укажите причину бана!", reply_to)
        return
    
    ban_user(target_id, chat_id, from_id, reason, duration)
    kicked = kick_user(chat_id, target_id)
    
    target_mention = f"[id{target_id}|{get_nick(target_id, chat_id) or get_user_info(target_id)}]"
    moder_mention = f"[id{from_id}|{get_nick(from_id, chat_id) or get_user_info(from_id)}]"
    message = f"🔴 Бан выдан!\n"
    message += f"👤 Пользователь: {target_mention}\n"
    message += f"👮 Администратор: {moder_mention}\n"
    if days > 0:
        message += f"⏰ Срок: {days} дней\n"
    else:
        message += f"⏰ Срок: Навсегда\n"
    message += f"📝 Причина: {reason}"
    if not kicked:
        message += f"\n⚠️ {target_mention} не удалось кикнуть. У пользователя имеется звезда в чате или тех причины."
    send_message(peer_id, message, reply_to)

def handle_unban(event, args, chat_id, from_id, peer_id, reply_to, get_role, get_user_from_reply_or_mention, get_user_info, is_banned, unban_user, send_message):
    """Команда /unban - разблокировка пользователя (старший модератор+)"""
    if chat_id == 0:
        return
    
    if get_role(from_id, chat_id) < 30:
        send_message(peer_id, "❌ Недостаточно прав!", reply_to)
        return
    
    target_id = get_user_from_reply_or_mention(event, args, 1)
    if not target_id:
        send_message(peer_id, "Укажите пользователя или ответьте на сообщение!", reply_to)
        return
    
    target_mention = f"[id{target_id}|{get_nick(target_id, chat_id) or get_user_info(target_id)}]"
    if not is_banned(target_id, chat_id):
        send_message(peer_id, f"ℹ️ {target_mention} не заблокирован в этой беседе", reply_to)
        return
    
    target_mention = f"[id{target_id}|{get_nick(target_id, chat_id) or get_user_info(target_id)}]"
    unban_user(target_id, chat_id)
    send_message(peer_id, f"✅ {target_mention} разблокирован в беседе!", reply_to)

def handle_banlist(chat_id, from_id, peer_id, reply_to, get_role, get_user_info, sql, send_message):
    """Команда /banlist - список заблокированных (старший модератор+)"""
    if chat_id == 0:
        return
    
    if get_role(from_id, chat_id) < 30:
        send_message(peer_id, "❌ Недостаточно прав!", reply_to)
        return
    
    sql.execute(f"SELECT user_id, reason, ban_until FROM bans_{chat_id}")
    bans = sql.fetchall()
    
    if not bans:
        send_message(peer_id, "🔴 Пользователи в бане: отсутствуют", reply_to)
    else:
        ban_text = "🔴 Пользователи в бане:\n"
        for i, (user_id, reason, ban_until) in enumerate(bans, 1):
            user_mention = f"[id{user_id}|{get_nick(user_id, chat_id) or get_user_info(user_id)}]"
            if ban_until > 0:
                until_str = datetime.fromtimestamp(ban_until).strftime('%d.%m.%Y')
                ban_text += f"   {i}. {user_mention} - {reason} - до {until_str}\n"
            else:
                ban_text += f"   {i}. {user_mention} - {reason} - навсегда\n"
        send_message(peer_id, ban_text, reply_to)