import os
import logging
import threading
import time
from app import app  # noqa: F401

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def run_data_integrity_task():
    """Run the data integrity task in a separate thread"""
    # Delay startup to allow the app to initialize first
    time.sleep(5)
    
    try:
        # Import here to avoid circular imports
        from tasks.data_integrity_check import data_task
        
        # Run the data integrity check once
        logger.info("Running initial data integrity check...")
        data_task.run_integrity_check()
        logger.info("Initial data integrity check completed")
    except Exception as e:
        logger.error(f"Error running data integrity task: {e}")

if __name__ == "__main__":
    # Start the data integrity task in a background thread
    # only if this is not a test environment
    if os.environ.get('TESTING') != 'true':
        logger.info("Starting data integrity background task")
        integrity_thread = threading.Thread(target=run_data_integrity_task)
        integrity_thread.daemon = True  # Thread will exit when main thread exits
        integrity_thread.start()
    
    # Start the Flask application
    app.run(host="0.0.0.0", port=5000, debug=True)
