from __future__ import annotations

import configparser
import unittest

from pythemes.__main__ import INIData
from pythemes.__main__ import parse_raw_program


class TestParsePrograms(unittest.TestCase):
    def setUp(self) -> None:
        """Prepare a fresh INIData before each test."""
        self.data: INIData = {}

    def test_valid_program_section(self):
        """Should parse all fields correctly when present."""
        config = configparser.ConfigParser()
        section = 'example_program'
        config.add_section(section)
        config.set(section, 'file', '/usr/bin/example')
        config.set(section, 'query', 'example-query')
        config.set(section, 'light', 'light-theme')
        config.set(section, 'dark', 'dark-theme')
        config.set(section, 'cmd', 'run-example')

        parse_raw_program(section, config, self.data)

        expected = {
            'file': '/usr/bin/example',
            'query': 'example-query',
            'light': 'light-theme',
            'dark': 'dark-theme',
            'cmd': 'run-example',
        }
        self.assertEqual(self.data[section], expected)

    def test_missing_program_section(self):
        """Should not modify data if the section is missing."""
        config = configparser.ConfigParser()
        parse_raw_program('missing_section', config, self.data)

        self.assertEqual(self.data, {})  # No changes

    def test_missing_optional_fields(self):
        """Should use fallback values for missing optional fields."""
        config = configparser.ConfigParser()
        section = 'example_program'
        config.add_section(section)
        config.set(section, 'light', 'light-theme')
        config.set(section, 'dark', 'dark-theme')

        parse_raw_program(section, config, self.data)

        expected = {
            'file': '',  # Default fallback
            'query': '',  # Default fallback
            'light': 'light-theme',
            'dark': 'dark-theme',
            'cmd': '',  # Default fallback
        }
        self.assertEqual(self.data[section], expected)

    def test_empty_values(self):
        """Should correctly handle empty values."""
        config = configparser.ConfigParser()
        section = 'example_program'
        config.add_section(section)
        config.set(section, 'file', '')
        config.set(section, 'query', '')
        config.set(section, 'light', '')
        config.set(section, 'dark', '')
        config.set(section, 'cmd', '')

        parse_raw_program(section, config, self.data)

        expected = {
            'file': '',
            'query': '',
            'light': '',
            'dark': '',
            'cmd': '',
        }
        self.assertEqual(self.data[section], expected)


if __name__ == '__main__':
    unittest.main()
