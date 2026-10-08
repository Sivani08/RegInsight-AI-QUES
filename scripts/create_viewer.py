"""Provision a DBeaver reader with explicit business/audit grants, excluding secrets."""
import getpass
from pathlib import Path
import sys

from psycopg import sql

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.database.postgres import connection


def create_viewer(password):
    if len(password) < 32:
        raise ValueError('Use a viewer password of at least 32 characters')
    with connection() as current:
        if not current.execute("SELECT 1 FROM pg_roles WHERE rolname='reginsight_viewer'").fetchone():
            current.execute('CREATE ROLE reginsight_viewer LOGIN')
        current.execute(sql.SQL('ALTER ROLE reginsight_viewer WITH NOSUPERUSER NOCREATEDB '
                               'NOCREATEROLE NOREPLICATION PASSWORD {}').format(sql.Literal(password)))
        current.execute('REVOKE ALL ON ALL TABLES IN SCHEMA public, staging FROM reginsight_viewer')
        current.execute('GRANT USAGE ON SCHEMA public, staging TO reginsight_viewer')
        current.execute('''GRANT SELECT ON inspections, staging.inspection_source,
            staging.citation_source, staging.annual_source, staging.annual_metadata,
            chat_sessions, chat_messages, chat_retrieval_events, chat_message_evidence,
            chat_message_citations, chat_tool_executions, admin_chat_history, admin_chat_evidence
            TO reginsight_viewer''')
        current.execute('ALTER ROLE reginsight_viewer SET default_transaction_read_only = on')


def main():
    password = getpass.getpass('Viewer password (at least 32 characters): ')
    if password != getpass.getpass('Confirm viewer password: '):
        raise SystemExit('Passwords do not match')
    create_viewer(password)
    print('Created read-only reginsight_viewer. Keep the password in your password manager.')


if __name__ == '__main__':
    main()
