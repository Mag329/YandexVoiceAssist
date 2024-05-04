import asyncio

from core.bot import bot
from core.utils import connect
from core.stats import send_stats_timer


async def start():
    connect_task = asyncio.create_task(connect())
    stats_send_timer_task = asyncio.create_task(send_stats_timer())
    await asyncio.gather(connect_task, bot.polling(), stats_send_timer_task)


if __name__ == "__main__":
    asyncio.run(start())
