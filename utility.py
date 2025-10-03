import json
from datetime import datetime
from functools import wraps
from time import perf_counter, perf_counter_ns, time
from logger_config import setup_logger

logger = setup_logger()


class JsonFile:
    @staticmethod
    def write(content: dict | list, path: str):
        """Sauvegarde des données au format json

        Args:
            content (dict | list): Les données à sauvegarder
            path (str): Le chemin du fichier sans l'extension
        """
        with open(f"{path}.json",'w') as f:
            json.dump(content,f,indent=4)
    
    @staticmethod
    def read(path: str)->dict | list:
        """Lecture des données au format json

        Args:
            path (str): Le chemin du fichier sans l'extension

        Returns:
            dict | list: _description_
        """
        with open(f"{path}.json",'r') as f:
            return json.load(f)
    
    @staticmethod
    def safe_get(data: dict | list, dot_chained_keys: str):
        """Renvoie un élément précis de données au format json

        data = {'a':{'b':[{'c':1}]}}
        safe_get(data, 'a.b.0.C') -> 1
        Args:
            data (dict | list): Les données à traiter
            dot_chained_keys (str): Les clés d'accès sous forme de chaine str

        Returns:
            _type_: L'élément cherché
        """
        keys = dot_chained_keys.split('.')
        for key in keys:
            try:
                data = data[int(key)] if isinstance(data,list) else data[key]
            except (KeyError, TypeError, IndexError, ValueError) as error:
                logger.error(f"{error.__class__.__name__} {error}")
                logger.warning(data)
                logger.warning(keys)
                logger.warning(key)
        return data






class HealthRecord:
    def __init__(self, record: dict):
        self.record_type = record.get("type").replace("HKQuantityTypeIdentifier", "")
        self.value = record.get("value")
        self.unit = record.get("unit")
        self.date = record.get("startDate")

    @property
    def date(self):
        return self._date
    @date.setter
    def date(self, value):
        # Convertit la date en format lisible
        self._date = datetime.strptime(value, "%Y-%m-%d %H:%M:%S %z") if value else None
        
    def __str__(self):
        return f"{self.record_type} - {self.value} {self.unit} on {self.date.date() if self.date else 'Unknown'}"

    def __repr__(self):
        return f"HealthRecord(type={self.record_type}, value={self.value}, date={self.date})"



def timer_performance(func):
    @wraps(func)
    def wrapper(*args,**kwargs):
        start = perf_counter()
        res = func(*args,**kwargs)
        logger.info(f"{func.__name__}: {perf_counter() - start:.2e}s")
        return res
    return wrapper

def timer_performance_ns(func):
    @wraps(func)
    def wrapper(*args,**kwargs):
        start = perf_counter_ns()
        res = func(*args,**kwargs)
        logger.info(f"{func.__name__}: {perf_counter_ns() - start:.2e}ns")
        return res
    return wrapper