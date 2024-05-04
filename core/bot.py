from core import bot, messages, logging
from core.gpt import request
from core.speechkit import stt, tts
from core.utils import (
    generate_markup,
    new_user,
    get_status,
    set_status,
    limit_info,
    clear_history,
)
from core.stats import send_stats, save_type


@bot.message_handler(commands=["start"])
async def start_handler(message):
    logging.info(f"{message.from_user.id} - Отправка приветственного сообщения")
    markup = await generate_markup(messages["bot"]["start"]["buttons"])
    status, text = await new_user(message)
    if status:
        await bot.send_message(
            message.chat.id, messages["bot"]["start"]["text"], reply_markup=markup
        )

    else:
        await bot.send_message(message.chat.id, text)


@bot.message_handler(commands=["help"])
async def help_handler(message):
    logging.warning(f"{message.from_user.id} - Использование /help")
    await bot.send_message(message.chat.id, messages["bot"]["help"]["text"])


@bot.message_handler(commands=["debug"])
async def debug(message):
    logging.warning(f"{message.from_user.id} - Использование /debug")
    with open("logs/latest.log", "rb") as f:
        await bot.send_document(message.chat.id, f)


@bot.message_handler(commands=["test"])
async def test(message):
    is_test = await get_status(message)
    if is_test:
        await set_status(message, "active")
        markup = await generate_markup(messages["bot"]["test"]["buttons_leave"])
        await bot.send_message(
            message.chat.id,
            messages["models"]["test"]["deactivate"],
            reply_markup=markup,
        )
    else:
        await set_status(message, "test")
        markup = await generate_markup(messages["bot"]["test"]["buttons"])
        await bot.send_message(
            message.chat.id, messages["models"]["test"]["activate"], reply_markup=markup
        )


@bot.message_handler(content_types=["voice"])
async def handler_stt(message):
    logging.info(f"{message.from_user.id} - Получено голосовое сообщение")
    file_id = message.voice.file_id  # получаем id голосового сообщения
    file_info = await bot.get_file(file_id)  # получаем информацию о голосовом сообщении
    file = await bot.download_file(file_info.file_path)

    is_test = await get_status(message)
    if is_test:
        status_stt, response_stt = await stt(message, file)
        if status_stt:
            await bot.send_message(
                message.chat.id, response_stt, reply_to_message_id=message.id
            )
            await bot.send_message(
                message.chat.id, messages["models"]["test"]["tts_check"]
            )
        else:
            await bot.send_message(
                message.chat.id, response_stt, reply_to_message_id=message.id
            )
    else:
        await save_type(message, "voice")

        status_stt, response_stt = await stt(message, file)
        if status_stt:
            status_gpt, response_gpt = await request(message, response_stt)
            if status_gpt:
                status_tts, response_tts = await tts(message, response_gpt)
                if status_tts:
                    await bot.send_voice(message.chat.id, response_tts)
                else:
                    await bot.send_message(
                        message.chat.id,
                        messages["models"]["tts"]["tts_not_work"].format(response_tts),
                    )
                    await bot.send_message(message.chat.id, response_gpt)
            else:
                await bot.send_message(message.chat.id, response_gpt)
        else:
            await bot.send_message(message.chat.id, response_stt)


@bot.message_handler(
    func=lambda message: message.text in messages["bot"]["skip"]["triger"]
    or message.text in messages["bot"]["test"]["triger"]
)
async def skip(message):
    is_test = await get_status(message)
    if is_test:
        await set_status(message, "active")
        markup = await generate_markup(messages["bot"]["test"]["buttons_leave"])
        await bot.send_message(
            message.chat.id,
            messages["models"]["test"]["deactivate"],
            reply_markup=markup,
        )


@bot.message_handler(
    func=lambda message: message.text in messages["bot"]["limit"]["triger"]
)
async def limit_handler(message):
    logging.info(f"{message.from_user.id} - Отправка лимита")
    text = await limit_info(message)
    await bot.send_message(message.chat.id, text)


@bot.message_handler(
    func=lambda message: message.text in messages["bot"]["clear"]["triger"]
)
async def clear_handler(message):
    logging.info(f"{message.from_user.id} - Очистка истории")
    await clear_history(message)
    await bot.send_message(message.chat.id, messages["bot"]["clear"]["text"])


@bot.message_handler()
async def text_handler(message):
    is_test = await get_status(message)
    if is_test:
        status_tts, response_tts = await tts(message, message.text)
        if status_tts:
            await bot.send_voice(
                message.chat.id, response_tts, reply_to_message_id=message.id
            )
            await set_status(message, "active")
            markup = await generate_markup(messages["bot"]["test"]["buttons"])
            await bot.send_message(
                message.chat.id,
                messages["models"]["test"]["deactivate"],
                reply_markup=markup,
            )
        else:
            await save_type(message, "text")
            await bot.send_message(
                message.chat.id, response_tts, reply_to_message_id=message.id
            )
    else:
        logging.debug(f"{message.from_user.id} - Полученный текст: {message.text}")
        status, response = await request(message)
        await bot.send_message(message.chat.id, response)
