import json

from bot.settings import Settings


class Database:
    data_structure: {}

    @classmethod
    def import_data(cls, file_path: str) -> None:
        from bot.handlers.queries import Queries

        with open(file_path, "r") as inputFile:
            cls.data_structure = json.load(inputFile)

            explore_categories_query_string = f"cd"

            Queries.register_query(explore_categories_query_string)

            for category_name, category_data_dict in cls.data_structure.items():
                explore_category_query_string = f"cd{Settings.queries_fd}{category_name}"

                cls.data_structure[category_name]["number_of_groups"] = len(cls.data_structure[category_name]["groups"].keys())

                Queries.register_query(explore_category_query_string)

                category_data_dict: dict
                for sub_category_name, sub_category_data in category_data_dict["sub_categories"].items():
                    explore_sub_category_query_string = f"cd{Settings.queries_fd}{category_name}{Settings.queries_fd}{sub_category_name}"

                    number_of_sub_category_groups = \
                        len(cls.data_structure[category_name]["sub_categories"][sub_category_name]["groups"].keys())

                    cls.data_structure[category_name]["sub_categories"][sub_category_name]["number_of_groups"] = \
                        number_of_sub_category_groups

                    cls.data_structure[category_name]["number_of_groups"] += number_of_sub_category_groups

                    Queries.register_query(explore_sub_category_query_string)
