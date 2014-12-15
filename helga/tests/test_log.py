import time

from mock import call, patch, Mock

from helga import log


@patch('helga.log.logging')
@patch('helga.log.settings')
def test_getLogger(settings, logging):
    logger = Mock()
    handler = Mock()
    formatter = Mock()

    settings.LOG_LEVEL = 'INFO'
    settings.LOG_FILE = None
    settings.LOG_FORMAT = None

    expected_format = '%(asctime)-15s [%(levelname)s] [%(name)s:%(lineno)d]: %(message)s'

    logging.getLogger.return_value = logger
    logging.StreamHandler.return_value = handler
    logging.Formatter.return_value = formatter

    log.getLogger('foo')
    logging.getLogger.assert_called_with('foo')
    logger.setLevel.assert_called_with(logging.INFO)
    logger.addHandler.assert_called_with(handler)
    logging.Formatter.assert_called_with(expected_format)
    handler.setFormatter.assert_called_with(formatter)
    assert not logger.propagate


@patch('helga.log.logging')
@patch('helga.log.settings')
def test_get_logger_uses_log_file(settings, logging):
    logger = Mock()
    handler = Mock()
    formatter = Mock()

    settings.LOG_LEVEL = 'INFO'
    settings.LOG_FILE = '/path/to/foo.log'
    settings.LOG_FORMAT = None

    logging.getLogger.return_value = logger
    logging.StreamHandler.return_value = handler
    logging.Formatter.return_value = formatter

    log.getLogger('foo')
    logging.handlers.RotatingFileHandler.assert_called_with(filename=settings.LOG_FILE,
                                                            maxBytes=50*1024*1024,
                                                            backupCount=6)


@patch('helga.log.logging')
@patch('helga.log.settings')
def test_get_logger_uses_custom_formatter(settings, logging):
    logger = Mock()
    handler = Mock()
    formatter = Mock()

    settings.LOG_LEVEL = 'INFO'
    settings.LOG_FILE = '/path/to/foo.log'
    settings.LOG_FORMAT = 'blah blah blah'

    logging.getLogger.return_value = logger
    logging.StreamHandler.return_value = handler
    logging.Formatter.return_value = formatter

    log.getLogger('foo')
    logging.Formatter.assert_called_with(settings.LOG_FORMAT)


@patch('helga.log.os')
@patch('helga.log.logging')
@patch('helga.log.settings')
def test_get_channel_logger(settings, logging, os):
    logger = Mock()
    handler = Mock()
    formatter = Mock()

    def os_join(*args):
        return '/'.join(args)

    settings.CHANNEL_LOGGING_DIR = '/path/to/channels'
    settings.CHANNEL_LOGGING_DB = False
    os.path.exists.return_value = True
    os.path.join = os_join

    # Mocked returns
    logging.getLogger.return_value = logger
    logging.handlers.TimedRotatingFileHandler.return_value = handler
    logging.Formatter.return_value = formatter

    log.get_channel_logger('#foo')

    # Gets the right logger
    logging.getLogger.assert_called_with('channel_logger/#foo')
    logger.setLevel.assert_called_with(logging.INFO)
    assert logger.propagate is False

    # Sets the handler correctly
    logging.handlers.TimedRotatingFileHandler.assert_called_with('/path/to/channels/#foo/log.txt',
                                                                 when='d', utc=True)
    handler.setFormatter.assert_called_with(formatter)

    # Sets the formatter correctly
    logging.Formatter.assert_called_with('%(asctime)s - %(nick)s - %(message)s')

    # Logger uses the handler
    logger.addHandler.assert_called_with(handler)


@patch('helga.log.os')
@patch('helga.log.logging')
@patch('helga.log.settings')
def test_get_channel_logger_creates_log_dirs(settings, logging, os):
    def os_join(*args):
        return '/'.join(args)

    settings.CHANNEL_LOGGING_DIR = '/path/to/channels'
    settings.CHANNEL_LOGGING_DB = False
    os.path.exists.return_value = False
    os.path.join = os_join

    log.get_channel_logger('#foo')

    os.makedirs.assert_called_with('/path/to/channels/#foo')


@patch('helga.log.db')
@patch('helga.log.pymongo')
def test_database_channel_log_handler(pymongo, db):
    handler = log.DatabaseChannelLogHandler('#foo')
    record = Mock(created=time.time(), nick='me', message='The message')

    with patch.object(handler, '_ensure_indexes'):
        handler.emit(record)
        db.channel_logs.insert.assert_called_with({
            'channel': '#foo',
            'created': record.created,
            'nick': 'me',
            'message': 'The message',
        })
        assert handler._ensure_indexes.called


@patch('helga.log.db', None)
@patch('helga.log.pymongo')
def test_database_channel_log_handler_no_db(pymongo):
    handler = log.DatabaseChannelLogHandler('#foo')
    record = Mock(created=time.time(), nick='me', message='The message')

    with patch.object(handler, '_ensure_indexes'):
        handler.emit(record)
        assert not handler._ensure_indexes.called


@patch('helga.log.db')
@patch('helga.log.pymongo')
def test_database_channel_log_handler_ensure_indexes(pymongo, db):
    handler = log.DatabaseChannelLogHandler('#foo')
    handler._ensure_indexes()

    calls = [
        call([
            ('channel', pymongo.ASCENDING),
            ('created', pymongo.DESCENDING)
        ]),
        call([
            ('nick', pymongo.ASCENDING),
            ('created', pymongo.DESCENDING)
        ]),
        call([
            ('nick', pymongo.ASCENDING),
            ('channel', pymongo.ASCENDING),
            ('created', pymongo.DESCENDING)
        ]),
    ]

    db.channel_logs.ensure_index.assert_has_calls(calls)
