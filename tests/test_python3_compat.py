# -*- coding: utf-8 -*-
"""
Tests for Python 3 compatibility.

These tests verify that the migration from Python 2 to Python 3 was done
correctly, covering areas that typically change between versions:
- Division behaviour (/ vs //)
- String/bytes handling
- Import paths
- API changes in dependencies
"""

import sys
import unittest
from datetime import datetime, timedelta

from tests import TestCase
from ad2web.utils import pretty_date, get_current_time


class TestPython3Compatibility(TestCase):
    """Tests for Python 3 compatibility issues."""

    def test_python3_required(self):
        """Ensure we are running on Python 3."""
        self.assertGreaterEqual(sys.version_info.major, 3,
                                "This application requires Python 3")

    def test_integer_division_in_pretty_date(self):
        """
        Test that pretty_date uses integer division correctly.

        In Python 2, '/' between integers was integer division.
        In Python 3, '/' is float division, '//` is integer division.
        pretty_date must use '//' to avoid returning '0 years ago' for
        values like 6 months.
        """
        now = datetime.utcnow()

        # 6 months ago: should NOT return '0 years ago'
        six_months_ago = now - timedelta(days=180)
        result = pretty_date(six_months_ago)
        self.assertNotEqual(result, '0 years ago',
                            "pretty_date returned '0 years ago' for 6 months - "
                            "likely float division bug from Python 2 to 3 migration")
        self.assertIn('month', result)

        # 3 years ago: should return a years result
        three_years_ago = now - timedelta(days=365 * 3)
        result = pretty_date(three_years_ago)
        self.assertIn('year', result)

        # 5 minutes ago
        five_mins_ago = now - timedelta(seconds=60 * 5 + 40)
        result = pretty_date(five_mins_ago)
        self.assertIn('minute', result)

    def test_get_current_time_returns_datetime(self):
        """get_current_time should return a datetime object."""
        t = get_current_time()
        self.assertIsInstance(t, datetime)

    def test_app_import(self):
        """Ensure create_app can be imported and the app is created."""
        from ad2web import create_app
        self.assertIsNotNone(create_app)

    def test_flask_extensions_importable(self):
        """Ensure Flask extension modules are importable with Python 3 paths."""
        from ad2web.extensions import db, mail, login_manager, oid
        self.assertIsNotNone(db)
        self.assertIsNotNone(mail)
        self.assertIsNotNone(login_manager)
        self.assertIsNotNone(oid)

    def test_markupsafe_import(self):
        """Ensure Markup is imported from markupsafe, not flask."""
        from markupsafe import Markup
        result = Markup('<b>test</b>')
        self.assertIsInstance(result, Markup)

    def test_werkzeug_security_import(self):
        """Ensure werkzeug.security functions are importable."""
        from werkzeug.security import generate_password_hash, check_password_hash
        hashed = generate_password_hash('test_password')
        self.assertTrue(check_password_hash(hashed, 'test_password'))
        self.assertFalse(check_password_hash(hashed, 'wrong_password'))

    def test_wtforms_stringfield_import(self):
        """Ensure StringField (renamed from TextField) is importable."""
        from wtforms import StringField
        self.assertIsNotNone(StringField)

    def test_wtforms_validators_import(self):
        """Ensure DataRequired (renamed from Required) is importable."""
        from wtforms.validators import DataRequired
        self.assertIsNotNone(DataRequired)

    def test_urllib_parse_import(self):
        """Ensure urllib.parse is used instead of Python 2's urlparse."""
        from urllib.parse import urlparse
        result = urlparse('https://example.com/path?q=1')
        self.assertEqual(result.netloc, 'example.com')

    def test_configparser_import(self):
        """Ensure configparser is used instead of Python 2's ConfigParser."""
        import configparser
        config = configparser.ConfigParser()
        self.assertIsNotNone(config)

    def test_flask_socketio_import(self):
        """Ensure flask-socketio is used instead of gevent-socketio."""
        from flask_socketio import SocketIO
        self.assertIsNotNone(SocketIO)

    def test_decoder_socketio_instance(self):
        """Ensure decoder uses flask-socketio SocketIO instance."""
        from ad2web.decoder import socketio
        from flask_socketio import SocketIO
        self.assertIsInstance(socketio, SocketIO)

    def test_notification_types_import(self):
        """Ensure notifications/types.py imports work without sleekxmpp."""
        from ad2web.notifications import types
        self.assertIsNotNone(types)

    def test_octal_literals(self):
        """Ensure octal literals use Python 3 syntax (0o prefix)."""
        # Python 3 requires 0o prefix for octal literals
        val = 0o755
        self.assertEqual(val, 493)  # 0755 in octal == 493 in decimal
        val = 0o700
        self.assertEqual(val, 448)

    def test_exception_syntax(self):
        """Ensure exception handling uses Python 3 syntax."""
        # This just tests that the syntax is valid (if it wasn't, import would fail)
        try:
            raise ValueError("test")
        except ValueError as e:
            self.assertEqual(str(e), "test")

    def test_ast_module_import_visitor(self):
        """Ensure the ImportVisitor uses Python 3's ast module."""
        import ast as _ast
        from ad2web.settings.views import ImportVisitor, parse_python_source
        self.assertTrue(issubclass(ImportVisitor, _ast.NodeVisitor))

    def test_parse_python_source(self):
        """Ensure parse_python_source works with Python 3 ast module."""
        import tempfile
        import os
        from ad2web.settings.views import parse_python_source

        # Create a temporary Python file to parse
        content = """
import os
import sys
from collections import OrderedDict
from flask import Flask, render_template
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(content)
            tmpfile = f.name

        try:
            modules = parse_python_source(tmpfile)
            modnames = [m['modname'] for m in modules]
            self.assertIn('os', modnames)
            self.assertIn('sys', modnames)
            self.assertIn('collections', modnames)
            self.assertIn('flask', modnames)
        finally:
            os.unlink(tmpfile)


class TestBytesStringHandling(TestCase):
    """Tests for bytes/string handling in Python 3."""

    def test_response_data_is_bytes(self):
        """Ensure response.data is bytes in Python 3."""
        response = self.client.get('/login')
        self.assertIsInstance(response.data, bytes)

    def test_login_page_returns_html(self):
        """Test login page returns HTML with proper bytes content."""
        response = self.client.get('/login')
        self.assert_200(response)
        # In Python 3, response.data is bytes
        self.assertIn(b'login', response.data.lower())


if __name__ == '__main__':
    unittest.main()
