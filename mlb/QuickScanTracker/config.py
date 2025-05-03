import os

# API Keys and Configuration
class Config:
    # APIs
    ODDS_API_KEY = os.environ.get("ODDS_API_KEY", "")
    DISCOVERY_LAB_API_KEY = os.environ.get("DISCOVERY_LAB_API_KEY", "")
    WEATHER_API_KEY = os.environ.get("WEATHER_API_KEY", "")
    SPORTSDATAIO_KEY = os.environ.get("SPORTSDATAIO_KEY", "d278779355b24327b8cf5c25f1dde2d3")  # SportsDataIO trial key
    
    # API Endpoints
    ODDS_API_BASE_URL = "https://api.the-odds-api.com/v4"
    DISCOVERY_LAB_BASE_URL = "https://discoverylab-api.com/v1"  # Example URL
    WEATHER_API_BASE_URL = "https://api.weatherapi.com/v1"
    MLB_STATCAST_BASE_URL = "https://baseballsavant.mlb.com/statcast_search"
    SPORTSDATAIO_BASE_URL = "https://api.sportsdata.io/v3/mlb"  # SportsDataIO MLB API
    
    # Model Parameters
    MODEL_CONFIDENCE_THRESHOLD = 0.65
    BAYESIAN_PRIOR_STRENGTH = 10
    ENSEMBLE_WEIGHTS = {
        "catboost": 0.6,
        "simulation": 0.4
    }
    
    # Betting Parameters
    MIN_EDGE_PERCENTAGE = 1.5  # Minimum edge in percentage to recommend a bet
    
    # Database settings
    DB_URI = os.environ.get("DATABASE_URL")
    
    # Scheduler settings
    UPDATE_ODDS_INTERVAL_MINUTES = 15
    UPDATE_WEATHER_INTERVAL_HOURS = 1
    UPDATE_STATS_INTERVAL_HOURS = 12
    
    # Model performance tracking
    TRACK_PERFORMANCE = True
    
    # App settings
    DEBUG = True
    TESTING = os.environ.get("TESTING", "False").lower() == "true"
