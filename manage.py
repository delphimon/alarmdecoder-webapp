# -*- coding: utf-8 -*-

import os
import sys
import datetime
import signal
import click
from flask.cli import FlaskGroup

from ad2web import create_app, init_app
from ad2web.extensions import db

def _create_app(info=None):
    app, socketio = create_app()
    return app

@click.group(cls=FlaskGroup, create_app=_create_app)
def cli():
    """Management script for the AlarmDecoder webapp."""
    pass

@cli.command('run')
@click.option('--host', default='0.0.0.0', help='Host to listen on')
@click.option('--port', default=None, type=int, help='Port to listen on')
@click.option('--debug', is_flag=True, default=True, help='Enable debug mode')
def run_command(host, port, debug):
    """Run in local machine."""
    from ad2web import create_app, init_app

    app, socketio = create_app()

    if port is None:
        port = int(os.getenv('AD_LISTENER_PORT', '5000'))

    try:
        init_app(app, socketio)
    except SystemExit:
        raise
    except Exception:
        app.logger.error("Error initializing app", exc_info=True)

    app.debug = debug
    socketio.run(app, host=host, port=port, debug=debug, allow_unsafe_werkzeug=True)

@cli.command('initdb')
def initdb_command():
    """Init/reset database."""
    app, socketio = create_app()
    with app.app_context():
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
    cli()
