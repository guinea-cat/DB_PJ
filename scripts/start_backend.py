from pathlib import Path
import os
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import settings


def main() -> None:
    subprocess.run([sys.executable, "scripts/wait_for_db.py"], check=True)
    subprocess.run([sys.executable, "scripts/bootstrap_db.py"], check=True)
    subprocess.run(
        [
            "uvicorn",
            "app.main:app",
            "--host",
            "0.0.0.0",
            "--port",
            "8000",
        ],
        check=True,
        env={
            **os.environ,
            "APP_NAME": settings.app_name,
        },
    )


if __name__ == "__main__":
    main()
