var AlarmDecoder = function() {
    var AlarmDecoder = {};
    var _socket = null;

    AlarmDecoder.init = function() {
        this.connect("/alarmdecoder");
    };

    AlarmDecoder.connect = function(namespace) {
        _socket = io(namespace, {
            reconnection: true,
            reconnectionDelay: 500,
            reconnectionAttempts: Infinity,
        });

        _socket.on('connect', function() { });
        _socket.on('disconnect', function() { });

        _socket.on('message', function(msg) {
            var obj = (typeof msg === 'string') ? JSON.parse(msg) : msg;

            var message = obj.message;
            if (message) {
                message.message_type = obj.message_type;
            }

            PubSub.publish('message', message || obj);
        });

        _socket.on('event', function(msg) {
            var obj = (typeof msg === 'string') ? JSON.parse(msg) : msg;

            PubSub.publish('event', obj);
        });

        _socket.on('test', function(msg) {
            var obj = (typeof msg === 'string') ? JSON.parse(msg) : msg;

            PubSub.publish('test', obj);
        });

        _socket.on('device_open', function(msg) {
            var obj = (typeof msg === 'string') ? JSON.parse(msg) : msg;

            PubSub.publish('device_open', obj);
        });

        _socket.on('device_close', function(msg) {
            var obj = (typeof msg === 'string') ? JSON.parse(msg) : msg;

            PubSub.publish('device_close', obj);
        });

        _socket.on('firmwareupload', function(msg) {
            var obj = (typeof msg === 'string') ? JSON.parse(msg) : msg;

            PubSub.publish('firmwareupload', obj);
        });
    };

    AlarmDecoder.disconnect = function() {
        _socket.disconnect();
    };

    AlarmDecoder.emit = function(type, arg) {
        _socket.emit(type, arg);
    };

    return AlarmDecoder;
};
