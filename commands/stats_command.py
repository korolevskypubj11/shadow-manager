import time
from datetime import datetime

def handle_stats(event_obj, args, chat_id, from_id, peer_id, reply_to, get_user_from_reply_or_mention, get_new_role_level, get_user_info, get_nick, get_role, get_role_name, get_warn_count, get_user_stats, get_marriage_partner, sql, database, send_message):
    """Обработка команды /stats (старый стиль)"""
    
    print(f"[STATS DEBUG] Начало обработки команды stats (старый стиль)")
    print(f"[STATS DEBUG] chat_id: {chat_id}, from_id: {from_id}")
    
    try:
        if chat_id == 0:
            send_message(peer_id, "🚫 Эта команда работает только в беседах!", reply_to)
            return
        
        # Определяем целевого пользователя
        target_id = get_user_from_reply_or_mention(event_obj, args, 1)
        if not target_id:
            target_id = from_id
            print(f"[STATS DEBUG] Используем отправителя как цель: {target_id}")
        
        print(f"[STATS DEBUG] Целевой пользователь: {target_id}")
        
        # Проверяем права на просмотр статистики других пользователей
        if target_id != from_id:
            viewer_role = get_role(from_id, chat_id)
            if viewer_role < 10:  # Только модератор и выше может смотреть чужие статистики
                send_message(peer_id, "❌ Недостаточно прав! Для просмотра статистики других пользователей нужна роль модератора или выше!", reply_to)
                return
            print(f"[STATS DEBUG] Просмотр чужой статистики разрешен")
        
        # Получаем основную информацию о пользователе
        user_name = get_user_info(target_id)
        print(f"[STATS DEBUG] Имя пользователя: {user_name}")
        
        # Получаем ник, если есть
        user_nick = get_nick(target_id, chat_id)
        
        # Получаем роль пользователя
        user_role_level = get_role(target_id, chat_id)
        print(f"[STATS DEBUG] Уровень роли: {user_role_level}")
        
        # Используем обновленную функцию get_role_name с параметром chat_id
        role_name = get_role_name(user_role_level, chat_id)
        print(f"[STATS DEBUG] Название роли: {role_name}")
        
        # Получаем статистику пользователя
        join_date, inviter_id, messages_count = get_user_stats(target_id, chat_id)
        print(f"[STATS DEBUG] Сообщений: {messages_count}")
        
        # Форматируем дату вступления (старый стиль)
        join_date_obj = datetime.fromtimestamp(join_date)
        month_names = {
            1: 'января', 2: 'февраля', 3: 'марта', 4: 'апреля',
            5: 'мая', 6: 'июня', 7: 'июля', 8: 'августа',
            9: 'сентября', 10: 'октября', 11: 'ноября', 12: 'декабря'
        }
        month_name = month_names[join_date_obj.month]
        join_date_str = f"{join_date_obj.day} {month_name} {join_date_obj.year} года в {join_date_obj.hour:02d}:{join_date_obj.minute:02d}"
        print(f"[STATS DEBUG] Дата вступления: {join_date_str}")
        
        # Вычисляем сколько дней в беседе
        days_in_chat = (int(time.time()) - join_date) // 86400
        print(f"[STATS DEBUG] Дней в чате: {days_in_chat}")
        
        # Получаем количество предупреждений
        warns_count = get_warn_count(target_id, chat_id)
        print(f"[STATS DEBUG] Варнов: {warns_count}")
        
        # Получаем информацию о браке
        marriage_partner = get_marriage_partner(target_id, chat_id)
        is_married = marriage_partner is not None
        print(f"[STATS DEBUG] В браке: {is_married}, Партнер: {marriage_partner}")
        
        # Получаем информацию о монетах
        try:
            sql.execute(f"CREATE TABLE IF NOT EXISTS bonuses_{chat_id} (user_id INTEGER, last_bonus INTEGER, streak INTEGER, coins INTEGER)")
            sql.execute(f"SELECT coins FROM bonuses_{chat_id} WHERE user_id = {target_id}")
            coins_result = sql.fetchone()
            coins = coins_result[0] if coins_result else 0
            print(f"[STATS DEBUG] Монет: {coins}")
        except Exception as e:
            print(f"[STATS ERROR] Ошибка получения монет: {e}")
            coins = 0
        
        # Получаем информацию о VIP статусе
        vip_status = "✗ Отсутствует"
        try:
            sql.execute("SELECT vip_type, end_time FROM vip_statuses WHERE user_id = ? AND chat_id = ?", (target_id, chat_id))
            vip_result = sql.fetchone()
            if vip_result:
                vip_type, end_time = vip_result
                if end_time > int(time.time()):
                    vip_names = {'gold': '🥇 GOLD VIP', 'elite': '📎 ELITE VIP', 'diamond': '💎 DIAMOND VIP'}
                    vip_status = vip_names.get(vip_type, vip_type)
                    days_left = (end_time - int(time.time())) // 86400
                    vip_status += f" ({days_left} дн.)"
            print(f"[STATS DEBUG] VIP статус: {vip_status}")
        except Exception as e:
            print(f"[STATS ERROR] Ошибка получения VIP: {e}")
        
        # Формируем сообщение в старом стиле
        user_mention = f"[id{target_id}|{user_nick or user_name}]"
        stats_message = f"🌐 Профиль участника — {user_mention}\n\n"
        
        # Роль (с использованием кастомного названия)
        stats_message += f"🌀 Роль: {role_name}\n"
        
        # Ник в беседе, если есть
        if user_nick:
            stats_message += f"📛 Ник в беседе: {user_nick}\n"
        
        # Активность
        stats_message += f"💬 Активность: {messages_count} сообщений\n"
        
        # Монетки
        stats_message += f"💰 Монетки: {coins}\n"
        
        # VIP статус
        stats_message += f"👑 VIP статус: {vip_status}\n"
        
        # Статус предупреждений
        if warns_count > 0:
            stats_message += f"⚠️ Статус предупреждений: {warns_count} / 3\n"
        else:
            stats_message += f"⚠️ Статус предупреждений: 0 / 3\n"
        
        # Семейный статус
        if is_married and marriage_partner:
            partner_name = get_user_info(marriage_partner)
            stats_message += f"💍 Семейный статус: Состоит в браке\n"
        else:
            stats_message += f"💍 Семейный статус: Не состоит в браке\n"
        
        # Дата входа
        stats_message += f"📅 Дата входа: {join_date_str}"
        
        # Информация о пригласившем (Теперь публично)
        if inviter_id and inviter_id > 0:
            inviter_name = get_user_info(inviter_id)
            inviter_mention = f"[id{inviter_id}|{inviter_name}]"
            stats_message += f"\n📌 Пригласил: {inviter_mention}"
        
        # Дополнительная информация для модераторов и выше
        viewer_role = get_role(from_id, chat_id)
        if viewer_role >= 10:  # Модератор и выше
            # Информация о муте
            try:
                sql.execute(f"CREATE TABLE IF NOT EXISTS mutes_{chat_id} (user_id INTEGER, moder INTEGER, reason TEXT, end_time INTEGER)")
                sql.execute(f"SELECT end_time FROM mutes_{chat_id} WHERE user_id = {target_id}")
                mute_result = sql.fetchone()
                if mute_result and int(time.time()) < mute_result[0]:
                    mute_end = datetime.fromtimestamp(mute_result[0]).strftime('%H:%M %d.%m.%Y')
                    stats_message += f"\n📌 Мут до: {mute_end}"
            except:
                pass
            
            # Информация о бане
            try:
                sql.execute(f"SELECT ban_until FROM bans_{chat_id} WHERE user_id = {target_id}")
                ban_result = sql.fetchone()
                if ban_result:
                    ban_until = ban_result[0]
                    if ban_until == 0 or int(time.time()) < ban_until:
                        if ban_until > 0:
                            ban_end = datetime.fromtimestamp(ban_until).strftime('%H:%M %d.%m.%Y')
                            stats_message += f"\n📌 Бан до: {ban_end}"
                        else:
                            stats_message += f"\n📌 Бан: Навсегда"
            except:
                pass
            

        
        print(f"[STATS DEBUG] Статистика сформирована (старый стиль), отправляем сообщение")
        send_message(peer_id, stats_message, reply_to)
        print(f"[STATS DEBUG] Сообщение отправлено успешно")
        
    except Exception as e:
        print(f"[STATS ERROR] Критическая ошибка в handle_stats: {e}")
        error_msg = f"❌ Ошибка получения статистики: {str(e)[:100]}"
        send_message(peer_id, error_msg, reply_to)
