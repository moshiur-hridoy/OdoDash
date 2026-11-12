"""Running migrations at startup must not silence the app's own loggers."""
import logging


def test_app_logger_still_enabled_after_startup(app):
    # create_app() runs Alembic, whose fileConfig() used to disable every
    # logger that already existed, app.logger included.
    assert app.logger.disabled is False


def test_service_loggers_still_enabled_after_startup(app):
    import app.services.recurring_processor  # noqa: F401 - registers its logger
    assert logging.getLogger('app.services.recurring_processor').disabled is False
