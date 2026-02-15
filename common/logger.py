import logging
from logging.handlers import TimedRotatingFileHandler

def init_logger(name:str, log_location:str) -> logging.Logger:
    # Create a logger
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    # Create a file handler
    #fh = logging.FileHandler('errors.log', encoding='utf-8')
    fh = TimedRotatingFileHandler(log_location, encoding='utf-8', when="D", interval=1, backupCount=30)
    fh.setLevel(logging.INFO)

    # Create a console handler
    ch = logging.StreamHandler()
    ch.setLevel(logging.ERROR)

    # Create a formatter
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    fh.setFormatter(formatter)
    ch.setFormatter(formatter)

    # Add handlers to the logger
    logger.addHandler(fh)
    logger.addHandler(ch)

    return logger