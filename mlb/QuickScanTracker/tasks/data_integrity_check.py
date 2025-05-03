import logging
import schedule
import time
import importlib
import inspect
from datetime import datetime, timedelta
from app import app, db
from models import Game, WeatherCondition, ParkFactor, Odds, Team, DataUpdateLog
from services.weather_service import WeatherService
from services.odds_service import OddsService

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DataIntegrityTask:
    """Task to ensure data completeness across the platform"""
    
    def __init__(self):
        # Standard services
        self.weather_service = WeatherService()
        self.odds_service = OddsService()
        
        # Dynamic services discovery
        self.data_services = {}
        self.integrity_checks = []
        self._discover_services()
    
    def ensure_stadium_data(self):
        """Ensure all teams and games have stadium data"""
        with app.app_context():
            # Stadium mapping for all MLB teams
            stadium_map = {
                'Arizona Diamondbacks': {'stadium': 'Chase Field', 'location': 'Phoenix, AZ'},
                'Atlanta Braves': {'stadium': 'Truist Park', 'location': 'Atlanta, GA'},
                'Baltimore Orioles': {'stadium': 'Oriole Park at Camden Yards', 'location': 'Baltimore, MD'},
                'Boston Red Sox': {'stadium': 'Fenway Park', 'location': 'Boston, MA'},
                'Chicago Cubs': {'stadium': 'Wrigley Field', 'location': 'Chicago, IL'},
                'Chicago White Sox': {'stadium': 'Guaranteed Rate Field', 'location': 'Chicago, IL'},
                'Cincinnati Reds': {'stadium': 'Great American Ball Park', 'location': 'Cincinnati, OH'},
                'Cleveland Guardians': {'stadium': 'Progressive Field', 'location': 'Cleveland, OH'},
                'Colorado Rockies': {'stadium': 'Coors Field', 'location': 'Denver, CO'},
                'Detroit Tigers': {'stadium': 'Comerica Park', 'location': 'Detroit, MI'},
                'Houston Astros': {'stadium': 'Minute Maid Park', 'location': 'Houston, TX'},
                'Kansas City Royals': {'stadium': 'Kauffman Stadium', 'location': 'Kansas City, MO'},
                'Los Angeles Angels': {'stadium': 'Angel Stadium', 'location': 'Anaheim, CA'},
                'Los Angeles Dodgers': {'stadium': 'Dodger Stadium', 'location': 'Los Angeles, CA'},
                'Miami Marlins': {'stadium': 'LoanDepot Park', 'location': 'Miami, FL'},
                'Milwaukee Brewers': {'stadium': 'American Family Field', 'location': 'Milwaukee, WI'},
                'Minnesota Twins': {'stadium': 'Target Field', 'location': 'Minneapolis, MN'},
                'New York Mets': {'stadium': 'Citi Field', 'location': 'Queens, NY'},
                'New York Yankees': {'stadium': 'Yankee Stadium', 'location': 'Bronx, NY'},
                'Oakland Athletics': {'stadium': 'Oakland Coliseum', 'location': 'Oakland, CA'},
                'Philadelphia Phillies': {'stadium': 'Citizens Bank Park', 'location': 'Philadelphia, PA'},
                'Pittsburgh Pirates': {'stadium': 'PNC Park', 'location': 'Pittsburgh, PA'},
                'San Diego Padres': {'stadium': 'Petco Park', 'location': 'San Diego, CA'},
                'San Francisco Giants': {'stadium': 'Oracle Park', 'location': 'San Francisco, CA'},
                'Seattle Mariners': {'stadium': 'T-Mobile Park', 'location': 'Seattle, WA'},
                'St. Louis Cardinals': {'stadium': 'Busch Stadium', 'location': 'St. Louis, MO'},
                'Tampa Bay Rays': {'stadium': 'Tropicana Field', 'location': 'St. Petersburg, FL'},
                'Texas Rangers': {'stadium': 'Globe Life Field', 'location': 'Arlington, TX'},
                'Toronto Blue Jays': {'stadium': 'Rogers Centre', 'location': 'Toronto, ON'},
                'Washington Nationals': {'stadium': 'Nationals Park', 'location': 'Washington, DC'}
            }
            
            # Fix team stadium data
            teams_without_stadium = db.session.query(Team).filter(
                (Team.stadium.is_(None)) | (Team.stadium == '')
            ).all()
            
            if teams_without_stadium:
                logger.info(f"Found {len(teams_without_stadium)} teams without stadium data")
                
                for team in teams_without_stadium:
                    if team.name in stadium_map:
                        stadium_info = stadium_map[team.name]
                        team.stadium = stadium_info['stadium']
                        team.stadium_location = stadium_info['location']
                        logger.info(f"Updated stadium data for {team.name}: {team.stadium}, {team.stadium_location}")
                    else:
                        logger.warning(f"No stadium mapping found for team: {team.name}")
                
                # Commit team changes
                db.session.commit()
                
                # Log the update
                self._log_update('fix_team_stadiums', True, f"Updated stadium data for {len(teams_without_stadium)} teams")
            
            # Fix game stadium data 
            games_without_stadium = db.session.query(Game).filter(
                (Game.stadium.is_(None)) | (Game.stadium == '')
            ).all()
            
            if games_without_stadium:
                logger.info(f"Found {len(games_without_stadium)} games without stadium data")
                updated_count = 0
                
                for game in games_without_stadium:
                    if game.home_team and game.home_team.stadium:
                        game.stadium = game.home_team.stadium
                        updated_count += 1
                        logger.info(f"Updated stadium for game ID {game.id} to {game.stadium}")
                    else:
                        logger.warning(f"Unable to update stadium for game ID {game.id} - home team has no stadium")
                
                # Commit game changes
                db.session.commit()
                
                # Log the update
                self._log_update('fix_game_stadiums', True, f"Updated stadium data for {updated_count} games")
    
    def ensure_weather_data(self, days_ahead=7):
        """Ensure all upcoming games have weather data"""
        with app.app_context():
            today = datetime.now()
            end_date = today + timedelta(days=days_ahead)
            
            # Find games in date range
            upcoming_games = db.session.query(Game).filter(
                Game.game_datetime >= today,
                Game.game_datetime <= end_date
            ).all()
            
            # Find games without weather or with old weather data
            games_to_update = []
            for game in upcoming_games:
                weather = db.session.query(WeatherCondition).filter_by(game_id=game.id).first()
                
                # Check if weather is missing or too old
                if not weather or (datetime.now() - weather.timestamp).total_seconds() > 21600:  # 6 hours
                    games_to_update.append(game)
            
            if not games_to_update:
                logger.info("All games have up-to-date weather data")
                return
            
            logger.info(f"Found {len(games_to_update)} games needing weather updates")
            update_count = 0
            
            for game in games_to_update:
                try:
                    # Ensure the game has stadium info first
                    if not game.stadium and game.home_team and game.home_team.stadium:
                        game.stadium = game.home_team.stadium
                        db.session.commit()
                    
                    # Now fetch weather
                    weather_data = self.weather_service.fetch_weather_for_game(game.id)
                    if weather_data:
                        update_count += 1
                        logger.info(f"Updated weather for game ID {game.id}")
                    else:
                        logger.warning(f"Failed to fetch weather for game ID {game.id}")
                except Exception as e:
                    logger.error(f"Error updating weather for game ID {game.id}: {e}")
            
            # Log the update
            self._log_update('update_weather', update_count > 0, 
                           f"Updated weather data for {update_count} of {len(games_to_update)} games")
    
    def ensure_odds_data(self, days_ahead=7):
        """Ensure all upcoming games have odds data"""
        with app.app_context():
            today = datetime.now()
            end_date = today + timedelta(days=days_ahead)
            
            # Group upcoming games by date
            games_by_date = {}
            games_without_odds = []
            
            upcoming_games = db.session.query(Game).filter(
                Game.game_datetime >= today,
                Game.game_datetime <= end_date
            ).all()
            
            # Check which games are missing odds
            for game in upcoming_games:
                odds = db.session.query(Odds).filter_by(game_id=game.id).first()
                if not odds:
                    games_without_odds.append(game)
                    
                    # Group by date for API calls
                    game_date = game.game_datetime.strftime('%Y-%m-%d')
                    if game_date not in games_by_date:
                        games_by_date[game_date] = []
                    games_by_date[game_date].append(game)
            
            if not games_without_odds:
                logger.info("All games have odds data")
                return
            
            logger.info(f"Found {len(games_without_odds)} games without odds data")
            
            # Update odds for each date
            update_count = 0
            for date, games in games_by_date.items():
                try:
                    logger.info(f"Updating odds for {len(games)} games on {date}")
                    success = self.odds_service.update_odds_for_date(date)
                    if success:
                        update_count += len(games)
                        logger.info(f"Successfully updated odds for {date}")
                    else:
                        logger.warning(f"Failed to update odds for {date}")
                except Exception as e:
                    logger.error(f"Error updating odds for {date}: {e}")
            
            # Log the update
            self._log_update('update_odds', update_count > 0, 
                           f"Updated odds data for {update_count} of {len(games_without_odds)} games")
    
    def ensure_park_factors(self):
        """Ensure all stadiums have park factor data"""
        with app.app_context():
            # Get all games with stadiums
            all_stadiums = db.session.query(Game.stadium).filter(Game.stadium.isnot(None)).distinct().all()
            stadium_list = [stadium[0] for stadium in all_stadiums]
            
            # Check which stadiums are missing park factors
            missing_park_factors = []
            for stadium in stadium_list:
                park_factor = db.session.query(ParkFactor).filter_by(stadium_name=stadium).first()
                if not park_factor:
                    missing_park_factors.append(stadium)
            
            if not missing_park_factors:
                logger.info("All stadiums have park factor data")
                return
            
            logger.info(f"Found {len(missing_park_factors)} stadiums without park factor data")
            
            # Create park factors for missing stadiums
            # This is just a placeholder - the actual implementation would need to fetch real park factor data
            from services.park_factor_service import ParkFactorService
            park_service = ParkFactorService()
            
            create_count = 0
            for stadium in missing_park_factors:
                try:
                    created = park_service.create_default_park_factor(stadium)
                    if created:
                        create_count += 1
                        logger.info(f"Created park factor for {stadium}")
                    else:
                        logger.warning(f"Failed to create park factor for {stadium}")
                except Exception as e:
                    logger.error(f"Error creating park factor for {stadium}: {e}")
            
            # Log the update
            self._log_update('create_park_factors', create_count > 0, 
                           f"Created park factors for {create_count} of {len(missing_park_factors)} stadiums")
    
    def _discover_services(self):
        """Dynamically discover data services and integrity checks"""
        try:
            # Discover all service modules
            logger.info("Discovering data services...")
            
            # This will try to import all modules in the services package
            try:
                import services
                # Get all service modules
                import pkgutil
                import importlib
                
                for _, name, is_pkg in pkgutil.iter_modules(services.__path__):
                    if not is_pkg and name.endswith('_service'):
                        try:
                            # Import the module
                            module = importlib.import_module(f'services.{name}')
                            
                            # Find service classes in the module
                            for attr_name in dir(module):
                                if attr_name.endswith('Service') and not attr_name.startswith('_'):
                                    service_class = getattr(module, attr_name)
                                    
                                    # Check if this class has an ensure_data method
                                    if hasattr(service_class, 'ensure_data'):
                                        logger.info(f"Found data service: {attr_name}")
                                        
                                        # Create an instance of the service
                                        service_instance = service_class()
                                        
                                        # Store the service
                                        self.data_services[attr_name] = service_instance
                                        
                                        # Register ensure_data method as an integrity check
                                        self.integrity_checks.append(
                                            (attr_name, getattr(service_instance, 'ensure_data'))
                                        )
                        except Exception as e:
                            logger.error(f"Error loading service module {name}: {e}")
            except ImportError:
                logger.warning("Could not import services package")
                
            logger.info(f"Discovered {len(self.integrity_checks)} additional integrity checks")
        except Exception as e:
            logger.error(f"Error discovering services: {e}")
            
    def register_integrity_check(self, name, check_function):
        """
        Register a custom integrity check function
        
        Args:
            name: Name of the check for logging
            check_function: Function that performs the check
        """
        self.integrity_checks.append((name, check_function))
        logger.info(f"Registered integrity check: {name}")

    def run_integrity_check(self):
        """Run all data integrity checks and fixes"""
        logger.info("Starting automated data integrity check")
        
        try:
            # 1. Ensure stadium data (needed for other data)
            self.ensure_stadium_data()
            
            # 2. Ensure weather data
            self.ensure_weather_data()
            
            # 3. Ensure odds data
            self.ensure_odds_data()
            
            # 4. Ensure park factors
            self.ensure_park_factors()
            
            # 5. Run any dynamically discovered integrity checks
            for check_name, check_func in self.integrity_checks:
                try:
                    logger.info(f"Running integrity check: {check_name}")
                    with app.app_context():
                        check_func()
                    logger.info(f"Completed integrity check: {check_name}")
                except Exception as e:
                    logger.error(f"Error in integrity check {check_name}: {e}")
                    self._log_update(f'integrity_{check_name}', False, f"Error in {check_name} check: {e}")
            
            logger.info("Data integrity check completed successfully")
        except Exception as e:
            logger.error(f"Error in data integrity check: {e}")
            self._log_update('data_integrity_check', False, f"Error in data integrity check: {e}")
    
    def _log_update(self, task, success, details):
        """Log the update to the database"""
        log_entry = DataUpdateLog(
            task=task,
            success=success,
            details=details
        )
        db.session.add(log_entry)
        try:
            db.session.commit()
        except:
            db.session.rollback()

# Initialize the task
data_task = DataIntegrityTask()

def run_scheduler():
    """Run the scheduler for regular data integrity checks"""
    # Run data integrity check every 3 hours
    schedule.every(3).hours.do(data_task.run_integrity_check)
    
    # Also run immediately on startup
    data_task.run_integrity_check()
    
    while True:
        schedule.run_pending()
        time.sleep(60)  # Check every minute

if __name__ == "__main__":
    logger.info("Starting data integrity scheduler")
    run_scheduler()