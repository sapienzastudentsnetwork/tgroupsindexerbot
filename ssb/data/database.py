from os import getenv as os_getenv
from urllib.parse import urlparse as urllib_parse_urlparse

import psycopg2
from telegram.ext import ContextTypes

from ssb.ui.menus import Menus
from ssb.logs import Logger


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
                # directory
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS directory (
                        id SERIAL PRIMARY KEY,
                        i18n_it_name VARCHAR(255) NOT NULL,
                        i18n_en_name VARCHAR(255),
                        parent_id INT,
                        FOREIGN KEY (parent_id) REFERENCES directory(id)
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
                        directory_id INT,
                        created_at TIMESTAMP DEFAULT now(),
                        updated_at TIMESTAMP DEFAULT now(),
                        FOREIGN KEY (directory_id) REFERENCES directory(id)
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
    cached_account_records = {}

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
        if chat_id not in cls.cached_account_records:
            cursor, iscursor = Database.get_cursor()

            if iscursor:
                cursor: psycopg2._psycopg.cursor

                try:
                    cursor.execute("SELECT * FROM account WHERE chat_id = %s", (chat_id,))

                    account_record = cursor.fetchone()

                    if account_record is not None:
                        columns = [desc[0] for desc in cursor.description]
                        user_data = dict(zip(columns, account_record))

                        cls.cached_account_records[chat_id] = user_data

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
            return cls.cached_account_records[chat_id], True


class DirectoryTable:
    CATEGORIES_ROOT_DIR_ID = 1

    cached_directory_records = {}

    cached_sub_directories = {}

    @classmethod
    def get_directory_data(cls, directory_id: int):
        if directory_id not in cls.cached_directory_records:
            cursor, iscursor = Database.get_cursor()

            if iscursor:
                cursor: psycopg2._psycopg.cursor

                try:
                    cursor.execute("SELECT * FROM directory WHERE id = %s", (directory_id,))

                    directory_record = cursor.fetchone()

                    if directory_record is not None:
                        columns = [desc[0] for desc in cursor.description]

                        directory_data = dict(zip(columns, directory_record))

                        cls.cached_directory_records[directory_id] = directory_data

                        return directory_data, True
                    else:
                        return {}, False

                except (Exception, psycopg2.DatabaseError) as ex:
                    Logger.log("exception", "Database.get_directory_data",
                               f"An exception occurred while trying to get directory name for directory "
                               f"having id equal to '{directory_id}': \n{ex}")

                    return {}, False

            else:
                Logger.log("error", "Database.get_directory_data", f"Couldn't get cursor required to get directory name")

                return {}, False
        else:
            return cls.cached_directory_records[directory_id], True

    @classmethod
    def get_sub_directories(cls, parent_id: int) -> (dir, bool):
        if parent_id not in cls.cached_sub_directories:
            cursor, iscursor = Database.get_cursor()

            if iscursor:
                cursor: psycopg2._psycopg.cursor

                try:
                    cursor.execute("SELECT * FROM directory WHERE parent_id = %s", (parent_id,))

                    directories_records = cursor.fetchall()

                    if directories_records is not None:
                        columns = [desc[0] for desc in cursor.description if desc[0] != "id"]

                        sub_directories = {directory_record[0]: dict(zip(columns, directory_record[1:])) for directory_record in directories_records}

                        cls.cached_sub_directories[parent_id] = sub_directories

                        return sub_directories, True
                    else:
                        return {}, True

                except (Exception, psycopg2.DatabaseError) as ex:
                    Logger.log("exception", "Database.get_sub_directories",
                               f"An exception occurred while trying to get sub-directories of "
                               f"directory with parent_id equal to '{parent_id}': \n{ex}")

                    return {}, False

            else:
                Logger.log("error", "Database.get_sub_directories", f"Couldn't get cursor required to get sub-directories")

                return {}, False
        else:
            return cls.cached_sub_directories[parent_id], True


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
                Logger.log("exception", "Database.get_number_of_groups",
                           f"An exception occurred while trying to get the number of groups in "
                           f"'{main_category_name} > {sub_category_name}': \n{ex}")

                return -1

        else:
            Logger.log("error", "Database.get_number_of_groups",
                       f"Couldn't get cursor required to get the number of groups")

            return -1

    @classmethod
    def get_groups(cls, directory_id: int) -> (dict, bool):
        cursor, iscursor = Database.get_cursor()

        if iscursor:
            cursor: psycopg2._psycopg.cursor

            cursor.execute("SELECT * FROM chat "
                           "WHERE directory_id = %s "
                           "ORDER BY title ASC", (directory_id,))

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
    def get_active_session_menu_message_id(cls, chat_id: int) -> int:
        if chat_id in cls.active_chat_sessions:
            return cls.active_chat_sessions[chat_id]
        else:
            return -1

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

                    from ssb.handlers.queries import Queries
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