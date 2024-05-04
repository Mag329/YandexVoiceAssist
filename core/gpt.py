import aiohttp
import asyncio

from core import logging, data, messages, bot
from core.database import User, Session, History
from core.utils import owner_send, load_history, save_history


# Подсчет токенов в тексте
async def count_tokens(message, text):
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(
                "https://llm.api.cloud.yandex.net/foundationModels/v1/tokenize",
                headers={
                    "Authorization": f"Bearer {data['secret']['iam_token']}",
                    "Content-Type": "application/json",
                },
                json={
                    "modelUri": f"gpt://{data['secret']['folder_id']}/yandexgpt-lite/latest",
                    "text": text,
                },
            ) as resp:
                if resp.status == 200:
                    return len((await resp.json())["tokens"])

        except aiohttp.ClientConnectionError as e:
            logging.error(f"{message.from_user.id} - Ошибка подключения: {e}")
            await owner_send(
                messages["models"]["count_tokens"]["owner_bad_connection"].format(e)
            )
            raise Warning(messages["models"]["count_tokens"]["bad_connection"]) from e
            # return messages['models']['count_tokens']['bad_connection']

        except Exception as e:
            logging.error(f"{message.from_user.id} - Непредвиденная ошибка: {e}")
            await owner_send(
                messages["models"]["count_tokens"]["owner_unexpected_error"].format(e)
            )

            raise Warning(messages["models"]["count_tokens"]["unexpected_error"]) from e
            # return messages['models']['count_tokens']['unexpected_error']


# Получить количество токенов
async def get_tokens(message):
    session = Session()

    tokens = (
        session.query(User)
        .filter_by(user_id=message.from_user.id, status="active")
        .first()
        .tokens
    )

    logging.info(f"{message.from_user.id} - Токенов: {tokens}")
    session.close()
    return tokens


# Обновить количество токенов
async def update_tokens(message, tokens, set=False):
    if not set:
        old_tokens = await get_tokens(message)
        tokens = int(tokens) + int(old_tokens)

    session = Session()
    user = (
        session.query(User)
        .filter_by(user_id=message.from_user.id, status="active")
        .first()
    )
    user.tokens = tokens
    session.commit()

    session.close()

    logging.info(f"{message.from_user.id} - Токены обновлены")


# запрос к GPT
async def request(message, text=None):
    try:
        history = await load_history(message)
    except ValueError as e:
        return False, e

    # Сколько токенов было до запроса
    tokens_before = await get_tokens(message)
    # Если история пустая, то добавляем системный текст и токены к истории
    if history == []:
        system_content = data["gpt"]["system_content"]

        history.append({"role": "system", "text": system_content})

        system_tokens = await count_tokens(message, system_content)

        await update_tokens(message, system_tokens)

    if not text:
        content = message.text
    else:
        content = text

    old_tokens = await get_tokens(message)
    new_tokens = await count_tokens(message, content)

    if new_tokens > data["gpt"]["max_tokens_request"]:
        return False, messages["models"]["gpt_request"]["too_long"]

    else:
        await update_tokens(message, new_tokens)

    if old_tokens + new_tokens > data["gpt"]["token_limit"]:
        return False, messages["models"]["gpt_request"]["token_limit"]

    history.append({"role": "user", "text": content})

    async def keep_typing(chat_id):
        while True:
            await bot.send_chat_action(chat_id=chat_id, action="typing")
            await asyncio.sleep(5)  # Задержка между отправками действия "typing"

    typing_task = asyncio.create_task(keep_typing(message.chat.id))

    history_messages = []
    for row in history:
        history_messages.append({"role": row["role"], "text": row["text"]})

    all_tokens = old_tokens + new_tokens
    if data["gpt"]["token_limit"] - all_tokens >= data["gpt"]["max_tokens_response"]:
        max_tokens_response = data["gpt"]["max_tokens_request"]

    else:
        max_tokens_response = data["gpt"]["token_limit"] - all_tokens

    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(
                "https://llm.api.cloud.yandex.net/foundationModels/v1/completion",
                headers={
                    "Authorization": f"Bearer {data['secret']['iam_token']}",
                    "Content-Type": "application/json",
                },
                json={
                    "modelUri": f"gpt://{data['secret']['folder_id']}/yandexgpt-lite/latest",
                    "completionOptions": {
                        "stream": False,
                        "temperature": data["gpt"]["temperature"],
                        "maxTokens": str(max_tokens_response),
                    },
                    "messages": history_messages,
                },
            ) as resp:
                logging_text = (
                    f"""- Request: {
                                    'https://llm.api.cloud.yandex.net/foundationModels/v1/completion',
                                    {
                                        'Authorization': f"Bearer {data['secret']['iam_token']}",
                                        'Content-Type': 'application/json'
                                    },
                                    {
                                        "modelUri": f"gpt://{data['secret']['folder_id']}/yandexgpt-lite/latest",
                                        "completionOptions": {
                                            "stream": False, 
                                            "temperature": data['gpt']['temperature'],
                                            "maxTokens": str(data['gpt']['max_tokens_response'])
                                        },
                                        "messages": history_messages}}\n\n"""
                    f"- Response: {str(resp.status)}"
                )

                logging.info(
                    f"{message.from_user.id} - Запрос к нейросети:\n{logging_text}"
                )

                if resp.status == 200:
                    result = (await resp.json())["result"]["alternatives"][0][
                        "message"
                    ]["text"]

                    tokens_usage = (await resp.json())["result"]["usage"][
                        "completionTokens"
                    ]
                    await update_tokens(message, tokens_usage)
                    history.append({"role": "assistant", "text": result})
                    await save_history(message, history)
                    typing_task.cancel()
                    return True, result

                else:
                    await update_tokens(message, tokens_before, True)
                    logging.error(
                        f"{message.from_user.id} - Не удалось получить ответ от нейросети\nТекст ошибки: {await resp.json()}"
                    )
                    typing_task.cancel()
                    return False, messages["models"]["gpt_request"]["bad_response"]

        except aiohttp.ClientConnectionError as e:
            logging.error(f"{message.from_user.id} - Ошибка подключения: {e}")
            await owner_send(
                messages["models"]["gpt_request"]["owner_bad_connection"].format(e)
            )
            typing_task.cancel()
            return False, messages["models"]["gpt_request"]["bad_connection"]

        except Exception as e:
            logging.error(f"{message.from_user.id} - Непредвиденная ошибка: {e}")
            await owner_send(
                messages["models"]["gpt_request"]["owner_unexpected_error"].format(e)
            )
            typing_task.cancel()
            return False, messages["models"]["gpt_request"]["unexpected_error"]
