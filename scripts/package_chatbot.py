"""Package portable source/assets; database backups are separate operator artifacts."""
import argparse
import zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
EXCLUDED={'node_modules','.venv','__pycache__','.pytest_cache','.git','runtime','work','exports','postgres_data','pgdata'}

def package(destination):
    destination=Path(destination).resolve()
    destination.parent.mkdir(parents=True,exist_ok=True)
    count=0
    with zipfile.ZipFile(destination,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as archive:
        for path in sorted(ROOT.rglob('*')):
            if not path.is_file() or path.is_symlink() or any(part in EXCLUDED for part in path.relative_to(ROOT).parts):
                continue
            if path==destination or path.suffix in ('.zip','.log','.pyc') or any(
                ending in path.name.lower() for ending in ('.db', '.sqlite', '.sqlite3')):
                continue
            if path.name.startswith('.env') and path.name!='.env.example':
                continue
            archive.write(path,Path('RegInsight-AI')/path.relative_to(ROOT))
            count+=1
    with zipfile.ZipFile(destination) as archive:
        if archive.testzip():
            raise ValueError('Archive integrity verification failed')
    return count

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',required=True)
    args=parser.parse_args()
    print('Verified archive with',package(args.output),'files')
