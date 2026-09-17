"""Compatibility entry point: build the complete release, not a partial pyz."""
from build_release import main

if __name__ == '__main__':
    raise SystemExit(main())
