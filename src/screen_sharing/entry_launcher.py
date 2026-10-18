"""Launch a saved connection in its own process from the connection manager."""
from .native.session import main

if __name__ == '__main__':
    raise SystemExit(main())
