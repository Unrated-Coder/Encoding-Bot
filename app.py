from main import app, start_bot

if __name__ == "__main__":
    app.loop.run_until_complete(start_bot())
