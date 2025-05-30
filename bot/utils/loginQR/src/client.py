import os
from .config import APP_HASH, APP_ID
from pyrogram import Client
from .Colored import ColoredArgParser
from .args import args as Args

SESSIONS_DIR = "sessions"

if not os.path.exists(SESSIONS_DIR):
    os.makedirs(SESSIONS_DIR)

parser = ColoredArgParser()
for arg in Args:
    parser.add_argument(
        arg['short_name'],
        arg['long_name'],
        help=arg['help'],
        type=arg['type']
    )
args = parser.parse_args()

session_path = os.path.join(SESSIONS_DIR, args.session_name or "pyrogram")

app = Client(session_path, api_id=APP_ID, api_hash=APP_HASH)