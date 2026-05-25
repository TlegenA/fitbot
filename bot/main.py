import asyncio
import logging
import signal

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiohttp import web

from bot.config import settings
from bot.handlers import onboarding, workout, exercises, stats, settings as settings_handler
from bot.scheduler import setup_scheduler

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


async def on_startup(bot: Bot) -> None:
    from sqlalchemy import text
    from bot.db.session import engine
    from bot.db.models import Base

    async with engine.begin() as conn:
        # Create new tables (no-op for existing ones)
        await conn.run_sync(Base.metadata.create_all)

        # Safe column migrations — ADD COLUMN IF NOT EXISTS is idempotent
        column_migrations = [
            "ALTER TABLE user_settings ADD COLUMN IF NOT EXISTS reminder_enabled BOOLEAN NOT NULL DEFAULT TRUE",
            "ALTER TABLE user_settings ADD COLUMN IF NOT EXISTS reminder_hour INTEGER NOT NULL DEFAULT 9",
        ]
        for sql in column_migrations:
            await conn.execute(text(sql))

    logger.info("Database schema up to date.")


async def on_shutdown(bot: Bot, scheduler) -> None:
    if scheduler.running:
        scheduler.shutdown(wait=False)
    await bot.session.close()
    logger.info("Bot stopped.")


async def main() -> None:
    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=MemoryStorage())

    # Register routers
    dp.include_router(onboarding.router)
    dp.include_router(workout.router)
    dp.include_router(exercises.router)
    dp.include_router(stats.router)
    dp.include_router(settings_handler.router)

    scheduler = setup_scheduler(bot)
    scheduler.start()

    dp.startup.register(on_startup)

    use_webhook = settings.environment == "production" and bool(settings.webhook_url)

    if use_webhook:
        from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

        webhook_url = f"{settings.webhook_url}/webhook"
        await bot.set_webhook(url=webhook_url, secret_token=settings.webhook_secret)
        logger.info(f"Webhook set: {webhook_url}")

        app = web.Application()
        SimpleRequestHandler(dispatcher=dp, bot=bot, secret_token=settings.webhook_secret).register(
            app, path="/webhook"
        )
        setup_application(app, dp, bot=bot)

        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, host="0.0.0.0", port=8080)
        await site.start()
        logger.info("Webhook server started on :8080")

        stop_event = asyncio.Event()

        def _stop(sig, frame):
            stop_event.set()

        signal.signal(signal.SIGTERM, _stop)
        signal.signal(signal.SIGINT, _stop)

        await stop_event.wait()
        await runner.cleanup()
    else:
        logger.info("Starting polling...")
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())

    await on_shutdown(bot, scheduler)


if __name__ == "__main__":
    asyncio.run(main())
