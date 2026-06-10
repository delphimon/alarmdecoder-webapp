# -*- coding: utf-8 -*-

import datetime
import signal
import sys

import click

from alarmdecoder.util import NoDeviceError
from ad2web import create_app, init_app
from ad2web.extensions import db

import logging

app, appsocket = None, None

def _create_app(config=None):
    global app, appsocket

    app, appsocket = create_app()

    return app


@click.group()
@click.option('-c', '--config', default=None, help='config file')
@click.pass_context
def manager(ctx, config):
    ctx.ensure_object(dict)
    ctx.obj['config'] = config
    _create_app(config=config)


@manager.command('run')
def run_command():
    """Run in local machine."""
    try:
        init_app(app, appsocket)
        app.debug = True
        port = int(__import__('os').getenv('AD_LISTENER_PORT', '5000'))
        appsocket.run(app, host='0.0.0.0', port=port, debug=True,
                      use_reloader=True, allow_unsafe_werkzeug=True)
    except Exception as err:
        if app:
            app.logger.error("Error", exc_info=True)


@manager.command('initdb')
def initdb_command():
    """Init/reset database."""

    try:
        db.drop_all()
        db.create_all()

        # Initialize alembic revision
        from alembic.config import Config
        from alembic import command
        alembic_cfg = Config('alembic.ini')
        command.stamp(alembic_cfg, "head")

        from ad2web.notifications.models import NotificationMessage
        from ad2web.notifications.constants import DEFAULT_EVENT_MESSAGES

        for event, message in DEFAULT_EVENT_MESSAGES.items():
            db.session.add(NotificationMessage(id=event, text=message))

        db.session.commit()
    except Exception as err:
        print("Database initialization failed: {0}".format(err))
    else:
        print("Database initialization complete!")


if __name__ == "__main__":
    manager()
