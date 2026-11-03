"""Import this first: it loads the local .env before settings is built.

settings reads os.getenv when src.core.config is imported, so .env has to be
loaded before any other src module is imported. src/main.py keeps this as its
first src import and tests/test_import_order.py guards that.
"""

from src.core.env import load_env

load_env()
