import logging
from flask import Flask
from app import db
from services.park_factor_service import ParkFactorService

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def populate_park_factors():
    """Populate park factors data for all MLB stadiums"""
    logger.info("Starting park factors population")
    
    # Create ParkFactorService
    park_service = ParkFactorService()
    
    # Update park factors
    success = park_service.update_park_factors()
    
    if success:
        logger.info("Successfully populated park factors data")
    else:
        logger.error("Failed to populate park factors data")
    
    return success

if __name__ == "__main__":
    # Import the Flask app from main.py
    from main import app
    
    # Initialize app context
    with app.app_context():
        populate_park_factors()