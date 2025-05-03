import logging
from datetime import datetime, timedelta
from app import app, db
from models import Game, WeatherCondition, ParkFactor, Odds, Team
from services.weather_service import WeatherService
from services.sportsdataio_service import SportsDataIOService
from services.odds_service import OddsService

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def fix_missing_stadium_data():
    """Fix missing stadium data for teams"""
    with app.app_context():
        teams_without_stadium = db.session.query(Team).filter(
            (Team.stadium.is_(None)) | (Team.stadium == '')
        ).all()
        
        logger.info(f"Found {len(teams_without_stadium)} teams without stadium data")
        
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
        for team in teams_without_stadium:
            if team.name in stadium_map:
                stadium_info = stadium_map[team.name]
                team.stadium = stadium_info['stadium']
                team.stadium_location = stadium_info['location']
                logger.info(f"Updated stadium data for {team.name}: {team.stadium}, {team.stadium_location}")
            else:
                logger.warning(f"No stadium mapping found for team: {team.name}")
        
        # Fix game stadium data for games with missing stadium
        games_without_stadium = db.session.query(Game).filter(
            (Game.stadium.is_(None)) | (Game.stadium == '')
        ).all()
        
        logger.info(f"Found {len(games_without_stadium)} games without stadium data")
        
        for game in games_without_stadium:
            if game.home_team and game.home_team.stadium:
                game.stadium = game.home_team.stadium
                logger.info(f"Updated stadium for game ID {game.id} to {game.stadium}")
            else:
                logger.warning(f"Unable to update stadium for game ID {game.id} - home team has no stadium")
        
        # Commit changes
        db.session.commit()
        logger.info("Stadium data fixes committed to database")

def fix_missing_weather_data():
    """Fetch and update weather data for games without it"""
    with app.app_context():
        today = datetime.now()
        end_date = today + timedelta(days=7)
        
        games_to_update = db.session.query(Game).filter(
            Game.game_datetime >= today,
            Game.game_datetime <= end_date
        ).all()
        
        weather_service = WeatherService()
        count = 0
        
        for game in games_to_update:
            # Check if game has weather data
            weather = db.session.query(WeatherCondition).filter_by(game_id=game.id).first()
            
            if not weather:
                logger.info(f"Fetching weather for game ID {game.id} - {game.away_team.name} @ {game.home_team.name}")
                try:
                    weather_data = weather_service.fetch_weather_for_game(game.id)
                    if weather_data:
                        count += 1
                        logger.info(f"Successfully updated weather for game ID {game.id}")
                    else:
                        logger.warning(f"Failed to fetch weather for game ID {game.id}")
                except Exception as e:
                    logger.error(f"Error fetching weather for game ID {game.id}: {e}")
        
        logger.info(f"Updated weather data for {count} games")

def fix_missing_odds_data():
    """Fetch and update odds data for games without it"""
    with app.app_context():
        today = datetime.now()
        end_date = today + timedelta(days=7)
        
        games_to_update = db.session.query(Game).filter(
            Game.game_datetime >= today,
            Game.game_datetime <= end_date
        ).all()
        
        odds_service = OddsService()
        
        # Group games by date to reduce API calls
        games_by_date = {}
        for game in games_to_update:
            game_date = game.game_datetime.strftime('%Y-%m-%d')
            if game_date not in games_by_date:
                games_by_date[game_date] = []
            games_by_date[game_date].append(game)
        
        # Update odds for each date
        for date, games in games_by_date.items():
            logger.info(f"Updating odds for {len(games)} games on {date}")
            try:
                success = odds_service.update_odds_for_date(date)
                if success:
                    logger.info(f"Successfully updated odds for {date}")
                else:
                    logger.warning(f"Failed to update odds for {date}")
            except Exception as e:
                logger.error(f"Error updating odds for {date}: {e}")

def fix_data_completeness():
    """Fix all data completeness issues"""
    logger.info("Starting data completeness fixes...")
    
    # 1. Fix missing stadium data first (needed for weather data)
    fix_missing_stadium_data()
    
    # 2. Fix missing weather data
    fix_missing_weather_data()
    
    # 3. Fix missing odds data
    fix_missing_odds_data()
    
    logger.info("Data completeness fixes completed")

if __name__ == "__main__":
    print("Starting data completeness fix...")
    fix_data_completeness()
    print("Fix complete!")