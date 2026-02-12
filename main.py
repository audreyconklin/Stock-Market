import sys

from src.bot import run_once, VERSION


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] in ("--version", "-v"):
        print(f"Stock Bot v{VERSION}")
        sys.exit(0)
    run_once()
