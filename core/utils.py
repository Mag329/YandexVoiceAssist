import telebot
import asyncssh
import re
import yaml
import ast
from sqlalchemy import func
from datetime import datetime, timedelta
import asyncio

from core import data, logging, messages, config_path, bot
from core.database import User, History, Session


async def generate_markup(buttons):
    markup = telebot.async_telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    for button in buttons:
        markup.add(button)

    return markup


# Отправка сообщения владельцу бота
async def owner_send(message):
    await bot.send_message(data["secret"]["owner_id"], message)


async def new_user(message):
    session = Session()

    unique_users = session.query(func.count(User.user_id.distinct())).scalar()
    if unique_users >= data["main"]["max_users"]:
        session.close()
        return False, messages["models"]["new_user"]["users_limit"]
    else:
        check_exist = (
            session.query(User).filter_by(user_id=message.from_user.id).first()
        )
        if check_exist is None:
            user = User(user_id=message.from_user.id)
            history = History(user_id=message.from_user.id)
            session.add(user)
            session.add(history)
            session.commit()
            session.close()
            return True, ""
        else:
            return False, messages["models"]["new_user"]["already_reg"]


async def set_status(message, status):
    session = Session()

    user = session.query(User).filter_by(user_id=message.from_user.id).first()
    user.status = status
    session.commit()
    session.close()


async def get_status(message):
    session = Session()

    user = (
        session.query(User)
        .filter_by(user_id=message.from_user.id, status="test")
        .first()
    )
    session.close()
    if user is None:
        return False
    else:
        return True


async def limit_info(message):
    session = Session()

    user = (
        session.query(User)
        .filter(
            User.user_id == message.from_user.id,
            ((User.status == "active") | (User.status == "test")),
        )
        .first()
    )

    tokens = user.tokens
    symbols = user.symbols
    blocks = user.blocks

    token_limit = data["gpt"]["token_limit"]
    symbols_limit = data["speechkit"]["max_symbols"]
    blocks_limit = data["speechkit"]["max_blocks"]
    return messages["bot"]["limit"]["text"].format(
        tokens,
        token_limit,
        (token_limit - tokens),
        symbols,
        symbols_limit,
        symbols_limit - symbols,
        blocks,
        blocks_limit,
        blocks_limit - blocks,
    )


async def save_history(message, history):
    session = Session()

    check_exist = session.query(User).filter_by(user_id=message.from_user.id).first()
    if check_exist is None:
        raise ValueError(messages["models"]["save_history"]["user_not_found"])

    else:
        history_db = (
            session.query(History)
            .filter_by(user_id=message.from_user.id, status="active")
            .first()
        )
        history_db.history = str(history).replace('"', '\\"')
        session.commit()
        logging.info(f"{message.from_user.id} - История сохранена")

    session.close()


# Загрузка истории из базы данных
async def load_history(message):
    session = Session()

    history = (
        session.query(History)
        .filter_by(user_id=message.from_user.id, status="active")
        .first()
    )
    session.close()

    if history is None:
        raise ValueError(messages["models"]["load_history"]["user_not_found"])

    history = history.history

    if history != "None":
        return ast.literal_eval(history)

    else:
        return []


async def clear_history(message):
    session = Session()

    history = (
        session.query(History)
        .filter_by(user_id=message.from_user.id, status="active")
        .first()
    )
    history.status = "disable"

    new_history = History(user_id=message.from_user.id)
    session.add(new_history)
    session.commit()
    logging.info(f"{message.from_user.id} - История очищена")

    session.close()


# Авто получение токена с сервера
async def run_command(host, username, key_file):
    async with asyncssh.connect(
        host, username=username, client_keys=[key_file]
    ) as conn:
        result = await conn.run(
            "curl -H Metadata-Flavor:Google 169.254.169.254/computeMetadata/v1/instance/service-accounts/default/token"
        )
        access_token = re.search(r'"access_token":"(.+?)"', result.stdout)
        if access_token:
            logging.info(f"Токен получен: {access_token.group(1)}")
            return access_token.group(1)
        else:
            return None


async def get_iam_token(host, username, key_file):
    access_token = await run_command(host, username, key_file)
    if access_token:
        # Сохраняем токен и текущее время в конфиг
        data["secret"]["iam_token"] = access_token
        data["secret"]["token_created_at"] = datetime.now().isoformat()
        try:
            with open(config_path, "w") as f:
                yaml.dump(data, f, allow_unicode=True)
        except yaml.YAMLError as e:
            print(f"Ошибка при сохранении токена в config.yaml: \n{e}")
            logging.critical(messages["models"]["get_token"]["error1"].format(e))
            owner_send(messages["models"]["get_token"]["owner1"].format(e))
    else:
        print("Не удалось получить IAM-токен")
        logging.critical(messages["models"]["get_token"]["error2"])
        owner_send(messages["models"]["get_token"]["owner2"])


async def connect():
    host = data["secret"]["ssh"]["host"]
    username = data["secret"]["ssh"]["username"]
    key_file = data["secret"]["ssh"]["key_file"]

    while True:
        # Проверяем срок действия токена
        token_created_at = data["secret"].get("token_created_at")
        if token_created_at != "None":
            token_created_at = datetime.fromisoformat(token_created_at)
            token_expiration = token_created_at + timedelta(hours=12)
            if datetime.now() >= token_expiration:
                logging.info(f"Срок действия токена истек, получаем новый токен")
                await get_iam_token(host, username, key_file)
        else:
            await get_iam_token(host, username, key_file)

        # Задержка перед следующей проверкой (1 час)
        await asyncio.sleep(3600)
