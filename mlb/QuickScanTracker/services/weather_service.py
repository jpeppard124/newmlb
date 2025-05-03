import logging
import requests
from datetime import datetime, timedelta
from .data_fetcher import DataFetcher
from app import db
from models import WeatherCondition, Game, ApiKey
from config import Config

logger = logging.getLogger(__name__)

class WeatherService(DataFetcher):
    """Service for fetching weather data for MLB games"""
    def __init__(self):
        super().__init__()
        self.base_url = self.config.WEATHER_API_BASE_URL
        
    @property
    def api_key(self):
        """Get the Weather API key from the database or fallback to config"""
        api_key = db.session.query(ApiKey).filter_by(service='weather_api', active=True).first()
        if api_key:
            return api_key.key
        return self.config.WEATHER_API_KEY
    
    def fetch_weather_for_game(self, game_id):
        """
        Fetch weather forecast for a specific game
        
        Args:
            game_id: Database ID of the game
            
        Returns:
            dict: Weather forecast data
        """
        # Check if we have a valid API key
        if not self.api_key:
            logger.warning("No WEATHER_API_KEY provided, cannot fetch weather data")
            return None
            
        game = db.session.query(Game).filter_by(id=game_id).first()
        if not game:
            logger.error(f"Game with ID {game_id} not found")
            return None
        
        if not game.stadium:
            # Try to get stadium from home team if game doesn't have it
            if game.home_team and game.home_team.stadium:
                game.stadium = game.home_team.stadium
                db.session.commit()
                logger.info(f"Updated game stadium to {game.stadium} from home team")
            else:
                logger.warning(f"No stadium information for game ID {game_id}")
                return None
                
        # Use stadium_location from home team if available for better geocoding
        location_query = game.stadium
        if game.home_team and game.home_team.stadium_location:
            location_query = f"{game.stadium}, {game.home_team.stadium_location}"
        
        # Calculate how many days in the future the game is
        days_ahead = (game.game_datetime.date() - datetime.now().date()).days
        
        # Always use hourly forecast for more accurate data
        endpoint = 'forecast.json'
        
        # If game is today, get current conditions too
        if days_ahead <= 0:
            params = {
                'key': self.api_key,
                'q': location_query,
                'days': 1,
                'hour': game.game_datetime.hour
            }
        elif days_ahead <= 2:
            # Use hourly forecast for near-term games
            params = {
                'key': self.api_key,
                'q': location_query,
                'days': 3
            }
        else:
            # Use daily forecast for games further out
            params = {
                'key': self.api_key,
                'q': location_query,
                'days': 10
            }
        
        url = f"{self.base_url}/{endpoint}"
        
        try:
            logger.info(f"Fetching weather for {game.stadium} on {game.game_datetime}")
            data = self._make_request(url, params=params)
            
            # Extract relevant weather data for the game time
            weather_data = self._extract_game_time_weather(data, game.game_datetime)
            
            # Store weather data in the database
            self._store_weather_data(game.id, weather_data)
            
            return weather_data
            
        except Exception as e:
            logger.error(f"Error fetching weather data for game {game_id}: {e}")
            return None
    
    def update_all_game_weather(self, days_ahead=7):
        """
        Update weather forecasts for all upcoming games
        
        Args:
            days_ahead: Number of days in the future to update
        """
        games = self._get_upcoming_games(days_ahead=days_ahead)
        
        for game in games:
            try:
                self.fetch_weather_for_game(game.id)
                logger.info(f"Updated weather for game {game.id}")
            except Exception as e:
                logger.error(f"Error updating weather for game {game.id}: {e}")
    
    def _extract_game_time_weather(self, weather_data, game_time):
        """
        Extract the weather forecast closest to the game time
        
        Args:
            weather_data: Full weather data from API
            game_time: Datetime of the game
            
        Returns:
            dict: Weather data for the game time
        """
        if not weather_data:
            logger.warning("No weather data received")
            return None
            
        # For today's games, check if current conditions are available 
        # and the game is within a few hours
        now = datetime.now()
        hours_until_game = (game_time - now).total_seconds() / 3600
        
        # If game is today and starting soon, use current conditions
        if game_time.date() == now.date() and hours_until_game < 4 and 'current' in weather_data:
            current = weather_data['current']
            
            # Extract relevant weather info from current conditions
            weather_info = {
                'location': weather_data.get('location', {}).get('name', ''),
                'temperature': current.get('temp_f'),
                'humidity': current.get('humidity'),
                'wind_speed': current.get('wind_mph'),
                'wind_direction': current.get('wind_dir'),
                'precipitation_chance': current.get('precip_in', 0) * 100,  # Convert to percentage
                'weather_description': current.get('condition', {}).get('text', 'Unknown')
            }
            
            # Log the exact temperature we're using from the API
            logger.info(f"Current temperature from API: {current.get('temp_f')}°F")
            
            logger.info(f"Using current weather conditions: {weather_info['temperature']}°F, {weather_info['weather_description']}")
            return weather_info
            
        # For future games, use forecast data
        if 'forecast' not in weather_data:
            logger.warning("Invalid weather data format - no forecast found")
            return None
        
        # Extract location info
        location = weather_data.get('location', {})
        location_name = location.get('name', '')
        
        # Find the forecast day
        game_date = game_time.strftime('%Y-%m-%d')
        forecast_day = None
        
        for day in weather_data['forecast']['forecastday']:
            if day['date'] == game_date:
                forecast_day = day
                break
        
        if not forecast_day:
            logger.warning(f"No forecast found for date {game_date}")
            return None
        
        # Find the closest hour to the game time
        game_hour = game_time.hour
        closest_hour = None
        min_diff = 24
        
        if 'hour' in forecast_day and isinstance(forecast_day['hour'], list):
            for hour_data in forecast_day['hour']:
                hour_time = datetime.fromisoformat(hour_data['time'].replace('Z', '+00:00'))
                diff = abs(hour_time.hour - game_hour)
                if diff < min_diff:
                    min_diff = diff
                    closest_hour = hour_data
        else:
            # If hourly data not available, use day data
            closest_hour = forecast_day['day']
        
        if not closest_hour:
            logger.warning(f"No hourly forecast found for game time {game_time}")
            return forecast_day['day']  # Fall back to day forecast
        
        # Extract relevant weather info
        weather_info = {
            'location': location_name,
            'temperature': closest_hour.get('temp_f'),
            'humidity': closest_hour.get('humidity'),
            'wind_speed': closest_hour.get('wind_mph'),
            'wind_direction': closest_hour.get('wind_dir'),
            'precipitation_chance': closest_hour.get('chance_of_rain', 0),
            'weather_description': closest_hour.get('condition', {}).get('text', 'Partly cloudy')
        }
        
        # Log the exact temperature we're using from the API
        logger.info(f"Forecast temperature from API: {closest_hour.get('temp_f')}°F")
        
        return weather_info
    
    def _store_weather_data(self, game_id, weather_data):
        """
        Store weather data in the database
        
        Args:
            game_id: Database ID of the game
            weather_data: Weather forecast data
        """
        if not weather_data:
            return
        
        # Create or update weather record
        weather = db.session.query(WeatherCondition).filter_by(game_id=game_id).first()
        
        if weather:
            # Update existing record
            weather.timestamp = datetime.utcnow()
            weather.temperature = weather_data.get('temperature')
            weather.humidity = weather_data.get('humidity')
            weather.wind_speed = weather_data.get('wind_speed')
            weather.wind_direction = weather_data.get('wind_direction')
            weather.precipitation_chance = weather_data.get('precipitation_chance')
            weather.weather_description = weather_data.get('weather_description')
        else:
            # Create new record
            weather = WeatherCondition(
                game_id=game_id,
                temperature=weather_data.get('temperature'),
                humidity=weather_data.get('humidity'),
                wind_speed=weather_data.get('wind_speed'),
                wind_direction=weather_data.get('wind_direction'),
                precipitation_chance=weather_data.get('precipitation_chance'),
                weather_description=weather_data.get('weather_description')
            )
            db.session.add(weather)
        
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error storing weather data: {e}")
    
    def get_latest_weather(self, game_id):
        """
        Get the latest weather condition for a game
        
        Args:
            game_id: Database ID of the game
            
        Returns:
            WeatherCondition: Latest weather data for the game
        """
        return db.session.query(WeatherCondition).filter_by(game_id=game_id).order_by(
            WeatherCondition.timestamp.desc()).first()
    
    def get_wind_factor(self, game_id):
        """
        Calculate a wind factor that affects home run probability
        
        Args:
            game_id: Database ID of the game
            
        Returns:
            float: Wind factor (>1 means wind helps HRs, <1 means wind hurts HRs)
        """
        weather = self.get_latest_weather(game_id)
        if not weather or not weather.wind_speed or not weather.wind_direction:
            return 1.0  # Neutral factor if no data
        
        # Calculate wind factor based on speed and direction
        # This is a simplified model; a real model would be more complex
        # and would account for the specific stadium's dimensions and orientation
        
        wind_speed = weather.wind_speed
        wind_direction = weather.wind_direction
        
        # Baseline factor
        factor = 1.0
        
        # Adjust for wind speed (stronger winds have more effect)
        if wind_speed > 15:
            speed_multiplier = 1.2
        elif wind_speed > 10:
            speed_multiplier = 1.1
        elif wind_speed > 5:
            speed_multiplier = 1.05
        else:
            speed_multiplier = 1.0
        
        # Adjust for wind direction (simplified - assuming outward is helpful)
        # In a real model, we'd need the stadium orientation
        outward_directions = ['S', 'SW', 'SE']  # Example outward directions
        inward_directions = ['N', 'NW', 'NE']   # Example inward directions
        
        if any(direction in wind_direction for direction in outward_directions):
            direction_multiplier = 1.1  # Wind blowing out helps HRs
        elif any(direction in wind_direction for direction in inward_directions):
            direction_multiplier = 0.9  # Wind blowing in hurts HRs
        else:
            direction_multiplier = 1.0  # Crosswind has neutral effect
        
        # Calculate final factor
        factor = factor * speed_multiplier * direction_multiplier
        
        return factor
        
    def _get_upcoming_games(self, days_ahead=7):
        """
        Get upcoming games from the database
        
        Args:
            days_ahead: Number of days in the future to look
            
        Returns:
            list: List of Game objects
        """
        today = datetime.now()
        end_date = today + timedelta(days=days_ahead)
        
        games = db.session.query(Game).filter(
            Game.game_datetime >= today,
            Game.game_datetime <= end_date,
            Game.status == 'scheduled'
        ).all()
        
        return games
        
    # Let the parent class handle the _make_request method
    # def _make_request(self, url, params=None, headers=None):
    #     """Make a GET request to the API"""
    #     response = requests.get(url, params=params, headers=headers)
    #     response.raise_for_status()
    #     return response.json()
