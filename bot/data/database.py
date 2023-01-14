from os import getenv as os_getenv
from urllib.parse import urlparse as urllib_parse_urlparse

import psycopg2
from telegram.ext import ContextTypes

from bot.ui.menus import Menus
from logs import Logger


class Database:
    connection = None
    POSTGRE_URI = os_getenv("DATABASE_URL")

    @classmethod
    def init_db(cls):
        try:
            result = urllib_parse_urlparse(cls.POSTGRE_URI)

            connection = psycopg2.connect(
                database=result.path[1:],
                user=result.username,
                password=result.password,
                host=result.hostname,
                port=result.port
            )

            cls.connection = connection

            cls.create_tables()

            return connection

        except (Exception, psycopg2.DatabaseError) as ex:
            Logger.log("exception", "Database.init_db",
                       f"An exception occurred while trying to connect to database: "
                       f"\n{ex}\n\nSHUTTING DOWN THE BOT...")

            exit()

        return None

    @classmethod
    def get_cursor(cls) -> (psycopg2._psycopg.cursor, bool):
        try:
            cursor = cls.connection.cursor()

            return cursor, True

        except psycopg2.InterfaceError as ie:
            Logger.log("warning", "Database.get_cursor",
                       f"An 'InterfaceError' exception occurred while trying to get connection cursor: \n{ie}"
                       f"\n\nTrying to recover by re-initializing the database")

            try:
                return cls.init_db().cursor(), True

            except (Exception, psycopg2.DatabaseError) as ex:
                Logger.log("critical", "Database.get_cursor",
                           f"An exception occurred while trying to init DB again to get connection cursor: \n{ex}")

                return None, False

        except (Exception, psycopg2.DatabaseError) as ex:
            Logger.log("exception", "Database.get_cursor",
                       f"An exception occurred while trying to get connection cursor: \n{ex}")

            return None, False

    @classmethod
    def create_tables(cls) -> None:
        cursor, iscursor = Database.get_cursor()

        return_value = 0

        if iscursor:
            cursor: psycopg2._psycopg.cursor

            connection = Database.connection
            connection: psycopg2._psycopg.connection

            try:
                # category
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS category (
                        main_category_name VARCHAR(60),
                        sub_category_name VARCHAR(60) DEFAULT '',
                        PRIMARY KEY (main_category_name, sub_category_name)
                    );
                    """
                )

                # chat
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS chat (
                        chat_id BIGINT PRIMARY KEY,
                        title VARCHAR(128),
                        invite_link VARCHAR(38),
                        chat_admins BIGINT[],
                        main_category_name VARCHAR(60),
                        sub_category_name VARCHAR(60) NULL,
                        created_at TIMESTAMP DEFAULT now(),
                        updated_at TIMESTAMP DEFAULT now(),
                        FOREIGN KEY (main_category_name, sub_category_name) 
                        REFERENCES category(main_category_name, sub_category_name)
                    );
                    """
                )

                # account
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS account (
                        chat_id BIGINT PRIMARY KEY,
                        created_at TIMESTAMP DEFAULT now(),
                        pref_lang_code VARCHAR(4),
                        is_admin BOOLEAN DEFAULT false,
                        can_view_groups BOOLEAN DEFAULT true,
                        can_add_groups BOOLEAN DEFAULT true,
                        can_modify_groups BOOLEAN DEFAULT true
                    );
                    """
                )

                # session
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS session (
                        chat_id BIGINT PRIMARY KEY,
                        created_at TIMESTAMP DEFAULT now(),
                        menu_message_id BIGINT
                    );
                    """

                )

                connection.commit()
            except (Exception, psycopg2.DatabaseError) as ex:
                Logger.log("exception", "Database.create_tables",
                           f"An exception occurred while trying to create a table: \n{ex}")

        else:
            Logger.log("error", "Database.create_tables", f"Couldn't get cursor required to create tables")


