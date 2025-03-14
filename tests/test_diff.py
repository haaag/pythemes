from __future__ import annotations

import pytest

from pythemes.__main__ import Differ


@pytest.mark.parametrize(
    'name, text1, text2, want',
    (
        (
            'no_difference',
            'Hello, world!',
            'Hello, world!',
            'Hello, world!',
        ),
        (
            'diff_with_additions',
            'Hello, world!',
            'Hello, world! How are you?',
            '- Hello, world!\n+ Hello, world! How are you?',
        ),
        (
            'with_deletions',
            'Hello, world! How are you?',
            'Hello, world!',
            '- Hello, world! How are you?\n+ Hello, world!',
        ),
        (
            'both_additions_and_deletions',
            'Hello, world!',
            'Hi, world!',
            '- Hello, world!\n+ Hi, world!',
        ),
        (
            'empty_lines',
            '',
            '',
            '',
        ),
    ),
)
def test_diff_changes(
    name: str,
    text1: str,
    text2: str,
    want: str,
    monkeypatch: pytest.MonkeyPatch,
):
    diff = Differ()
    monkeypatch.setenv('NO_COLOR', '1')
    got = diff.changes(text1, text2)
    assert got == want, f'{name}: want: {want!r}, got: {got!r}'
