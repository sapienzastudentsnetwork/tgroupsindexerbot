from telegram import Update
from telegram.ext import ContextTypes

from bot.data.database import SessionTable
from bot.handlers.queries import Queries
from bot.i18n.locales import Locale
from bot.ui.menus import Menus


class Commands:
    @classmethod
    async def commands_handler(cls, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        bot           = context.bot
        chat_id       = update.effective_chat.id
        query_message = update.message

        if query_message.chat.type == "private":
            command = query_message.text.split()[0][1:]

            if Queries.user_can_perform_action(chat_id, "/" + command):
                locale = Locale(update.effective_user.language_code)

                text, reply_markup = "", None

                if command == "start":
                    text, reply_markup = Menus.get_main_menu(locale)

                elif command == "groups":
                    text, reply_markup = Queries.get_categories(locale)

                if text or reply_markup:
                    reply_markup = Queries.encode_queries(reply_markup)

                    new_message = await bot.send_message(chat_id=chat_id, text=text, reply_markup=reply_markup)

                    try:
                        await bot.delete_message(chat_id=chat_id, message_id=query_message.message_id)
                    except:
                        pass

                    old_latest_menu_message_id = SessionTable.get_active_session_menu_message_id(chat_id)

                    if old_latest_menu_message_id != -1:
                        try:
                            await bot.delete_message(chat_id=chat_id, message_id=old_latest_menu_message_id)
                        except:
                            pass

                        SessionTable.update_session(chat_id, new_message.message_id)
                    else:
                        SessionTable.add_session(chat_id, new_message.message_id)