class AccountTable:
    cached_accounts = {}

    @classmethod
    def create_account_record(cls, chat_id: int) -> bool:
        cursor, iscursor = Database.get_cursor()

        if iscursor:
            try:
                cursor.execute(
                    "INSERT INTO account (chat_id, created_at) "
                    "VALUES (%s, now() AT TIME ZONE 'Europe/Rome')",
                    (chat_id,)
                )

                return True

            except (Exception, psycopg2.DatabaseError) as ex:
                Logger.log("exception", "Database.create_user_record",
                           f"An exception occurred while trying to create account record for '{chat_id}': \n{ex}")

                return False

        else:
            Logger.log("error", "Database.create_user_record", f"Couldn't get cursor required to create account record")

            return False

    @classmethod
    def get_account_record(cls, chat_id: int) -> (dict, bool):
        if chat_id not in cls.cached_accounts:
            cursor, iscursor = Database.get_cursor()

            if iscursor:
                cursor: psycopg2._psycopg.cursor

                try:
                    cursor.execute("SELECT * FROM account WHERE chat_id = %s", (chat_id,))

                    row = cursor.fetchone()

                    if row:
                        columns = [desc[0] for desc in cursor.description]
                        user_data = dict(zip(columns, row))

                        cls.cached_accounts[chat_id] = user_data

                        return user_data, True
                    else:
                        if AccountTable.create_account_record(chat_id):
                            return AccountTable.get_account_record(chat_id)
                        else:
                            return {}, False

                except (Exception, psycopg2.DatabaseError) as ex:
                    Logger.log("exception", "Database.get_user",
                               f"An exception occurred while trying to get account record with '{chat_id}' as chat_id: \n{ex}")

                    return {}, False

            else:
                Logger.log("error", "Database.get_user", f"Couldn't get cursor required to get user")

                return {}, False
        else:
            return cls.cached_accounts[chat_id], True


class CategoriesTable:
    @classmethod
    def get_categories(cls) -> (list, bool):
        categories = []

        cursor, iscursor = Database.get_cursor()

        if iscursor:
            cursor: psycopg2._psycopg.cursor

            try:
                cursor.execute("SELECT DISTINCT main_category_name "
                               "FROM category "
                               "WHERE main_category_name != ''")

                records = cursor.fetchall()

                for record in records:
                    categories.append(record[0])

                return categories, True

            except (Exception, psycopg2.DatabaseError) as ex:
                Logger.log("exception", "Database.get_categories",
                           f"An exception occurred while trying to get categories: \n{ex}")

                return [], False

        else:
            Logger.log("error", "Database.get_categories", f"Couldn't get cursor required to get categories")

            return [], False

    @classmethod
    def get_sub_categories(cls, main_category_name: str) -> (list, bool):
        sub_categories = []

        cursor, iscursor = Database.get_cursor()

        if iscursor:
            cursor: psycopg2._psycopg.cursor

            try:
                cursor.execute(
                    "SELECT sub_category_name FROM category "
                    "WHERE main_category_name = %s "
                    "AND sub_category_name != ''",
                    (main_category_name,)
                )

                records = cursor.fetchall()

                for record in records:
                    sub_categories.append(record[0])

                return sub_categories, True

            except (Exception, psycopg2.DatabaseError) as ex:
                Logger.log("exception", "Database.get_sub_categories",
                           f"An exception occurred while trying to get "
                           f"sub categories of '{main_category_name}': \n{ex}")

                return [], False

        else:
            Logger.log("error", "Database.get_sub_categories", f"Couldn't get cursor required to get sub-categories")

            return [], False


