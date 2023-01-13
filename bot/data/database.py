from os import getenv as os_getenv
from urllib.parse import urlparse as urllib_parse_urlparse

import psycopg2

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
                        FOREIGN KEY (main_category_name, sub_category_name) REFERENCES category(main_category_name, sub_category_name)
                    );
                    """
                )

                connection.commit()
            except (Exception, psycopg2.DatabaseError) as ex:
                Logger.log("exception", "Database.create_tables",
                           f"An exception occurred while trying to create a table: \n{ex}")

                return_value = 2
        else:
            Logger.log("error", "Database.create_tables", f"Couldn't get cursor required to create tables")

            return_value = 1

        return return_value

    @classmethod
    def get_categories(cls) -> (list, bool):
        categories = []

        cursor, iscursor = Database.get_cursor()

        if iscursor:
            cursor: psycopg2._psycopg.cursor

            try:
                cursor.execute("SELECT main_category_name FROM category")

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
                cursor.execute("SELECT sub_category_name FROM category WHERE main_category_name = %s", (main_category_name,))

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

    @classmethod
    def get_number_of_groups(cls, main_category_name: str, sub_category_name: str = None) -> int:
        cursor, iscursor = Database.get_cursor()

        if iscursor:
            cursor: psycopg2._psycopg.cursor

            try:
                if sub_category_name is None:
                    cursor.execute("SELECT COUNT(*) FROM category WHERE main_category_name = %s", (main_category_name,))
                else:
                    cursor.execute("SELECT COUNT(*) FROM category "
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
                cursor.execute("SELECT * FROM chat WHERE main_category_name = %s", (main_category_name,))
            else:
                cursor.execute(
                    "SELECT * FROM chat "
                    "WHERE main_category_name = %s "
                    "AND sub_category_name = %s",
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
