import time
from telegram import ReplyKeyboardMarkup, Update
import logging
import os
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
from notion_client import Client
from keep_alive import keep_alive

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s — %(levelname)s — %(message)s",
    handlers=[logging.StreamHandler()]
)


logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
NOTION_TOKEN = os.environ["NOTION_TOKEN"]
DATABASE_ID = os.environ["DATABASE_ID"]

notion = Client(auth=NOTION_TOKEN)
user_active_books = {}


def find_book_page_id(book_title):
    response = notion.databases.query(database_id=DATABASE_ID,
                                      filter={
                                          "property": "Название",
                                          "rich_text": {
                                              "contains": book_title
                                          }
                                      })
    results = response.get("results")
    if results:
        return results[0]["id"]
    return None


def create_quote_page(book_page_id, quote_text):
    book_page = notion.pages.retrieve(page_id=book_page_id)
    props = book_page.get("properties", {})

    quote_url = None
    rich_text_field = props.get("Цитаты", {}).get("rich_text", [])
    for item in rich_text_field:
        if "link" in item.get("text", {}):
            quote_url = item["text"]["link"]["url"]

    if not quote_url:
        new_quote_page = notion.pages.create(parent={
            "type": "page_id",
            "page_id": book_page_id
        },
                                             properties={
                                                 "title": [{
                                                     "type": "text",
                                                     "text": {
                                                         "content": "Цитаты"
                                                     }
                                                 }]
                                             },
                                             children=[])
        quote_page_id = new_quote_page["id"]
        quote_url = f"https://www.notion.so/{quote_page_id.replace('-', '')}"

        notion.pages.update(page_id=book_page_id,
                            properties={
                                "Цитаты": {
                                    "type":
                                    "rich_text",
                                    "rich_text": [{
                                        "type": "text",
                                        "text": {
                                            "content": "Цитаты →",
                                            "link": {
                                                "url": quote_url
                                            }
                                        }
                                    }]
                                }
                            })
    else:
        quote_page_id = quote_url.split("/")[-1]
        quote_page_id = f"{quote_page_id[:8]}-{quote_page_id[8:12]}-{quote_page_id[12:16]}-{quote_page_id[16:20]}-{quote_page_id[20:]}"

    notion.blocks.children.append(block_id=quote_page_id,
                                  children=[{
                                      "object": "block",
                                      "type": "bulleted_list_item",
                                      "bulleted_list_item": {
                                          "rich_text": [{
                                              "type": "text",
                                              "text": {
                                                  "content": quote_text
                                              }
                                          }]
                                      }
                                  }])


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [["/book", "/quotes"], ["/current", "/reset"],
                ["/status", "/help"]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(
        "Привет! Отправь мне цитату — я добавлю её в Notion 📚\n\nКоманды:",
        reply_markup=reply_markup)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🛠 *Справка по командам*\n\n"
        "📌 *Работа с книгой:*\n"
        "📚 /book <название> — выбрать активную книгу\n"
        "📖 /current — показать текущую книгу\n"
        "🗑 /reset — сбросить выбранную книгу\n\n"
        "📝 *Цитаты:*\n"
        "💬 /quotes — показать все цитаты из книги\n"
        "✍️ Просто отправь текст — он добавится как цитата\n\n"
        "🔧 *Система:*\n"
        "⚙️ /status — проверить, в сети ли бот\n"
        "🟰 /start — показать главное меню",
        parse_mode="Markdown")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        text = update.message.text.strip()
        user_id = str(update.message.from_user.id)
        active_book = user_active_books.get(user_id, "Без категории")
        book_page_id = find_book_page_id(active_book)

        if not book_page_id:
            await update.message.reply_text(
                f"⚠️ Книга '{active_book}' не найдена в Notion.")
            return

        create_quote_page(book_page_id, text)
        await update.message.reply_text("✅ Цитата добавлена!")
    except Exception as e:
        await update.message.reply_text(f"🚫 Ошибка: {e}")

    except Exception as e:
        logger.error(f"❌ Ошибка в обработке сообщения: {e}")
        await update.message.reply_text(f"🚫 Ошибка: {e}")


async def set_book(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    args = context.args
    if not args:
        await update.message.reply_text(
            "Укажи название книги после команды /book")
        return
    book_title = " ".join(args)
    user_active_books[user_id] = book_title
    await update.message.reply_text(
        f"📚 Активная книга установлена: {book_title}")


async def reset_book(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    user_active_books.pop(user_id, None)
    await update.message.reply_text("🔄 Активная книга сброшена.")


async def get_quotes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    active_book = user_active_books.get(user_id)
    if not active_book:
        await update.message.reply_text(
            "⚠️ Сначала выбери книгу командой /book.")
        return

    book_page_id = find_book_page_id(active_book)
    if not book_page_id:
        await update.message.reply_text(
            f"⚠️ Книга '{active_book}' не найдена в Notion.")
        return

    book_page = notion.pages.retrieve(page_id=book_page_id)
    props = book_page.get("properties", {})
    quote_url = None
    rich_text_field = props.get("Цитаты", {}).get("rich_text", [])
    for item in rich_text_field:
        if "link" in item.get("text", {}):
            quote_url = item["text"]["link"]["url"]

    if not quote_url:
        await update.message.reply_text("⛔ У этой книги ещё нет цитат.")
        return

    quote_page_id = quote_url.split("/")[-1]
    quote_page_id = f"{quote_page_id[:8]}-{quote_page_id[8:12]}-{quote_page_id[12:16]}-{quote_page_id[16:20]}-{quote_page_id[20:]}"
    blocks = notion.blocks.children.list(block_id=quote_page_id).get(
        "results", [])
    quotes = []
    for block in blocks:
        if block["type"] == "bulleted_list_item":
            texts = block["bulleted_list_item"]["rich_text"]
            content = "".join([t["text"]["content"] for t in texts])
            quotes.append(content)

    if quotes:
        reply = "\n\n".join(f"• {q}" for q in quotes)
        await update.message.reply_text(
            f"📖 Цитаты из книги *{active_book}*:\n\n{reply}",
            parse_mode="Markdown")
    else:
        await update.message.reply_text("😕 Цитаты ещё не добавлены.")


async def current_book(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    book = user_active_books.get(user_id)
    if book:
        await update.message.reply_text(f"📖 Сейчас выбрана книга: *{book}*",
                                        parse_mode="Markdown")
    else:
        await update.message.reply_text(
            "📖 Книга не выбрана. Используй /book, чтобы установить её.")


async def bot_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🟢 Бот в сети и работает!")


def main():
    keep_alive()
    logger.info("🚀 Бот запускается...")

    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("book", set_book))
    app.add_handler(CommandHandler("current", current_book))
    app.add_handler(CommandHandler("reset", reset_book))
    app.add_handler(CommandHandler("quotes", get_quotes))
    app.add_handler(CommandHandler("status", bot_status))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("✅ Бот успешно запущен. Ожидаю команды...")

    app.run_polling()

    logger.warning("⚠️ app.run_polling() завершилось. Бот отключён!")

    while True:
        logger.debug("🔄 Бот живой (ожидание)...")
        time.sleep(60)


if __name__ == "__main__":
    main()

if __name__ == "__main__":
    main()
