"""Public synthetic inputs only; never fall back to installed/private evidence."""
from pathlib import Path

FIXTURE_ROOT = Path(__file__).resolve().parents[1] / 'fixtures'


def fixture_path(relative: str) -> Path:
    path = (FIXTURE_ROOT / relative).resolve()
    if not path.is_relative_to(FIXTURE_ROOT.resolve()):
        raise ValueError('Fixture must stay within the public fixture root')
    if not path.exists():
        raise FileNotFoundError(path)
    return path
