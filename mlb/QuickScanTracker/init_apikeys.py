import os
import logging
from app import app, db
from models import ApiKey

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def save_api_key(service, key):
    """Save or update an API key in the database"""
    api_key = db.session.query(ApiKey).filter_by(service=service).first()
    
    if api_key:
        # Update existing key
        api_key.key = key
        api_key.active = True
        logger.info(f"Updated existing API key for {service}")
    else:
        # Create new key
        api_key = ApiKey(service=service, key=key)
        db.session.add(api_key)
        logger.info(f"Created new API key for {service}")
    
    db.session.commit()

def init_api_keys():
    """Initialize API keys from environment variables"""
    with app.app_context():
        # The Odds API key
        odds_api_key = os.environ.get('ODDS_API_KEY')
        if odds_api_key:
            save_api_key('odds_api', odds_api_key)
            logger.info("Saved ODDS_API_KEY to database")
        else:
            logger.warning("No ODDS_API_KEY found in environment variables")
            
        # Weather API key
        weather_api_key = os.environ.get('WEATHER_API_KEY')
        if weather_api_key:
            save_api_key('weather_api', weather_api_key)
            logger.info("Saved WEATHER_API_KEY to database")
        else:
            logger.warning("No WEATHER_API_KEY found in environment variables")
            
        # Discovery Lab API key
        discovery_lab_api_key = os.environ.get('DISCOVERY_LAB_API_KEY')
        if discovery_lab_api_key:
            save_api_key('discovery_lab', discovery_lab_api_key)
            logger.info("Saved DISCOVERY_LAB_API_KEY to database")
        else:
            logger.warning("No DISCOVERY_LAB_API_KEY found in environment variables")
            
        logger.info("API key initialization complete")

if __name__ == '__main__':
    init_api_keys()