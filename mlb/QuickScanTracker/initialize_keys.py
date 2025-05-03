#!/usr/bin/env python3
import os
import sys
from app import app, db
from models import ApiKey
from datetime import datetime

def initialize_api_keys():
    """Initialize API keys from environment variables"""
    print("Initializing API keys...")
    
    # Get keys from environment
    weather_api_key = os.environ.get("WEATHER_API_KEY")
    odds_api_key = os.environ.get("ODDS_API_KEY")
    sportsdataio_key = os.environ.get("SPORTSDATAIO_KEY", "d278779355b24327b8cf5c25f1dde2d3")  # Use trial key as fallback
    
    # Save keys to database
    with app.app_context():
        # Weather API
        if weather_api_key:
            weather_key = db.session.query(ApiKey).filter_by(service="weather_api").first()
            if weather_key:
                weather_key.key = weather_api_key
                weather_key.active = True
                weather_key.updated_at = datetime.utcnow()
            else:
                weather_key = ApiKey(
                    service="weather_api",
                    key=weather_api_key,
                    active=True
                )
                db.session.add(weather_key)
            print("✓ Weather API key added")
        
        # Odds API
        if odds_api_key:
            odds_key = db.session.query(ApiKey).filter_by(service="odds_api").first()
            if odds_key:
                odds_key.key = odds_api_key
                odds_key.active = True
                odds_key.updated_at = datetime.utcnow()
            else:
                odds_key = ApiKey(
                    service="odds_api",
                    key=odds_api_key,
                    active=True
                )
                db.session.add(odds_key)
            print("✓ Odds API key added")
        
        # SportsDataIO API
        if sportsdataio_key:
            sportsdataio = db.session.query(ApiKey).filter_by(service="sportsdataio").first()
            if sportsdataio:
                sportsdataio.key = sportsdataio_key
                sportsdataio.active = True
                sportsdataio.updated_at = datetime.utcnow()
            else:
                sportsdataio = ApiKey(
                    service="sportsdataio",
                    key=sportsdataio_key,
                    active=True
                )
                db.session.add(sportsdataio)
            print("✓ SportsDataIO API key added")
        
        db.session.commit()
        print("API keys initialized successfully!")

if __name__ == "__main__":
    initialize_api_keys()