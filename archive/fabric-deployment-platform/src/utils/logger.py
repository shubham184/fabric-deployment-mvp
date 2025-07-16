"""
Logging utility for the configuration management system.

This module provides consistent logging setup and configuration across
the entire configuration loading system.
"""

import logging
import sys
from typing import Optional


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance with consistent formatting.
    
    Args:
        name: Logger name (typically __name__ from calling module)
        
    Returns:
        Configured logger instance
        
    Example:
        >>> logger = get_logger(__name__)
        >>> logger.info("Configuration loaded successfully")
    """
    return logging.getLogger(name)


def setup_logging(level: str = "INFO", format_string: Optional[str] = None) -> None:
    """
    Set up logging configuration for the application.
    
    Args:
        level: Logging level (DEBUG, INFO, WARN, ERROR)
        format_string: Custom format string for log messages
        
    Example:
        >>> setup_logging("DEBUG")
        >>> logger = get_logger(__name__)
        >>> logger.debug("Detailed debug information")
    """
    if format_string is None:
        format_string = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    # Convert string level to logging constant
    numeric_level = getattr(logging, level.upper(), None)
    if not isinstance(numeric_level, int):
        raise ValueError(f"Invalid log level: {level}")
    
    # Configure root logger
    logging.basicConfig(
        level=numeric_level,
        format=format_string,
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    # Set third-party loggers to WARNING to reduce noise
    logging.getLogger("yaml").setLevel(logging.WARNING)
    logging.getLogger("jsonschema").setLevel(logging.WARNING)


def log_config_operation(logger: logging.Logger, operation: str, details: str) -> None:
    """
    Log configuration operations with consistent formatting.
    
    Args:
        logger: Logger instance
        operation: Operation being performed (e.g., "LOAD", "VALIDATE", "MERGE")
        details: Details about the operation
        
    Example:
        >>> logger = get_logger(__name__)
        >>> log_config_operation(logger, "LOAD", "customer 'contoso' environment 'dev'")
    """
    logger.info(f"[{operation}] {details}")


def log_config_error(logger: logging.Logger, operation: str, error: Exception, context: str = "") -> None:
    """
    Log configuration errors with consistent formatting.
    
    Args:
        logger: Logger instance
        operation: Operation that failed
        error: Exception that occurred
        context: Additional context about the error
        
    Example:
        >>> logger = get_logger(__name__)
        >>> try:
        ...     # some operation
        ... except Exception as e:
        ...     log_config_error(logger, "VALIDATE", e, "customer config validation")
    """
    context_str = f" ({context})" if context else ""
    logger.error(f"[{operation}] FAILED{context_str}: {str(error)}")