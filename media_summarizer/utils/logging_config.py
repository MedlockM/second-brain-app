import logging
import json
import sys
from datetime import datetime, timezone

class JsonFormatter(logging.Formatter):
    """
    Formatter that outputs JSON strings after parsing the LogRecord.
    """
    def format(self, record):
        log_record = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
            "logger": record.name,
            "module": record.module,
            "line": record.lineno,
        }
        
        # Add exception info if present
        if record.exc_info:
            log_record["exception"] = self.formatException(record.exc_info)
        
        # Add extra fields from the record's dict
        # This captures 'extra={...}' passed to logger calls
        standard_attributes = {
            "args", "asctime", "created", "exc_info", "exc_text", "filename", 
            "funcName", "levelname", "levelno", "lineno", "module", 
            "msecs", "message", "msg", "name", "pathname", "process", 
            "processName", "relativeCreated", "stack_info", "thread", "threadName"
        }
        
        for key, value in record.__dict__.items():
            if key not in standard_attributes and key not in log_record:
                # Convert non-serializable objects to string
                try:
                    json.dumps(value)
                    log_record[key] = value
                except (TypeError, OverflowError):
                    log_record[key] = str(value)

        return json.dumps(log_record)

def configure_logging(level=logging.INFO):
    """
    Configure root logger to output JSON to stdout.
    """
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    
    # Remove existing handlers to avoid duplicates
    for h in root_logger.handlers[:]:
        root_logger.removeHandler(h)
        
    root_logger.addHandler(handler)
    
    # Set levels for some noisy libraries
    logging.getLogger("botocore").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
