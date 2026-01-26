
from functools import wraps
from time import perf_counter, perf_counter_ns, sleep
from logs.logger_config import setup_logger

logger = setup_logger()










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



def retry(func, retries: int=3, delay: float=1.0):
    @wraps(func)
    def wrapper(*args, **kwargs):
        for attempt in range(retries):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                logger.warning(f"Attempt {attempt + 1} failed: {e}. Retrying in {delay} seconds...")
                sleep(delay)
        logger.error(f"All {retries} attempts failed.", exc_info=True)
    return wrapper