"""Run application and LangGraph migrations explicitly before API/worker startup."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from alembic.config import Config
from alembic import command
import psycopg
from sqlalchemy.engine import make_url
from langgraph.checkpoint.postgres import PostgresSaver
from backend.database.postgres import database_url


def migrate():
    command.upgrade(Config('alembic.ini'),'head')
    url=make_url(database_url()).set(drivername='postgresql').render_as_string(hide_password=False)
    with psycopg.connect(url,autocommit=True) as current:
        PostgresSaver(current).setup()
    print('Application and durable checkpoint schemas are ready')


if __name__=='__main__':
    migrate()
