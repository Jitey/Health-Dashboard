# logger_config.py
import logging

class ColoredFormatter(logging.Formatter):
    COLORS = {
        "DEBUG": "\033[92m",   # Vert
        "INFO": "\033[94m",    # Bleu
        "WARNING": "\033[93m", # Jaune
        "ERROR": "\033[91m",   # Rouge
        "CRITICAL": "\033[95m" # Magenta
    }
    RESET = "\033[0m"

    def format(self, record):
        # Crée une variable locale pour l'affichage coloré
        colored_levelname = f"{self.COLORS.get(record.levelname, self.RESET)}{record.levelname}{self.RESET}"
        # Sauvegarde l’original
        original_levelname = record.levelname
        # Remplace temporairement pour le format
        record.levelname = colored_levelname
        result = super().format(record)
        # Restaure l’original pour les autres handlers
        record.levelname = original_levelname
        return result

    def formatException(self, ei):
        return ""  # ignore complètement la trace
    
class FileFormatter(logging.Formatter):
    def formatException(self, ei):
        return ""  # ignore complètement la trace


def set_consol_handler(logger: logging.Logger, log_format: str, date_format: str):
    console_handler = logging.StreamHandler()
    # console_handler.setFormatter(ColoredFormatter(fmt=log_format, datefmt=date_format))
    console_handler.setFormatter(ColoredFormatter(
        fmt='\033[90m\033[1m%(asctime)s\033[0m [%(levelname)s]   %(message)s',
        datefmt=date_format
    ))
    logger.addHandler(console_handler)



def set_file_handler(logger: logging.Logger, log_format: str, date_format: str):
    file_handler = logging.FileHandler("logs.log")
    file_handler.setFormatter(FileFormatter(fmt=log_format, datefmt=date_format))
    logger.addHandler(file_handler)



def set_error_handler(logger: logging.Logger, log_format: str, date_format: str):
    error_handler = logging.FileHandler("errors.log")
    error_handler.setLevel(logging.WARNING)
    error_handler.setFormatter(logging.Formatter(
        fmt="%(asctime)s %(levelname)-8s %(name)s: %(message)s\n\t%(exc_info)s",
        datefmt=date_format
    ))
    logger.addHandler(error_handler)



def setup_logger(name="Dasboard") -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    logger.propagate = False

    date_format = "%Y-%m-%d %H:%M:%S"
    log_format = "%(asctime)s %(levelname)-8s %(message)s"

    # ⚡ Ajoute le console handler seulement s'il n'existe pas déjà
    if not any(isinstance(h, logging.StreamHandler) for h in logger.handlers):
        set_consol_handler(logger, log_format, date_format)

    # File handler général
    if not any(isinstance(h, logging.FileHandler) and h.baseFilename.endswith("logs.log") for h in logger.handlers):
        set_file_handler(logger, log_format, date_format)

    # File handler pour erreurs uniquement
    if not any(isinstance(h, logging.FileHandler) and h.baseFilename.endswith("errors.log") for h in logger.handlers):
        set_error_handler(logger, log_format, date_format)


    return logger