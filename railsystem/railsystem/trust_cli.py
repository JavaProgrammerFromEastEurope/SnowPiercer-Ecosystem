"""Compatibility entrypoint delegates to mandatory production release admission."""
from .release_cli import main
if __name__ == '__main__':
    raise SystemExit(main())
