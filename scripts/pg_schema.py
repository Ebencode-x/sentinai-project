"""Create or drop a throwaway Postgres schema and print a URL that points at it."""

import sys

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url


def main(action: str, base: str, schema: str) -> None:
    engine = create_engine(base, isolation_level="AUTOCOMMIT")
    with engine.connect() as conn:
        if action == "create":
            conn.execute(text(f'CREATE SCHEMA "{schema}"'))
        else:
            conn.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
    engine.dispose()
    if action == "create":
        url = make_url(base).update_query_dict({"options": f"-csearch_path={schema}"})
        print(url.render_as_string(hide_password=False))


main(*sys.argv[1:4])
