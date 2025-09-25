from functools import wraps
import time
import json
from pathlib import Path
parent_folder = Path(__file__).resolve().parent
import logging
from icecream import ic



class JsonFile:
    def write(content: dict | list, file_name: str):
        with open(f"{file_name}.json",'w') as f:
            json.dump(content,f,indent=4)
    
    def read(file_name: str)->dict | list:
        with open(f"{file_name}.json",'r') as f:
            return json.load(f)
    
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
                logging.error(f"{error.__class__.__name__} {error}")
                logging.warning(data)
                logging.warning(keys)
                logging.warning(key)
        return data


from datetime import datetime as dt
class Update:
    def get_last_date():
        last_save = JsonFile.read(f"{parent_folder}/parametres/sauvegarde")
        return dt.strptime(JsonFile.safe_get(last_save, 'last_update.date'), "%Y-%m-%d %H:%M:%S.%f").date()

    def write_date():
        from datetime import datetime as dt
        save = {'last_update': {
            "date": str(dt.now())
            }
        }
        JsonFile.write(save,f"{parent_folder}/parametres/sauvegarde")


def timing_performance(func):
    @wraps(func)
    def wrapper(*args,**kwargs):
        logging.info(f"Début {func.__name__}")
        start = time.perf_counter()
        res = func(*args,**kwargs)
        logging.info(f"Fin {func.__name__} {time.perf_counter()-start:.3f}s")
        return res
    return wrapper