
import json
from logs.logger_config import setup_logger

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
        original_data = data
        keys = dot_chained_keys.split('.')
        for key in keys:
            try:
                data = data[int(key)] if isinstance(data,list) else data[key]
            except (KeyError, TypeError, IndexError, ValueError) as error:
                logger.error(f"{error.__class__.__name__} {error}")
                JsonFile.write(original_data, "error_data")
                logger.warning(original_data)
                logger.warning(dot_chained_keys)
                logger.warning(key)
        return data
