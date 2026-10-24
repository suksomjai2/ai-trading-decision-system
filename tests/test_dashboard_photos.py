"""Both dashboard photographs must stay on the dashboard, unchanged, in every release.

Installers run the full test suite before installing, so any future edit that drops,
replaces or stops showing either photograph fails here and is not installed.
"""
import hashlib
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PHOTOS = {
    'dashboard_photo.jpeg': '04da0474f17be1d0afd647111df12edfebac60bec4410d880f9fe7cd9370facb',
    'dashboard_photo_2.jpeg': 'f4ea4177d932e7d0d538b35f63fbe917cbca1a9f341e691ea8af219a40852a3c',
}


def test_photo_files_present_and_byte_for_byte_unchanged():
    for name, digest in PHOTOS.items():
        path = ROOT / 'assets' / name
        assert path.exists(), f'missing dashboard photo {name}'
        assert hashlib.sha256(path.read_bytes()).hexdigest() == digest, f'dashboard photo {name} was modified'


def test_dashboard_shows_both_photos_in_header():
    source = (ROOT / 'streamlit_app.py').read_text(encoding='utf-8')
    match = re.search(r"PHOTO_FILES\s*=\s*\(([^)]*)\)", source)
    assert match, 'streamlit_app.py must declare PHOTO_FILES'
    listed = re.findall(r"'([^']+)'", match.group(1))
    assert set(PHOTOS) <= set(listed), 'both photos must be listed in PHOTO_FILES'
    assert 'v3-photos' in source and 'photo_html' in source
    hero = next(line for line in source.splitlines() if 'class="v3-hero"' in line)
    assert '{photo_html}' in hero, 'photos must be rendered in the dashboard header'
