import logging
import sys
from pyrogram import Client, errors
from .src import args, app, APP_ID, APP_HASH
from rich.logging import RichHandler

FORMAT = "%(message)s"
logging.basicConfig(
    level=logging.WARNING, format=FORMAT, datefmt="[%X]", handlers=[RichHandler()]
)


if args.token:
    app = Client(
        args.session_name or "pyrogram",
        api_id=APP_ID,
        api_hash=APP_HASH,
        bot_token=args.token
    )
    try:
        app.start()
    except (
        errors.AccessTokenInvalid,
        errors.AccessTokenExpired,
        errors.AuthKeyUnregistered
    ) as err:
        sys.exit(print(err))
    me = app.get_me().first_name
    session_string = app.export_session_string()
    app.stop()
    #logging.info(
    #        f"Generated session for {me}"
    #    )
    sys.exit(
    #    print(f'SessionString:\n{session_string}\n\nquitting...')
    )

