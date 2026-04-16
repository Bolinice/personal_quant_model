import logging
import logging.config
from pathlib import Path
from app.core.config import settings

def setup_logging():
    """配置日志系统"""
    log_config = {
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': {
            'standard': {
                'format': '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
            },
        },
        'handlers': {
            'console': {
                'level': 'INFO',
                'class': 'logging.StreamHandler',
                'formatter': 'standard',
            },
            'file': {
                'level': 'DEBUG',
                'class': 'logging.handlers.RotatingFileHandler',
                'filename': Path('logs/app.log'),
                'maxBytes': 10485760,  # 10MB
                'backupCount': 5,
                'formatter': 'standard',
            },
        },
        'loggers': {
            '': {
                'handlers': ['console', 'file'] if not settings.debug else ['console'],
                'level': 'DEBUG' if settings.debug else 'INFO',
                'propagate': True
            },
            'uvicorn': {
                'handlers': ['console', 'file'] if not settings.debug else ['console'],
                'level': 'INFO',
                'propagate': False
            },
            'sqlalchemy': {
                'handlers': ['console', 'file'] if not settings.debug else ['console'],
                'level': 'WARNING',
                'propagate': False
            },
        }
    }

    logging.config.dictConfig(log_config)
    logger = logging.getLogger(__name__)
    logger.info("Logging system initialized")
    return logger

logger = setup_logging()