class ChatTable:
    @classmethod
    def get_number_of_groups(cls, main_category_name: str, sub_category_name: str = None) -> int:
        cursor, iscursor = Database.get_cursor()

        if iscursor:
            cursor: psycopg2._psycopg.cursor

            try:
                if sub_category_name is None:
                    cursor.execute("SELECT COUNT(*) FROM chat WHERE main_category_name = %s", (main_category_name,))
                else:
                    cursor.execute("SELECT COUNT(*) FROM chat "
                                   "WHERE main_category_name = %s "
                                   "AND sub_category_name = %s", (main_category_name,sub_category_name))

                return cursor.fetchone()[0]

            except (Exception, psycopg2.DatabaseError) as ex:
                Logger.log("exception", "Database.get_sub_categories",
                           f"An exception occurred while trying to get the number of groups in "
                           f"'{main_category_name} > {sub_category_name}': \n{ex}")

                return -1

        else:
            Logger.log("error", "Database.get_number_of_groups",
                       f"Couldn't get cursor required to get the number of groups")

            return -1

    @classmethod
    def get_groups(cls, main_category_name: str, sub_category_name: str = None) -> (dict, bool):
        cursor, iscursor = Database.get_cursor()

        if iscursor:
            cursor: psycopg2._psycopg.cursor

            if sub_category_name is None:
                cursor.execute("SELECT * FROM chat "
                               "WHERE main_category_name = %s "
                               "AND sub_category_name = ''"
                               "ORDER BY title ASC", (main_category_name,))
            else:
                cursor.execute(
                    "SELECT * FROM chat "
                    "WHERE main_category_name = %s "
                    "AND sub_category_name = %s "
                    "ORDER BY title ASC",
                    (main_category_name, sub_category_name)
               )

            column_names = [desc[0] for desc in cursor.description]
            records = cursor.fetchall()

            groups = {}

            for record in records:
                chat_id = record[0]

                group_data = {}
                for i, column_name in enumerate(column_names):
                    if i == 0:
                        continue
                    group_data[column_name] = record[i]

                groups[chat_id] = group_data

            return groups, True

        else:
            Logger.log("error", "Database.get_groups", f"Couldn't get cursor required to get groups")

            return {}, False


class SessionTable:
    active_chat_sessions = {}

    @classmethod
    def add_session(cls, chat_id: int, latest_menu_message_id: int) -> None:
        cls.active_chat_sessions[chat_id] = latest_menu_message_id

        cursor, iscursor = Database.get_cursor()

        if iscursor:
            cursor: psycopg2._psycopg.cursor

            try:
                connection = Database.connection
                connection: psycopg2._psycopg.connection

                cursor.execute("INSERT INTO session (chat_id, menu_message_id) VALUES (%s, %s)",
                               (chat_id, latest_menu_message_id))
                connection.commit()

            except (Exception, psycopg2.DatabaseError) as ex:
                Logger.log("critical", "Database.add_session",
                           f"An exception occurred while trying to insert '{latest_menu_message_id}' "
                           f"latest_menu_message_id in 'session' table for '{chat_id}': \n{ex}")

        else:
            Logger.log("error", "Database.add_session", f"Couldn't get cursor required to insert session data")

    @classmethod
    def update_session(cls, chat_id: int, new_latest_menu_message_id: int) -> None:
        cls.active_chat_sessions[chat_id] = new_latest_menu_message_id

        cursor, iscursor = Database.get_cursor()

        if iscursor:
            cursor: psycopg2._psycopg.cursor

            try:
                connection = Database.connection
                connection: psycopg2._psycopg.connection

                cursor.execute("UPDATE session SET menu_message_id = %s WHERE chat_id = %s",
                               (new_latest_menu_message_id, chat_id))

                connection.commit()

            except (Exception, psycopg2.DatabaseError) as ex:
                Logger.log("critical", "Database.update_session",
                           f"An exception occurred while trying to update latest_menu_message_id for "
                           f"'{chat_id}' to `{new_latest_menu_message_id}': \n{ex}")

        else:
            Logger.log("error", "Database.update_session", f"Couldn't get cursor required to update session data")

    @classmethod
    async def expire_old_sessions(cls, context: ContextTypes.DEFAULT_TYPE) -> None:
        cursor, iscursor = Database.get_cursor()

        if iscursor:
            cursor: psycopg2._psycopg.cursor

            try:
                connection = Database.connection
                connection: psycopg2._psycopg.connection

                cursor.execute("SELECT chat_id, menu_message_id FROM session")

                records = cursor.fetchall()

                for record in records:
                    chat_id, menu_message_id = record

                    text, reply_markup = Menus.get_expired_session_menu()

                    from bot.handlers.queries import Queries
                    reply_markup = Queries.encode_queries(reply_markup)

                    try:
                        await context.bot.edit_message_text(chat_id=chat_id, message_id=menu_message_id,
                                                            text=text, reply_markup=reply_markup)
                    except Exception:
                        pass

                cursor.execute("DELETE FROM session")

                connection.commit()

            except (Exception, psycopg2.DatabaseError) as ex:
                Logger.log("critical", "Database.expire_old_sessions",
                           f"An exception occurred while trying to expire old sessions: \n{ex}")

        else:
            Logger.log("error", "Database.expire_old_sessions", f"Couldn't get cursor required to expire old sessions")