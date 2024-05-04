# Бот голосовой помощник

Бот выполняет функцию внимательного и дружелюбного ассистента, с которым можно обсуждать любые вопросы

### **Алгоритм работы бота**
- Бот принимает текстовое или голосовое сообщение
- Если получен текст, он отправляется в качестве промта в YandexGPT
- Если получено голосовое сообщение:
    - Оно расшифровывается в текст с помощью SpeechKit
    - Бот отправляет текст в качестве запроса в YandexGPT
    - Сгенерированный YandexGPT ответ бот направит в SpeechKit для превращения текста в голос
- Бот присылает пользователю ответ в том же формате, в котором пользователь присылал запрос (текст в ответ на текст, голос в ответ на голос)

### **Структура проекта**
```.
├── README.md
├── ssh_key
├── bot.db
├── config.yaml
├── core
│   ├── __init__.py
│   ├── bot.py
│   ├── database.py
│   ├── gpt.py
│   ├── speechkit.py
│   ├── stats.py 
│   └── utils.py
├── logs
│   ├── latest.log
├── .gitignore
├── messages.yaml
├── requirements.txt
└── start.py
```

### **Настройка**
1. Склонируйте этот репозиторий 
```
git clone https://github.com/Mag329/YandexVoiceAssist.git
```
2. Установите все необходимые зависимости, указанные в `requirements.txt`
```
pip install -r requirements.txt
```
3. Заполните файл `config.yaml`
4. При необходимости измените `messages.yaml`
5. Запустите бота с помощью команды 
```
python3 start.py
```
6. Для использования статистики, необходимо запустить на своем сервере сайт из репозитория [BotStats](https://github.com/Mag329/BotStats)

## Использование
- /start — запустить бота
- /help — список доступных команд
- Лимит — отправка доступных токенов, символов и блоков 
- Очистить историю - очистка истории разговора с GPT
- /test — включить режим проверки распознавания и синтеза
- /debug — получить файл с логами


### **Использовано**
![Python](https://img.shields.io/badge/Python-blue?style=for-the-badge)  
![YandexGPT](https://img.shields.io/badge/YandexGPT-DD0031?style=for-the-badge)  
![SpeechKit](https://img.shields.io/badge/SpeechKit-orange?style=for-the-badge)  
![Telebot](https://img.shields.io/badge/Telebot-lightgray?style=for-the-badge)  