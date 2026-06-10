# -*- coding: utf-8 -*-
"""
    Unit Tests
    ~~~~~~~~~~

    Define TestCase as base class for unit tests.
    Ref: http://packages.python.org/Flask-Testing/
"""

from flask_testing import TestCase as Base

from ad2web import create_app
from ad2web.user import User, UserDetail, ADMIN, USER, ACTIVE
from ad2web.config import TestConfig
from ad2web.extensions import db
from ad2web.utils import MALE


class TestCase(Base):
    """Base TestClass for your application."""

    def create_app(self):
        """Create and return a testing flask app."""

        app, appsocket = create_app(TestConfig)
        self.appsocket = appsocket
        return app

    def init_data(self):

        demo = User(
                name=u'demo',
                email=u'demo@example.com',
                password=u'123456',
                role_code=USER,
                status_code=ACTIVE,
                user_detail=UserDetail(
                    sex_code=MALE,
                    age=10,
                    url=u'http://demo.example.com',
                    deposit=100.00,
                    location=u'Hangzhou',
                    bio=u'admin Guy is ... hmm ... just a demo guy.'))
        admin = User(
                name=u'admin',
                email=u'admin@example.com',
                password=u'123456',
                role_code=ADMIN,
                status_code=ACTIVE,
                user_detail=UserDetail(
                    sex_code=MALE,
                    age=10,
                    url=u'http://admin.example.com',
                    deposit=100.00,
                    location=u'Hangzhou',
                    bio=u'admin Guy is ... hmm ... just a admin guy.'))
        db.session.add(demo)
        db.session.add(admin)
        db.session.commit()

    def init_settings(self):
        """Initialize minimum required settings for the app to function in tests."""
        from ad2web.settings.models import Setting
        from ad2web.setup.constants import SETUP_COMPLETE

        # Mark setup as complete so the setup wizard doesn't redirect
        setup_stage = Setting(name='setup_stage', value=SETUP_COMPLETE)
        db.session.add(setup_stage)

        # Add other required settings
        for name, value in [
            ('device_type', '0'),
            ('secret_key', 'test-secret-key'),
        ]:
            db.session.add(Setting(name=name, value=value))

        db.session.commit()

    def setUp(self):
        """Reset all tables before testing."""

        db.create_all()
        self.init_settings()
        self.init_data()

    def tearDown(self):
        """Clean db session and drop all tables."""

        db.drop_all()

    def login(self, username, password):
        data = {
            'login': username,
            'password': password,
        }
        response = self.client.post('/login', data=data, follow_redirects=True)
        assert b"invalid" not in response.data.lower()
        assert response.status_code == 200
        return response

    def _logout(self):
        response = self.client.get('/logout')
        self.assertStatus(response, 302)

    def _test_get_request(self, endpoint, template=None):
        response = self.client.get(endpoint)
        self.assert_200(response)
        if template:
            self.assertTemplateUsed(name=template)
        return response
