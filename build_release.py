"""Build an artifact from a clean, audited commit; never zip the working tree."""
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parent


def git(*args):
    return subprocess.check_output(['git', '-C', str(ROOT), *args], text=True).strip()


if __name__ == '__main__':
    if git('status', '--porcelain'):
        raise SystemExit('Commit or resolve changes before building a release.')
    for name in git('ls-files').splitlines():
        path = Path(name)
        if ((path.name.startswith('.env') and path.name != '.env.example') or
                path.suffix in {'.zip', '.sqlite3', '.pem', '.key'} or '.git' in path.parts):
            raise SystemExit('Private file found in release index: ' + name)
    commit = git('rev-parse', 'HEAD')
    target = ROOT.parent / 'InstrumentPSK-artifacts' / (commit + '.tar')
    target.parent.mkdir(exist_ok=True)
    subprocess.run(['git', '-C', str(ROOT), 'archive', '--format=tar',
                    '-o', str(target), commit], check=True)
    print(target)
