def handle_id(args, from_id, peer_id, reply_to, send_message):
    if len(args) > 1:
        mention = args[1]
        if mention.startswith('[id') and '|' in mention:
            user_id = mention.split('|')[0][3:]
            send_message(peer_id, f"ID пользователя: {user_id}", reply_to)
        else:
            send_message(peer_id, "Неверный формат! Используйте: /id @пользователь", reply_to)
    else:
        send_message(peer_id, f"Ваш ID: {from_id}", reply_to)

def handle_bonus(chat_id, from_id, peer_id, reply_to, get_bonus, send_message):
    if chat_id == 0:
        return
    
    bonus, streak = get_bonus(from_id, chat_id)
    if bonus == 0:
        send_message(peer_id, "⏰ Бонус можно получить каждые 6 часов!", reply_to)
    else:
        send_message(peer_id, f"💰 Получен бонус: {bonus} монет!\n🔥 Серия заходов: {streak} дней", reply_to)