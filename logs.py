import logging


class Logger:
    logger = None

    @classmethod
    def init_logger(cls):
        logging.basicConfig(level=logging.INFO,
                            format='%(levelname)s - %(message)s')

        cls.logger = logging.getLogger()

    @classmethod
    def log(cls, log_type, author, text) -> bool:
        message = f"{author} | {text}"
        logger  = cls.logger

        if log_type == "exception":
            logger.exception(message)
        elif log_type == "info":
            logger.info(message)
        elif log_type == "debug":
            logger.debug(message)
        elif log_type == "warning":
            logger.warning(message)
        elif log_type == "error":
            logger.error(message)
        elif log_type == "critical":
            logger.critical(message)
        else:
            return False

        return True
