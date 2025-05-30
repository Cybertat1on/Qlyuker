from .src import app, check_session, create_qrcodes, nearest, raw_handler
from pyrogram import idle, handlers
import asyncio

async def main():
    await check_session(app, nearest.nearest_dc)
    await create_qrcodes()
    await idle()

app.add_handler(
    handlers.RawUpdateHandler(
        raw_handler
    )
)

loop = asyncio.get_event_loop()
loop.run_until_complete(main())
