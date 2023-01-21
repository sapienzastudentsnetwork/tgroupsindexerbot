class GlobalVariables:
    queries_fd = "  "

    stats_accounts_count = -1

    @classmethod
    def set_accounts_count(cls, accounts_count):
        cls.stats_accounts_count = accounts_count

    @classmethod
    def increment_accounts_count(cls):
        cls.stats_accounts_count += 1
