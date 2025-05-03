import logging
import threading
from services.scheduler import SchedulerService

# Set up logging
logger = logging.getLogger(__name__)

# Global scheduler instance
_scheduler = None
_scheduler_lock = threading.Lock()

def get_scheduler():
    """Get the global scheduler instance (creating it if needed)"""
    global _scheduler
    with _scheduler_lock:
        if _scheduler is None:
            _scheduler = SchedulerService()
        return _scheduler

def start_scheduler():
    """Start the scheduler service"""
    scheduler = get_scheduler()
    scheduler.start()
    logger.info("Scheduler service started")

def stop_scheduler():
    """Stop the scheduler service"""
    global _scheduler
    with _scheduler_lock:
        if _scheduler is not None:
            _scheduler.stop()
            _scheduler = None
            logger.info("Scheduler service stopped")

def update_teams():
    """Manually trigger team update"""
    scheduler = get_scheduler()
    return scheduler.update_teams()

def update_games():
    """Manually trigger games update"""
    scheduler = get_scheduler()
    return scheduler.update_games()

def update_player_stats():
    """Manually trigger player stats update"""
    scheduler = get_scheduler()
    return scheduler.update_player_stats()

def update_injuries():
    """Manually trigger injuries update"""
    scheduler = get_scheduler()
    return scheduler.update_injuries()

def update_lineups_and_games():
    """Manually trigger lineups and game statuses update"""
    scheduler = get_scheduler()
    return scheduler.update_lineups_and_games()

def update_weather():
    """Manually trigger weather update"""
    scheduler = get_scheduler()
    return scheduler.update_weather()

def update_odds():
    """Manually trigger odds update"""
    scheduler = get_scheduler()
    return scheduler.update_odds()

def generate_predictions():
    """Manually trigger prediction generation"""
    scheduler = get_scheduler()
    return scheduler.generate_predictions()

def fetch_initial_data():
    """Manually trigger initial data fetch"""
    scheduler = get_scheduler()
    return scheduler.fetch_initial_data()