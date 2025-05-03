"""
Run the data integrity checker as a standalone process

This script runs the data integrity check system that ensures all game data
is complete and up to date. It should be run in the background using:
python run_data_integrity.py
"""

import logging
from tasks.data_integrity_check import run_scheduler

if __name__ == "__main__":
    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger(__name__)
    
    logger.info("Starting data integrity scheduler service")
    # This will run the scheduler and not return (infinite loop)
    run_scheduler()