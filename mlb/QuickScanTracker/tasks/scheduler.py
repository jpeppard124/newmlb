#!/usr/bin/env python3
import os
import time
import logging
import schedule
import requests
from datetime import datetime, timedelta
import sys

# Add the parent directory to sys.path to allow imports from the main app
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Initialize logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('scheduler.log')
    ]
)
logger = logging.getLogger('mlb_betting_scheduler')

# Import configuration
from config import Config

# Set up API base URL
API_BASE_URL = "http://localhost:8000/api"  # For local development
if os.environ.get("FLASK_ENV") == "production":
    API_BASE_URL = "http://localhost:5000/api"  # For production

class SchedulerTask:
    """Base class for scheduled tasks"""
    def __init__(self, name, endpoint):
        self.name = name
        self.endpoint = endpoint
        
    def execute(self):
        """Execute the scheduled task"""
        logger.info(f"Executing task: {self.name}")
        
        try:
            response = requests.post(f"{API_BASE_URL}/{self.endpoint}")
            
            if response.status_code == 200:
                result = response.json()
                logger.info(f"Task {self.name} completed: {result.get('message', 'Success')}")
                return True
            else:
                logger.error(f"Task {self.name} failed with status code {response.status_code}: {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Error executing task {self.name}: {str(e)}")
            return False

class OddsUpdateTask(SchedulerTask):
    """Task to update betting odds"""
    def __init__(self):
        super().__init__("Odds Update", "update_odds")
    
class WeatherUpdateTask(SchedulerTask):
    """Task to update weather forecasts"""
    def __init__(self):
        super().__init__("Weather Update", "update_weather")
    
class StatsUpdateTask(SchedulerTask):
    """Task to update player and team statistics"""
    def __init__(self):
        super().__init__("Stats Update", "update_stats")
    
class PredictionGenerationTask(SchedulerTask):
    """Task to generate predictions for upcoming games"""
    def __init__(self):
        super().__init__("Prediction Generation", "generate_predictions")
    
class PerformanceUpdateTask(SchedulerTask):
    """Task to update performance metrics"""
    def __init__(self):
        super().__init__("Performance Update", "update_performance")

def setup_schedule():
    """Set up the task schedule based on configuration"""
    logger.info("Setting up scheduled tasks")
    
    # Update odds every X minutes
    schedule.every(Config.UPDATE_ODDS_INTERVAL_MINUTES).minutes.do(OddsUpdateTask().execute)
    logger.info(f"Scheduled odds updates every {Config.UPDATE_ODDS_INTERVAL_MINUTES} minutes")
    
    # Update weather forecasts every X hours
    schedule.every(Config.UPDATE_WEATHER_INTERVAL_HOURS).hours.do(WeatherUpdateTask().execute)
    logger.info(f"Scheduled weather updates every {Config.UPDATE_WEATHER_INTERVAL_HOURS} hours")
    
    # Update statistics every X hours
    schedule.every(Config.UPDATE_STATS_INTERVAL_HOURS).hours.do(StatsUpdateTask().execute)
    logger.info(f"Scheduled stats updates every {Config.UPDATE_STATS_INTERVAL_HOURS} hours")
    
    # Generate new predictions 3 times per day
    schedule.every().day.at("09:00").do(PredictionGenerationTask().execute)
    schedule.every().day.at("15:00").do(PredictionGenerationTask().execute)
    schedule.every().day.at("21:00").do(PredictionGenerationTask().execute)
    logger.info("Scheduled prediction generation at 9:00, 15:00, and 21:00 daily")
    
    # Update performance metrics once per day (early morning)
    schedule.every().day.at("06:00").do(PerformanceUpdateTask().execute)
    logger.info("Scheduled performance updates at 06:00 daily")

def initial_data_load():
    """Perform initial data load on startup"""
    logger.info("Performing initial data load")
    
    # Update odds
    OddsUpdateTask().execute()
    
    # Update weather
    WeatherUpdateTask().execute()
    
    # Update stats
    StatsUpdateTask().execute()
    
    # Generate initial predictions
    PredictionGenerationTask().execute()
    
    logger.info("Initial data load completed")

def run_scheduler():
    """Run the scheduler loop"""
    logger.info("Starting MLB Betting Engine scheduler")
    
    # Perform initial data load
    initial_data_load()
    
    # Set up scheduled tasks
    setup_schedule()
    
    # Run the scheduler loop
    logger.info("Scheduler running, press Ctrl+C to exit")
    
    try:
        while True:
            schedule.run_pending()
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Scheduler stopped by user")
    except Exception as e:
        logger.error(f"Scheduler error: {str(e)}")
        raise

if __name__ == "__main__":
    run_scheduler()
