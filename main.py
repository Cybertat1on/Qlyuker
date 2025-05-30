import asyncio
from contextlib import suppress
from bot.core.launcher import process
from os import system, name as os_name, environ
import os

def is_docker() -> bool:
    path = '/proc/self/cgroup'
    return os.path.exists('/.dockerenv') or (os.path.isfile(path) and any('docker' in line for line in open(path)))

def can_set_title() -> bool:
    if is_docker():
        return False
    
    term = environ.get('TERM', '')
    if term in ('', 'dumb', 'unknown'):
        return False
        
    return True

def set_window_title(title: str) -> None:
    if not can_set_title():
        return     
    try:
        if os_name == 'nt':
            system(f'title {title}')
        else:
            print(f'\033]0;{title}\007', end='', flush=True)
    except Exception:
        pass

async def main() -> None:
    await process()

if __name__ == '__main__':
    set_window_title('NAME')
    with suppress(KeyboardInterrupt):
        asyncio.run(main())
