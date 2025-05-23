# conftest.py (ana dizin veya tests klasöründe)
# import pytest
# import logging
# import sys
# from loguru import logger

# # Configure Loguru to propagate to standard logging handlers
# # This allows pytest's standard caplog to capture Loguru messages
# class PropagateHandler(logging.Handler):
#     def emit(self, record):
#         logging.getLogger(record.name).handle(record)

# # Check if the handler already exists to avoid duplicates
# handler_exists = any(isinstance(handler, PropagateHandler) for handler_id, handler in logger._core.handlers.items())

# if not handler_exists:
#     # Propagate Loguru messages to standard logging
#     # Ensure the level is low enough to capture WARNINGs, or adjust as needed
#     # logger.add(PropagateHandler(), format="{message}", level="WARNING") # Capture WARNING level and above
#     # logger.info("Loguru PropagateHandler added for pytest caplog compatibility.")
# # Optional: Configure standard logging level if needed (pytest might handle it)
# # logging.basicConfig(level=logging.DEBUG)
