from sqlalchemy import func
from datetime import datetime, timedelta
import aiohttp
import asyncio
import yaml

from core import data, config_path, logging
from core.database import Session, User, History, Stats


async def get_total_users():
    session = Session()
    total_users = session.query(User).count()
    session.close()
    return total_users


async def get_total_tokens():
    session = Session()
    total_tokens = (session.query(func.sum(User.tokens))).scalar()
    session.close()
    return total_tokens


async def get_total_symbols():
    session = Session()
    total_symbols = (session.query(func.sum(User.symbols))).scalar()
    session.close()
    return total_symbols


async def get_total_blocks():
    session = Session()
    total_blocks = (session.query(func.sum(User.blocks))).scalar()
    session.close()
    return total_blocks


async def save_type(message, type):
    session = Session()

    stats = Stats(user_id=message.from_user.id, type=type)
    session.add(stats)
    session.commit()
    session.close()


async def get_popular_type():
    session = Session()
    popular_type = (
        session.query(Stats.type)
        .group_by(Stats.type)
        .order_by(func.count(Stats.type).desc())
        .first()
    )

    if popular_type is None:
        return True, "Н/д", "0", "0"

    type_amount_voice = session.query(Stats).filter(Stats.type == "voice").count()

    type_amount_text = session.query(Stats).filter(Stats.type == "text").count()

    session.close()
    return True, popular_type[0], type_amount_voice, type_amount_text


async def send_stats():
    total_users = await get_total_users()
    status, popular_type, type_amount_voice, type_amount_text = await get_popular_type()
    total_tokens = await get_total_tokens()
    total_symbols = await get_total_symbols()
    total_blocks = await get_total_blocks()

    if status:
        stats = {
            "members": str(total_users),
            "popular_type": str(popular_type),
            "type_amount_voice": str(type_amount_voice),
            "type_amount_text": str(type_amount_text),
            "total_tokens": str(total_tokens),
            "total_symbols": str(total_symbols),
            "total_blocks": str(total_blocks),
        }

        logging.info(f"Отправка статистики: {data}")
        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(
                    f"{data['secret']['stats']['stats_url']}/api/send_stats",
                    headers={
                        "token": f"{data['secret']['stats']['stats_token']}",
                    },
                    json=stats,
                ) as resp:
                    if resp.status == 200:
                        return
                    else:
                        logging.error(f"Ошибка отправки статистики: {resp.status}")

            except aiohttp.ClientConnectionError as e:
                logging.error(f"Ошибка отправки статистики: {e}")

            except Exception as e:
                logging.error(f"Непредвиденная ошибка при отправки статистики: {e}")


async def send_stats_timer():
    while True:
        # Проверяем срок действия токена
        time = data["secret"]["stats"]["stats_send_time"]
        if time != "None":
            time = datetime.fromisoformat(time)
            time = time + timedelta(hours=1)
            if datetime.now() >= time:
                await send_stats()
                data["secret"]["stats"]["stats_send_time"] = datetime.now().isoformat()
                with open(config_path, "w") as f:
                    yaml.dump(data, f, allow_unicode=True)
        else:
            await send_stats()
            data["secret"]["stats"]["stats_send_time"] = datetime.now().isoformat()
            with open(config_path, "w") as f:
                yaml.dump(data, f, allow_unicode=True)

        # Задержка перед следующей проверкой (1 час)
        await asyncio.sleep(3600)
