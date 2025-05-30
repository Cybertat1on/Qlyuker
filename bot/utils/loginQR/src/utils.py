from pyrogram.session import Session, Auth
from pyrogram import Client, raw
import asyncio
import os
from qrcode import QRCode
from base64 import urlsafe_b64encode as base64url
from subprocess import call
from .config import APP_ID, APP_HASH
from .client import app

qr = QRCode()


async def check_session(client: Client, dc_id: int):
    if not isinstance(dc_id, int):
        raise ValueError(f"Error: dc_id must be an integer, but got {type(dc_id)}")
    
    await client.session.stop()
    await client.storage.dc_id(dc_id)
    
    test_mode = bool(await client.storage.test_mode())

    await client.storage.auth_key(
        await Auth(
            client, await client.storage.dc_id(),
            test_mode
        ).create()
    )
    
    client.session = Session(
        client, await client.storage.dc_id(),
        await client.storage.auth_key(), test_mode
    )
    return await client.session.start()
        
async def clear_screen():
    call(['cls' if os.name == 'nt' else 'clear'], shell=True)


async def create_qrcodes():
    if not app.is_initialized:
        await app.dispatcher.start()
        app.is_initialized = True
    while True:
        await clear_screen()
        print(
            'Scan the QR code below:'
        )
        print(
            'Settings > Privacy and Security > Active Sessions > Scan QR Code'
        )
        r = await app.invoke(
            raw.functions.auth.ExportLoginToken(
                api_id=APP_ID, api_hash=str(APP_HASH), except_ids=[]
            )
        )
        if isinstance(r, raw.types.auth.LoginToken):
            await _gen_qr(r.token)
            await asyncio.sleep(30)


async def _gen_qr(token: bytes):
    token = base64url(token).decode("utf8")
    login_url = f"tg://login?token={token}"
    qr.clear()
    qr.add_data(login_url)
    qr.print_ascii()

app.connect()
nearest = app.invoke(raw.functions.help.GetNearestDc())