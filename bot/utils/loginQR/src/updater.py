from .config import APP_ID, APP_HASH
from pyrogram import Client, raw, errors, utils
import asyncio
from .utils import check_session, clear_screen, _gen_qr, nearest
import sys

ACCEPTED = False

async def raw_handler(client: Client, update: raw.base.Update, users: list, chats: list):
    if isinstance(update, raw.types.auth.LoginToken) and nearest.nearest_dc != await client.storage.dc_id():
        await check_session(client, dc_id=nearest.nearest_dc)

    if isinstance(update, raw.types.UpdateLoginToken):
        try:
            r = await client.invoke(
                raw.functions.auth.ExportLoginToken(
                    api_id=APP_ID, api_hash=APP_HASH, except_ids=[]
                )
            )
        except errors.exceptions.unauthorized_401.SessionPasswordNeeded as err:
            await client.check_password(await utils.ainput("2FA Password: ", hide=True))
            r = await client.invoke(
                raw.functions.auth.ExportLoginToken(
                    api_id=APP_ID, api_hash=APP_HASH, except_ids=[]
                )
            )

        if isinstance(r, raw.types.auth.LoginTokenSuccess):
            me = await client.get_me() 
            try:
                dc_id = await client.storage.dc_id()
                auth_key = await client.storage.auth_key()
                test_mode = bool(await client.storage.test_mode())
                user_id = me.id  
                is_bot = me.is_bot

                await client.storage.user_id(user_id)
                await client.storage.is_bot(is_bot)


                if not isinstance(dc_id, int):
                    raise ValueError(f"Error: dc_id must be an integer, but got {type(dc_id)}")
                if not isinstance(test_mode, bool):
                    raise ValueError(f"Error: test_mode must be a boolean, but got {type(test_mode)}")
                if not isinstance(auth_key, bytes):
                    raise ValueError(f"Error: auth_key must be bytes, but got {type(auth_key)}")
                if not isinstance(user_id, int):
                    raise ValueError(f"Error: user_id must be an integer, but got {type(user_id)}")
                if not isinstance(is_bot, bool):
                    raise ValueError(f"Error: is_bot must be a boolean, but got {type(is_bot)}")

                session_string = await client.export_session_string()

                sys.exit(
                    #print(f"Generated session for {me.username}\n\nSessionString:\n{session_string}\n\nquitting...")
                )
            except Exception as e:
                print(f"Error generating session string: {e}")