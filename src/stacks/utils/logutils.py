import logging
import sys
from stacks.constants import LOG_PATH, LOG_FORMAT, LOG_DATE_FORMAT
from pathlib import Path
from datetime import datetime

def setup_logging(config):
    """Setup logging configuration"""
    log_level = getattr(logging, config.get('logging', 'level', default='WARNING'))
    log_path = Path(LOG_PATH)
    
    # Create log directory
    log_path.mkdir(parents=True, exist_ok=True)
    
    # Log file with date
    log_file = log_path / f"log-{datetime.now().strftime('%Y-%m-%d')}.log"
    
    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    
    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
        handler.close()
    
    # Create new handlers
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(log_level)
    file_handler.setFormatter(logging.Formatter(LOG_FORMAT, LOG_DATE_FORMAT))
    
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(logging.Formatter(LOG_FORMAT, LOG_DATE_FORMAT))
    
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)
    
    # Configure werkzeug (Flask) logger - silence all output including startup
    werkzeug_logger = logging.getLogger('werkzeug')
    werkzeug_logger.setLevel(logging.ERROR)  # Only errors from Flask
    werkzeug_logger.propagate = False  # Don't propagate to root logger
    
    # Remove all werkzeug handlers
    for handler in werkzeug_logger.handlers[:]:
        werkzeug_logger.removeHandler(handler)
    
    # Add a silent handler for werkzeug errors only
    werkzeug_handler = logging.StreamHandler(sys.stdout)
    werkzeug_handler.setLevel(logging.ERROR)
    werkzeug_handler.setFormatter(logging.Formatter(LOG_FORMAT, LOG_DATE_FORMAT))
    werkzeug_logger.addHandler(werkzeug_handler)