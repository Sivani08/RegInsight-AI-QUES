"""Provision an individual account using an operator-supplied hidden access key."""
import argparse
import getpass
import uuid
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backend.api.identity import digest
from backend.database.postgres import connection


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--name',required=True)
    parser.add_argument('--role',choices=('analyst','reviewer','admin'),default='analyst')
    args=parser.parse_args()
    key=getpass.getpass('Individual access key (at least 32 characters): ')
    if len(key)<32 or key!=getpass.getpass('Confirm access key: '):
        raise SystemExit('Use matching access keys of at least 32 characters.')
    identifier=str(uuid.uuid4())
    with connection() as current:
        current.execute('INSERT INTO users(id,name,role,key_digest) VALUES (%s,%s,%s,%s)',
                        (identifier,args.name,args.role,digest(key)))
    print('Created account',identifier,'with role',args.role)


if __name__=='__main__':
    main()
