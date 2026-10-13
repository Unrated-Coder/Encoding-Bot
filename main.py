import asyncio
import dns.resolver
from hydrogram import idle
from VideoEncoder import app, log, LOGGER

dns.resolver.default_resolver = dns.resolver.Resolver(configure=False)
dns.resolver.default_resolver.nameservers = ['8.8.8.8']

async def start_bot():
    while True:
        try:
            if not app.is_connected:
                await app.start()
            bot_me = await app.get_me()
            LOGGER.info(f"Bot started as @{bot_me.username}")
            if log:
                try:
                    await app.send_message(chat_id=log, text=f'<b>Bot Started! @{bot_me.username}</b>')
                except Exception as e:
                    LOGGER.warning(f"Could not send start message to log channel: {e}")
            await idle()
            break
        except (KeyboardInterrupt, SystemExit):
            LOGGER.info("Bot execution interrupted manually.")
            break
        except Exception as e:
            LOGGER.error(f"Bot experienced connection/runtime error: {e}. Retrying in 5s...", exc_info=True)
            await asyncio.sleep(5)
        finally:
            if app.is_connected:
                try:
                    await app.stop()
                except Exception:
                    pass

if __name__ == "__main__":
    app.loop.run_until_complete(start_bot())
