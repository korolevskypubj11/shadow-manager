def handle_givemoney(event, args, chat_id, from_id, peer_id, reply_to, BOT_OWNER_ID, get_user_from_reply_or_mention, get_user_info, sql, database, send_message):
    if from_id != BOT_OWNER_ID:
        send_message(peer_id, "❌ Недостаточно прав! Команда доступна только владельцу бота!", reply_to)
        return
    
    target_id = get_user_from_reply_or_mention(event, args, 1)
    if not target_id:
        send_message(peer_id, "❌ Укажите пользователя или ответьте на сообщение!", reply_to)
        return
    
    # Определяем количество монет
    if 'reply_message' in event.message:
        if len(args) < 2:
            send_message(peer_id, "❌ Укажите количество монет!\nПример: /givemoney 1000", reply_to)
            return
        try:
            amount = int(args[1])
        except:
            send_message(peer_id, "❌ Укажите корректное количество!", reply_to)
            return
    else:
        if len(args) < 3:
            send_message(peer_id, "❌ Укажите количество монет!\nПример: /givemoney @user 1000", reply_to)
            return
        try:
            amount = int(args[2])
        except:
            send_message(peer_id, "❌ Укажите корректное количество!", reply_to)
            return
    
    if amount <= 0:
        send_message(peer_id, "❌ Количество должно быть больше 0!", reply_to)
        return
    
    # Выдаем монеты во всех чатах где есть пользователь
    sql.execute("SELECT chat_id FROM chats")
    all_chats = sql.fetchall()
    updated_chats = 0
    
    for (chat,) in all_chats:
        try:
            sql.execute(f"CREATE TABLE IF NOT EXISTS bonuses_{chat} (user_id INTEGER, last_bonus INTEGER, streak INTEGER, coins INTEGER)")
            sql.execute(f"SELECT coins FROM bonuses_{chat} WHERE user_id = {target_id}")
            if sql.fetchone():
                sql.execute(f"UPDATE bonuses_{chat} SET coins = coins + ? WHERE user_id = ?", (amount, target_id))
            else:
                sql.execute(f"INSERT INTO bonuses_{chat} VALUES (?, 0, 0, ?)", (target_id, amount))
            updated_chats += 1
        except:
            pass
    
    database.commit()
    
    target_mention = f"[id{target_id}|{get_user_info(target_id)}]"
    message = f"💰 Монеты выданы!\n"
    message += f"👤 Пользователь: {target_mention}\n"
    message += f"💸 Сумма: {amount} монет\n"
    message += f"📊 Обновлено чатов: {updated_chats}"
    send_message(peer_id, message, reply_to)

def handle_addmoder(args, from_id, peer_id, reply_to, BOT_OWNER_ID, BOT_MODERATORS, parse_user_mention, get_user_info, sql, database, send_message):
    if from_id != BOT_OWNER_ID:
        send_message(peer_id, "❌ Недостаточно прав! Команда доступна только владельцу бота!", reply_to)
        return
    if len(args) < 2:
        send_message(peer_id, "Укажите пользователя: /addmoder @пользователь", reply_to)
        return
    target_id = parse_user_mention(args[1])
    if not target_id:
        send_message(peer_id, "Неверный формат пользователя!", reply_to)
        return
    if target_id not in BOT_MODERATORS:
        BOT_MODERATORS.append(target_id)
    sql.execute("INSERT OR REPLACE INTO bot_admins VALUES (?, 'moderator')", (target_id,))
    database.commit()
    target_mention = f"[id{target_id}|{get_user_info(target_id)}]"
    send_message(peer_id, f"✅ {target_mention} получил права модератора бота!", reply_to)

def handle_stop_bot(from_id, peer_id, reply_to, BOT_OWNER_ID, sql, database, send_message):
    if from_id != BOT_OWNER_ID:
        send_message(peer_id, "❌ Недостаточно прав! Команда доступна только владельцу бота!", reply_to)
        return
    
    shutdown_msg = "🔴 Бот остановлен для обновления или по тех причинам. \n🔄 Ожидайте пока разработчики бота включат бота"
    
    sql.execute("SELECT peer_id FROM chats")
    all_chats = sql.fetchall()
    for chat in all_chats:
        try:
            send_message(chat[0], shutdown_msg)
        except:
            pass
    
    try:
        send_message(from_id, shutdown_msg)
    except:
        pass
    
    print("Бот остановлен командой /stop_bot")
    database.commit()
    exit(0)