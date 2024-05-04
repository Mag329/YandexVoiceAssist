from sqlalchemy import func
import math
import aiohttp

from core import logging, data, messages, bot
from core.database import User, Session, History
from core.utils import owner_send, load_history, save_history


# ========-TTS-======== #
async def count_symbols(message):
    session = Session()

    sum_symbols = (
        session.query(func.sum(User.symbols))
        .filter_by(user_id=message.from_user.id)
        .scalar()
    )

    sum_symbols = int(sum_symbols)

    session.close()

    return sum_symbols


async def update_symbols(message, symbols, set=False):
    session = Session()
    if not set:
        try:
            old_symbols = await count_symbols(message)
        except ValueError as e:
            session.close()
            raise ValueError(e) from e

        symbols = int(symbols) + int(old_symbols)

    # user = session.query(User).filter_by(user_id=message.from_user.id, status='active').first()
    user = (
        session.query(User)
        .filter(
            User.user_id == message.from_user.id,
            ((User.status == "active") | (User.status == "test")),
        )
        .first()
    )
    user.symbols = symbols
    session.commit()
    session.close()

    logging.info(f"{message.from_user.id} - Количество символов обновлено обновлены")


async def tts(message, text):
    try:
        symbols_before = await count_symbols(message)
    except ValueError as e:
        return e

    new_symbols = len(text)

    if symbols_before + new_symbols > data["speechkit"]["max_symbols"]:
        return False, messages["models"]["tts"]["symbols_limit"]

    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(
                "https://tts.api.cloud.yandex.net/speech/v1/tts:synthesize",
                headers={
                    "Authorization": f"Bearer {data['secret']['iam_token']}",
                },
                data={
                    "text": text,  # текст, который нужно преобразовать в голосовое сообщение
                    "lang": "ru-RU",  # язык текста - русский
                    "voice": "alena",  # голос Филиппа
                    "folderId": data["secret"]["folder_id"],
                },
            ) as resp:

                logging_text = f"""
                    url: https://tts.api.cloud.yandex.net/speech/v1/tts:synthesize,
                    Headers: 'Authorization': f"Bearer {data['secret']['iam_token']}",
                    Data:
                        'text': {text},
                        'lang': 'ru-RU',
                        'voice': 'filipp',
                        'folderId': {data['secret']['folder_id']}
                    """

                logging.info(f"{message.from_user.id} - Запрос к API:\n{logging_text}")

                if resp.status == 200:
                    result = await resp.read()
                    await update_symbols(message, symbols_before + new_symbols)
                    return True, result
                else:
                    try:
                        await update_symbols(message, symbols_before, True)
                    except ValueError as e:
                        return e

                    logging.error(
                        f"{message.from_user.id} - Не удалось получить ответ от нейросети\nТекст ошибки: {await resp.json()}"
                    )
                    return False, messages["models"]["tts"]["bad_response"]
        except aiohttp.ClientConnectionError as e:
            logging.error(f"{message.from_user.id} - Ошибка подключения: {e}")
            await owner_send(
                messages["models"]["tts"]["owner_bad_connection"].format(e)
            )
            return False, messages["models"]["tts"]["bad_connection"]

        except Exception as e:
            logging.error(f"{message.from_user.id} - Непредвиденная ошибка: {e}")
            await owner_send(
                messages["models"]["tts"]["owner_unexpected_error"].format(e)
            )
            return False, messages["models"]["tts"]["unexpected_error"]


# ========-STT-======== #
async def count_blocks(message):
    session = Session()

    # Выполняем запрос с использованием SQLAlchemy
    sum_blocks = (
        session.query(func.sum(User.blocks))
        .filter_by(user_id=message.from_user.id)
        .scalar()
    )

    # Проверяем, если сумма равна None, заменяем ее на 0
    if sum_blocks is None:
        sum_blocks = 0
    else:
        sum_blocks = int(sum_blocks)

    session.close()

    return sum_blocks


async def delete_last(message):
    session = Session()

    # Находим максимальный ID для данного пользователя
    max_id = (
        session.query(func.max(User.id))
        .filter_by(user_id=message.from_user.id)
        .scalar()
    )

    # Удаляем запись с найденным максимальным ID
    if max_id is not None:
        user_to_delete = session.query(User).filter_by(id=max_id).first()
        session.delete(user_to_delete)
        session.commit()

    session.close()


async def seconds_to_blocks(message, duration):
    blocks = math.ceil(duration / 15)
    return await count_blocks(message), blocks


async def stt(message, file):
    duration = message.voice.duration
    all_blocks, blocks = await seconds_to_blocks(message, duration)
    if duration >= 30:
        return False, messages["models"]["stt"]["long_voice"]

    if all_blocks >= data["speechkit"]["max_blocks"]:
        return False, messages["models"]["stt"]["max_blocks"].format(
            data["speechkit"]["max_blocks"],
            all_blocks,
            (data["speechkit"]["max_blocks"] - all_blocks),
        )

    async with aiohttp.ClientSession() as session:
        try:
            params = "&".join(
                [
                    "topic=general",
                    f"folderId={data['secret']['folder_id']}",
                    "lang=ru-RU",
                ]
            )

            async with session.post(
                f"https://stt.api.cloud.yandex.net/speech/v1/stt:recognize?{params}",
                headers={
                    "Authorization": f"Bearer {data['secret']['iam_token']}",
                },
                data=file,
            ) as resp:

                logging_text = f""" 
                    url: https://stt.api.cloud.yandex.net/speech/v1/stt:recognize?{params} 
                    Headers: 'Authorization': f"Bearer {data['secret']['iam_token']}" 
                    """
                logging.info(f"{message.from_user.id} - Запрос к API:\n{logging_text}")

                if resp.status == 200:
                    result = await resp.json()

                    if result.get("error_code") is None:
                        session = Session()
                        # user = session.query(User).filter_by(user_id=message.from_user.id, status="active").first()
                        user = (
                            session.query(User)
                            .filter(
                                User.user_id == message.from_user.id,
                                ((User.status == "active") | (User.status == "test")),
                            )
                            .first()
                        )
                        user.blocks = all_blocks + blocks
                        session.commit()
                        session.close()

                        if result.get("result") == "":
                            return True, messages["models"]["stt"]["empty_result"]
                        return True, result.get("result")

                    else:
                        return False, messages["models"]["stt"]["error"]
                else:
                    await delete_last(message)
                    logging.error(
                        f"{message.from_user.id} - Не удалось получить ответ от нейросети\nТекст ошибки: {await resp.json()}"
                    )
                    return False, messages["models"]["stt"]["bad_response"]
        except aiohttp.ClientConnectionError as e:
            logging.error(f"{message.from_user.id} - Ошибка подключения: {e}")
            await delete_last(message)
            await owner_send(
                messages["models"]["stt"]["owner_bad_connection"].format(e)
            )
            return False, messages["models"]["stt"]["bad_connection"]

        except Exception as e:
            logging.error(f"{message.from_user.id} - Непредвиденная ошибка: {e}")
            await delete_last(message)
            await owner_send(
                messages["models"]["stt"]["owner_unexpected_error"].format(e)
            )
            return False, messages["models"]["stt"]["unexpected_error"]
