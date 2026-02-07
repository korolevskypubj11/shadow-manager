def handle_remove_role(event, args, chat_id, from_id, peer_id, reply_to, get_role, get_user_from_reply_or_mention, get_user_info, set_role, get_role_name, is_bot_admin, BOT_OWNER_ID, sql, send_message):
    """Команда /rr - снятие роли (старший администратор+)"""
    if chat_id == 0:
        return
    
    if get_role(from_id, chat_id) < 45:
        send_message(peer_id, "❌ Недостаточно прав! Команда доступна с Ст. Администратора!", reply_to)
        return
    
    target_id = get_user_from_reply_or_mention(event, args, 1)
    if not target_id:
        send_message(peer_id, "❌ Укажите пользователя или ответьте на сообщение!", reply_to)
        return
    
    if target_id == from_id:
        send_message(peer_id, "❌ Вы не можете снять роль самому себе!", reply_to)
        return
    
    # Проверяем админов/модеров бота - владелец может снимать роли
    if is_bot_admin(target_id) and from_id == BOT_OWNER_ID:
        try:
            sql.execute("DELETE FROM bot_admins WHERE user_id = ?", (target_id,))
            sql.commit()
            target_mention = f"[id{target_id}|{get_user_info(target_id)}]"
            send_message(peer_id, f"✅ У {target_mention} снята роль администратора/модератора бота!", reply_to)
            return
        except:
            send_message(peer_id, "❌ Ошибка снятия роли!", reply_to)
            return
    elif is_bot_admin(target_id) and from_id != BOT_OWNER_ID:
        send_message(peer_id, "❌ Снимать роли админам и модерам бота может только Владелец бота!", reply_to)
        return
    
    if get_role(from_id, chat_id) <= get_role(target_id, chat_id):
        send_message(peer_id, "❌ Вы не можете снять роль пользователю с равной или выше ролью!", reply_to)
        return
    
    old_role = get_role(target_id, chat_id)
    set_role(target_id, chat_id, 0)
    
    target_mention = f"[id{target_id}|{get_user_info(target_id)}]"
    message = f"✅ Роль успешно снята!\n"
    message += f"👤 Пользователь: {target_mention}\n"
    message += f"📝 Снята роль: {get_role_name(old_role)}"
    send_message(peer_id, message, reply_to)

def handle_remove_nick(event, args, chat_id, from_id, peer_id, reply_to, get_role, get_user_from_reply_or_mention, get_user_info, get_nick, sql, database, send_message):
    """Команда /rnick - удаление ника (старший администратор+)"""
    if chat_id == 0:
        return
    
    if get_role(from_id, chat_id) < 45:
        send_message(peer_id, "❌ Недостаточно прав! Команда доступна с Ст. Администратора!", reply_to)
        return
    
    target_id = get_user_from_reply_or_mention(event, args, 1)
    if not target_id:
        target_id = from_id
    
    # Проверяем права
    if target_id != from_id:
        if get_role(from_id, chat_id) <= get_role(target_id, chat_id):
            send_message(peer_id, "❌ Вы не можете удалить ник пользователю с равной или выше ролью!", reply_to)
            return
    
    old_nick = get_nick(target_id, chat_id)
    target_mention = f"[id{target_id}|{get_user_info(target_id)}]"
    if not old_nick:
        send_message(peer_id, f"ℹ️ У {target_mention} нет ника", reply_to)
        return
    
    try:
        sql.execute(f"DELETE FROM nicks_{chat_id} WHERE user_id = ?", (target_id,))
        database.commit()
        
        target_mention = f"[id{target_id}|{get_user_info(target_id)}]"
        message = f"🗑️ Ник успешно удалён!\n"
        message += f"👤 Пользователь: {target_mention}\n"
        message += f"📝 Удалённый ник: {old_nick}"
        send_message(peer_id, message, reply_to)
    except Exception as e:
        send_message(peer_id, "❌ Ошибка удаления ника!", reply_to)