import turso.sync
from turso import IntegrityError
import libsql
from settings import logger
from typing import Any
from utility import retry

from icecream import ic

    

class NotNullConstraintError(IntegrityError):
    def __init__(self, original_error: Exception, table: str = None, columns: list[str] = None, values: list = None):
        msg = str(original_error)
        column_error = msg[27:-5]
        
        idx_error = columns.index(column_error)
        col_msg = f"{column_error}: {values[idx_error]}"
            
        self.message = f"Veuillez fournir les valeurs manquantes - {msg} \nValues: {values}"
        

    
        # Appelle le constructeur parent avec le message remodelé
        super().__init__(self.message)
    
    def __str__(self):
        return self.message

class UniqueConstraintError(IntegrityError):
    def __init__(self, original_error: Exception, table: str = None, columns: list[str] = None, values: list = None):
        msg = str(original_error)
        columns_error = msg[26:-5].split(".")[1]
        
        if '(' in columns_error:
            col_list = columns_error[1:-1].split(", ")
            idxs = [columns.index(col) for col in col_list]
            col_msg = ", ".join([f"{col}: {values[columns.index(col)]}" for col in col_list])
        else:
            idx_error = columns.index(columns_error)
            col_msg = f"{columns_error}: {values[idx_error]}"
            
        self.message = f"{original_error} - {col_msg}"
        

    
        # Appelle le constructeur parent avec le message remodelé
        super().__init__(self.message)
    
    def __str__(self):
        return self.message




class TursoDB():
    def __init__(self, path: str, remote_url: str, auth_token: str) -> None:
        self.conn = turso.sync.connect(path=path, remote_url=remote_url, auth_token=auth_token)
      
    
    @retry
    def sync(self) -> None:
        changed = self.conn.pull()
        logger.info(f"Pulled: {changed}")  # True if there were new remote changes

        stats = self.conn.stats()
        logger.info(f"Network received (bytes): {stats.network_received_bytes}")
        # conn.checkpoint()  # compact local WAL after many writes
        
        
    def insert(self, table: str, values: dict|list, columns: list[str]=None) -> None:
        if isinstance(values, dict):
            return self._insert_dict(table, values)
        
        elif isinstance(values, (list, tuple)) and columns is not None:
            return self._insert_list(table, values, columns)
        
        else:
            raise ValueError("Values must be a dict or a list with specified columns.")
    
    def _insert_dict(self, table: str, values: dict[str, Any]) -> None:
        keys = values.keys()
        
        columns = ', '.join(keys)
        placeholders = ', '.join(':' + str(key) for key in keys)
            
        try:
            cur = self.conn.execute(f"INSERT INTO {table} ({columns}) VALUES ({placeholders})")
            self.conn.commit()
            self.conn.push()
            
            return cur.lastrowid
        except IntegrityError as e:
            if "NOT NULL constraint failed" in str(e):
                self.conn.rollback()
                logger.error(f"IntegrityError: {e} \nValues: {values}")
            else:
                raise e
        
    def _insert_list(self, table: str, values: list|tuple, columns: list[str]) -> None:
        placeholders = ', '.join('?' * len(values))
        
        try:
            cur = self.conn.execute(f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({placeholders})", values)
            self.conn.commit()
            self.conn.push()

            return cur.lastrowid
        except IntegrityError as e:
            self.conn.rollback()
            msg = str(e)
            
            if "NOT NULL constraint failed" in msg:
                raise NotNullConstraintError(e, table, columns, values)
            elif "UNIQUE constraint failed" in msg:
                raise UniqueConstraintError(e, table, columns, values)
            else:
                raise e
        
   
   
   
   
        
class TursoCloud():
    def __init__(self, path, remote_url: str, auth_token: str) -> None:
        self.conn = self._init_conn(path, remote_url, auth_token)
        
        
    def _init_conn(self, path, remote_url: str, auth_token: str) -> libsql.Connection:
        if remote_url and auth_token:
            conn = libsql.connect(path, sync_url=remote_url, auth_token=auth_token)
            conn.sync()
            
            return conn
        else:
            return libsql.connect(path)