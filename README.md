# QuoteToNotion Telegram Bot

Telegram-бот для отправки цитат прямо в базу данных Notion. Поддерживает выбор книги, сохранение цитат на подстранице, просмотр всех цитат.

ссылка на список книг в Notion: https://surl.li/zaldft

**Возможности**

- Выбор активной книги из таблицы в Notion
- Добавление цитаты простым сообщением в Telegram
- Просмотр всех цитат из книги
- Проверка статуса бота

**Команды**

* /start — Показать главное меню
* /book <название> — Выбрать книгу 
* /current — Показать текущую выбранную книгу
* /reset — Сбросить активную книгу
* /quotes — Показать все цитаты из выбранной книги
* /status — Проверить, в сети ли бот
* /help — Справка по командам

**Используемые технологии**

Python 3.10+

Telegram Bot API (python-telegram-bot)

Notion API (notion-client)

Railway для хостинга