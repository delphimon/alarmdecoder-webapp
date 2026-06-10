SocketIO-Flask-Debug
====================

This module provides Werkzeug debugger integration for Flask applications using
[Flask-SocketIO](https://flask-socketio.readthedocs.io/).

It works by injecting exception reraising into `app.before_request()`, which allows
forwarding incoming requests to the Werkzeug debugger if an exception was caught
during a Socket.IO event handler.

```python
# Server-side usage

from flask_socketio import SocketIO
from ad2web.socketioflaskdebug.debugger import SocketIODebugger

app.debug = True
app = SocketIODebugger(app, evalex=True)

socketio = SocketIO(app, async_mode='gevent')
socketio.run(app, host='0.0.0.0', port=5000)
```

Python dependencies: `flask`, `werkzeug`, `gevent`, `flask-socketio`, `gevent-websocket`.
