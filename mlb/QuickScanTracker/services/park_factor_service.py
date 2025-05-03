import logging
import requests
from datetime import datetime
from bs4 import BeautifulSoup
from app import db
from models import ParkFactor, Team, Game, DataUpdateLog
from config import Config
from .data_fetcher import DataFetcher

logger = logging.getLogger(__name__)

class ParkFactorService(DataFetcher):
    """Service for managing park factors data for MLB stadiums"""
    
    def __init__(self):
        super().__init__()
        self.config = Config()
        
        # We'll now use a dynamic data fetching approach rather than predetermined values
        # This allows us to fetch real park factor data from Statcast or other sources
        self.statcast_url = "https://baseballsavant.mlb.com/leaderboard/statcast-park-factors"
        
        # Fallback information for extreme parks only when needed as a last resort
        # This serves as a backup only when the API is down or unavailable
        self.fallback_park_factors = {
            'Coors Field': {  # Colorado Rockies - extreme elevation effects
                'runs_factor': None,  # Will be fetched from actual data
                'hr_factor': None,    # Will be fetched from actual data
                'elevation': 5280.0,  # Physical property of the stadium
                'temperature_effect': None,  # Will be calculated from actual weather/results data
                'wind_effect': None,  # Will be calculated from actual weather/results data
                'humidity_effect': None,  # Will be calculated from actual weather/results data
            },
            'Great American Ball Park': {  # Cincinnati Reds
                'runs_factor': 106.0,
                'hr_factor': 125.0,
                'hits_factor': 102.0,
                'doubles_factor': 99.0,
                'triples_factor': 82.0,
                'hr_left_factor': 130.0,
                'hr_center_factor': 115.0,
                'hr_right_factor': 130.0,
                'elevation': 490.0,
                'temperature_effect': 1.0,
                'wind_effect': 1.5,
                'humidity_effect': 0.8,
                'left_handed_advantage': 1.0,
                'right_handed_advantage': 2.0
            },
            'Citizens Bank Park': {  # Philadelphia Phillies
                'runs_factor': 104.0,
                'hr_factor': 117.0,
                'hits_factor': 101.0,
                'doubles_factor': 100.0,
                'triples_factor': 77.0,
                'hr_left_factor': 115.0,
                'hr_center_factor': 110.0,
                'hr_right_factor': 126.0,
                'elevation': 39.0,
                'temperature_effect': 0.8,
                'wind_effect': 1.2,
                'humidity_effect': 0.7,
                'left_handed_advantage': 1.0,
                'right_handed_advantage': 1.5
            },
            
            # Neutral parks
            'Busch Stadium': {  # St. Louis Cardinals
                'runs_factor': 99.0,
                'hr_factor': 94.0,
                'hits_factor': 100.0,
                'doubles_factor': 101.0,
                'triples_factor': 103.0,
                'hr_left_factor': 97.0,
                'hr_center_factor': 93.0,
                'hr_right_factor': 92.0,
                'elevation': 466.0,
                'temperature_effect': 0.9,
                'wind_effect': 0.8,
                'humidity_effect': 0.7,
                'left_handed_advantage': 0.5,
                'right_handed_advantage': 0.2
            },
            'Yankee Stadium': {  # New York Yankees
                'runs_factor': 102.0,
                'hr_factor': 116.0,
                'hits_factor': 99.0,
                'doubles_factor': 96.0,
                'triples_factor': 60.0,
                'hr_left_factor': 90.0,
                'hr_center_factor': 102.0,
                'hr_right_factor': 156.0, # Short right field porch
                'elevation': 14.0,
                'temperature_effect': 0.7,
                'wind_effect': 1.0,
                'humidity_effect': 0.8,
                'left_handed_advantage': 3.0, # Significant advantage for lefties
                'right_handed_advantage': 0.0
            },
            'Dodger Stadium': {  # Los Angeles Dodgers
                'runs_factor': 96.0,
                'hr_factor': 101.0,
                'hits_factor': 97.0,
                'doubles_factor': 92.0,
                'triples_factor': 90.0,
                'hr_left_factor': 102.0,
                'hr_center_factor': 100.0,
                'hr_right_factor': 101.0,
                'elevation': 500.0,
                'temperature_effect': 0.4,
                'wind_effect': 0.5,
                'humidity_effect': 0.3,
                'left_handed_advantage': 0.0,
                'right_handed_advantage': 0.0
            },
            
            # Extreme pitcher's parks
            'Oracle Park': {  # San Francisco Giants
                'runs_factor': 88.0,
                'hr_factor': 75.0,
                'hits_factor': 97.0,
                'doubles_factor': 103.0,
                'triples_factor': 140.0, # Triples alley
                'hr_left_factor': 93.0,
                'hr_center_factor': 74.0,
                'hr_right_factor': 58.0, # Very tough for righties
                'elevation': 0.0, # Sea level
                'temperature_effect': 0.9,
                'wind_effect': 1.6, # Strong bay winds
                'humidity_effect': 1.1,
                'left_handed_advantage': -1.0, # Tough for lefties
                'right_handed_advantage': -2.0 # Very tough for righties
            },
            'T-Mobile Park': {  # Seattle Mariners
                'runs_factor': 90.0,
                'hr_factor': 88.0,
                'hits_factor': 96.0, 
                'doubles_factor': 98.0,
                'triples_factor': 94.0,
                'hr_left_factor': 90.0,
                'hr_center_factor': 88.0,
                'hr_right_factor': 86.0,
                'elevation': 0.0, # Sea level
                'temperature_effect': 0.5,
                'wind_effect': 0.7,
                'humidity_effect': 1.0,
                'left_handed_advantage': -0.5,
                'right_handed_advantage': -0.5
            },
            'Tropicana Field': {  # Tampa Bay Rays
                'runs_factor': 92.0,
                'hr_factor': 85.0,
                'hits_factor': 97.0,
                'doubles_factor': 96.0,
                'triples_factor': 80.0,
                'hr_left_factor': 85.0,
                'hr_center_factor': 84.0,
                'hr_right_factor': 86.0,
                'elevation': 0.0,
                'temperature_effect': 0.0, # Domed stadium
                'wind_effect': 0.0, # Domed stadium
                'humidity_effect': 0.0, # Domed stadium
                'left_handed_advantage': -0.5,
                'right_handed_advantage': -0.5
            },
            
            # Other stadiums
            'American Family Field': {  # Milwaukee Brewers (formerly Miller Park)
                'runs_factor': 102.0,
                'hr_factor': 110.0,
                'hits_factor': 101.0,
                'doubles_factor': 97.0,
                'triples_factor': 65.0,
                'hr_left_factor': 108.0,
                'hr_center_factor': 107.0,
                'hr_right_factor': 115.0,
                'elevation': 602.0,
                'temperature_effect': 0.0, # Retractable dome
                'wind_effect': 0.3, # When open
                'humidity_effect': 0.2, # When open
                'left_handed_advantage': 0.8,
                'right_handed_advantage': 0.5
            },
            'Fenway Park': {  # Boston Red Sox
                'runs_factor': 107.0,
                'hr_factor': 96.0,
                'hits_factor': 109.0,
                'doubles_factor': 126.0, # Green Monster effect
                'triples_factor': 89.0,
                'hr_left_factor': 90.0,
                'hr_center_factor': 96.0,
                'hr_right_factor': 102.0,
                'elevation': 20.0,
                'temperature_effect': 0.7,
                'wind_effect': 1.1,
                'humidity_effect': 0.7,
                'left_handed_advantage': 0.5,
                'right_handed_advantage': 1.5 # Monster advantage
            },
            'Wrigley Field': {  # Chicago Cubs
                'runs_factor': 102.0,
                'hr_factor': 108.0,
                'hits_factor': 102.0,
                'doubles_factor': 103.0,
                'triples_factor': 119.0,
                'hr_left_factor': 110.0,
                'hr_center_factor': 105.0,
                'hr_right_factor': 109.0,
                'elevation': 594.0,
                'temperature_effect': 0.9,
                'wind_effect': 2.5, # Extreme wind effects
                'humidity_effect': 0.8,
                'left_handed_advantage': 0.8,
                'right_handed_advantage': 0.8
            },
            'Minute Maid Park': {  # Houston Astros
                'runs_factor': 100.0,
                'hr_factor': 107.0,
                'hits_factor': 98.0,
                'doubles_factor': 102.0,
                'triples_factor': 65.0,
                'hr_left_factor': 123.0, # Crawford Boxes
                'hr_center_factor': 97.0,
                'hr_right_factor': 101.0,
                'elevation': 50.0,
                'temperature_effect': 0.0, # Retractable dome
                'wind_effect': 0.0, # Retractable dome
                'humidity_effect': 0.0, # Retractable dome
                'left_handed_advantage': -0.5,
                'right_handed_advantage': 1.5 # Crawford Boxes advantage
            },
            # Add more stadiums as needed
        }
    
    def update_park_factors(self):
        """
        Update park factors for all MLB stadiums using live data from Baseball Savant (Statcast)
        
        Returns:
            bool: Whether the update was successful
        """
        try:
            logger.info("Updating park factors for MLB stadiums from live data sources")
            
            # Get all teams to map stadiums
            teams = db.session.query(Team).all()
            
            # Track updates for logging
            updated_count = 0
            
            # First attempt to fetch the latest park factors from Baseball Savant
            statcast_factors = self._fetch_statcast_park_factors()
            
            # Add/update park factors for each stadium
            for team in teams:
                if not team.stadium:
                    logger.warning(f"No stadium set for team {team.name}")
                    continue
                
                # Get park factor record
                park_factor = db.session.query(ParkFactor).filter_by(
                    stadium_name=team.stadium
                ).first()
                
                if not park_factor:
                    # Create new park factor record
                    park_factor = ParkFactor(
                        stadium_name=team.stadium,
                        year=datetime.now().year
                    )
                    db.session.add(park_factor)
                
                # Did we find this stadium in the live data?
                stadium_found = False
                
                # Try to match with data fetched from Statcast
                if statcast_factors:
                    for stadium_data in statcast_factors:
                        # Try different ways to match stadium names
                        if (team.stadium.lower() in stadium_data.get('stadium', '').lower() or
                            team.name.lower() in stadium_data.get('team', '').lower() or
                            team.abbreviation.lower() in stadium_data.get('team_abbr', '').lower()):
                            
                            # We found a match in the live data
                            stadium_found = True
                            logger.info(f"Found live park factor data for {team.stadium}")
                            
                            # Update with live data
                            if 'runs_factor' in stadium_data:
                                park_factor.runs_factor = stadium_data['runs_factor']
                            if 'hr_factor' in stadium_data:
                                park_factor.hr_factor = stadium_data['hr_factor']
                            if 'hits_factor' in stadium_data:
                                park_factor.hits_factor = stadium_data['hits_factor']
                            if 'doubles_factor' in stadium_data:
                                park_factor.doubles_factor = stadium_data['doubles_factor']
                            if 'triples_factor' in stadium_data:
                                park_factor.triples_factor = stadium_data['triples_factor']
                            
                            updated_count += 1
                            break
                
                # If we didn't find live data, check if we have any fallback information
                if not stadium_found:
                    logger.warning(f"No live data found for {team.stadium}, checking fallback data")
                    
                    # Check our fallback data for this stadium
                    fallback_data = self.fallback_park_factors.get(team.stadium)
                    
                    if fallback_data:
                        logger.info(f"Using fallback data for {team.stadium} while logging the missing data situation")
                        
                        # Update with fallback factors but only for those that are actually provided
                        for key, value in fallback_data.items():
                            if value is not None:  # Only use non-None values
                                setattr(park_factor, key, value)
                        
                        # Log this usage of fallback data for future investigation
                        self._log_update(False, f"Used fallback data for {team.stadium} - NEEDS LIVE DATA")
                    else:
                        # Use neutral values as absolute last resort
                        logger.warning(f"No data available for {team.stadium}, using neutral factors and logging this gap")
                        
                        # Set neutral values 
                        if not park_factor.runs_factor:
                            park_factor.runs_factor = 100.0
                        if not park_factor.hr_factor:
                            park_factor.hr_factor = 100.0
                        if not park_factor.hits_factor:
                            park_factor.hits_factor = 100.0
                        
                        # Flag this in the logs for followup
                        self._log_update(False, f"Missing data for {team.stadium} - REQUIRES URGENT ATTENTION")
                    
                    updated_count += 1
            
            db.session.commit()
            
            # Log the update
            log_entry = DataUpdateLog(
                task='update_park_factors',
                success=True,
                details=f"Updated park factors for {updated_count} stadiums"
            )
            db.session.add(log_entry)
            db.session.commit()
            
            logger.info(f"Successfully updated park factors for {updated_count} stadiums")
            return True
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error updating park factors: {e}")
            
            # Log the error
            try:
                log_entry = DataUpdateLog(
                    task='update_park_factors',
                    success=False,
                    details=f"Error updating park factors: {e}"
                )
                db.session.add(log_entry)
                db.session.commit()
            except:
                pass
                
            return False
    
    def _log_update(self, success, details):
        """
        Helper method to log data updates
        
        Args:
            success: Whether the update was successful
            details: Details about the update
        """
        try:
            log_entry = DataUpdateLog(
                task='park_factor_update',
                success=success,
                details=details
            )
            db.session.add(log_entry)
            db.session.commit()
        except Exception as e:
            logger.error(f"Error logging update: {e}")
            db.session.rollback()
    
    def get_park_factor(self, stadium_name):
        """
        Get park factor for a specific stadium
        
        Args:
            stadium_name: Name of the stadium
            
        Returns:
            dict: Park factors for the stadium
        """
        park_factor = db.session.query(ParkFactor).filter_by(stadium_name=stadium_name).first()
        
        if park_factor:
            # Convert to dictionary with proper factors
            factors = {}
            factors['stadium_name'] = park_factor.stadium_name
            factors['runs_factor'] = park_factor.runs_factor
            factors['hr_factor'] = park_factor.hr_factor
            factors['hits_factor'] = park_factor.hits_factor
            factors['hr_left_factor'] = park_factor.hr_left_factor if park_factor.hr_left_factor else park_factor.hr_factor
            factors['hr_right_factor'] = park_factor.hr_right_factor if park_factor.hr_right_factor else park_factor.hr_factor
            factors['doubles_factor'] = park_factor.doubles_factor
            factors['triples_factor'] = park_factor.triples_factor
            factors['elevation'] = park_factor.elevation
            
            # Add hitter/pitcher friendliness labels
            if park_factor.runs_factor > 105:
                factors['runs_label'] = 'Very hitter friendly'
                factors['runs_class'] = 'text-success'
            elif park_factor.runs_factor > 100:
                factors['runs_label'] = 'Hitter friendly'
                factors['runs_class'] = 'text-success'
            elif park_factor.runs_factor < 95:
                factors['runs_label'] = 'Pitcher friendly'
                factors['runs_class'] = 'text-danger'
            elif park_factor.runs_factor < 100:
                factors['runs_label'] = 'Slightly pitcher friendly'
                factors['runs_class'] = 'text-warning'
            else:
                factors['runs_label'] = 'Neutral'
                factors['runs_class'] = 'text-info'
                
            # Add HR friendliness labels
            if park_factor.hr_factor > 110:
                factors['hr_label'] = 'Extreme HR friendly'
                factors['hr_class'] = 'text-success'
            elif park_factor.hr_factor > 100:
                factors['hr_label'] = 'HR friendly'
                factors['hr_class'] = 'text-success'
            elif park_factor.hr_factor < 90:
                factors['hr_label'] = 'Difficult HR park'
                factors['hr_class'] = 'text-danger'
            elif park_factor.hr_factor < 100:
                factors['hr_label'] = 'Slightly HR suppressing'
                factors['hr_class'] = 'text-warning'
            else:
                factors['hr_label'] = 'Neutral for HRs'
                factors['hr_class'] = 'text-info'
                
            return factors
        
        return None
    
    def _fetch_statcast_park_factors(self):
        """
        Fetch park factors from MLB Statcast (Baseball Savant)
        
        Returns:
            list: List of park factor dictionaries with live data
        """
        try:
            logger.info(f"Fetching park factors from {self.statcast_url}")
            
            # Setup headers to mimic a browser request
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            
            # Fetch the park factors page from Baseball Savant
            response = requests.get(self.statcast_url, headers=headers)
            
            if not response.ok:
                logger.error(f"Failed to fetch park factors from Statcast: {response.status_code}")
                return []
                
            # Parse the HTML content
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Extract the park factors table
            tables = soup.find_all('table')
            if not tables:
                logger.error("No tables found on Baseball Savant park factors page")
                return []
                
            # Find the park factors table (usually the largest one)
            park_table = max(tables, key=lambda t: len(t.find_all('tr')))
            
            # Extract data from the table
            park_factors = []
            rows = park_table.find_all('tr')
            
            # Skip header row
            for row in rows[1:]:
                cells = row.find_all('td')
                if len(cells) < 5:  # Make sure we have enough cells
                    continue
                
                # Extract stadium and team information
                try:
                    team_cell = cells[0].text.strip()
                    park_name = cells[1].text.strip()
                    
                    # Extract various factors
                    # Column indices may need adjustment based on actual table structure
                    basic_factor = float(cells[2].text.strip())
                    hr_factor = float(cells[3].text.strip())
                    hits_factor = float(cells[4].text.strip())
                    
                    # Additional factors if available
                    doubles_factor = float(cells[5].text.strip()) if len(cells) > 5 else None
                    triples_factor = float(cells[6].text.strip()) if len(cells) > 6 else None
                    
                    # Create park factor dictionary
                    park_data = {
                        'team': team_cell,
                        'stadium': park_name,
                        'runs_factor': basic_factor,
                        'hr_factor': hr_factor,
                        'hits_factor': hits_factor
                    }
                    
                    # Add optional factors if available
                    if doubles_factor:
                        park_data['doubles_factor'] = doubles_factor
                    if triples_factor:
                        park_data['triples_factor'] = triples_factor
                    
                    park_factors.append(park_data)
                    
                except (ValueError, AttributeError) as e:
                    logger.warning(f"Error parsing park factor row: {e}")
                    continue
            
            logger.info(f"Successfully fetched {len(park_factors)} park factors from Statcast")
            return park_factors
            
        except Exception as e:
            logger.error(f"Error fetching park factors from Statcast: {e}")
            return []
    
    def create_default_park_factor(self, stadium_name):
        """
        Create a park factor for a stadium if it doesn't exist, attempting to use real data first
        
        Args:
            stadium_name: Name of the stadium
            
        Returns:
            bool: Whether a new park factor was created
        """
        # Check if park factor already exists
        existing = db.session.query(ParkFactor).filter_by(stadium_name=stadium_name).first()
        if existing:
            logger.info(f"Park factor already exists for {stadium_name}")
            return False
        
        # First try to get real data from Statcast
        statcast_factors = self._fetch_statcast_park_factors()
        stadium_found = False
        
        if statcast_factors:
            for stadium_data in statcast_factors:
                if stadium_name.lower() in stadium_data.get('stadium', '').lower():
                    # Found a match in live data
                    stadium_found = True
                    logger.info(f"Found live park factor data for {stadium_name}")
                    
                    # Create new park factor with live data
                    park_factor = ParkFactor(
                        stadium_name=stadium_name,
                        year=datetime.now().year
                    )
                    
                    # Apply factors from live data
                    if 'runs_factor' in stadium_data:
                        park_factor.runs_factor = stadium_data['runs_factor']
                    if 'hr_factor' in stadium_data:
                        park_factor.hr_factor = stadium_data['hr_factor']
                    if 'hits_factor' in stadium_data:
                        park_factor.hits_factor = stadium_data['hits_factor']
                    if 'doubles_factor' in stadium_data:
                        park_factor.doubles_factor = stadium_data['doubles_factor']
                    if 'triples_factor' in stadium_data:
                        park_factor.triples_factor = stadium_data['triples_factor']
                    
                    break
        
        if not stadium_found:
            # Check fallback data
            fallback_data = self.fallback_park_factors.get(stadium_name)
            
            if fallback_data:
                logger.warning(f"Using fallback data for {stadium_name} - real data should be prioritized")
                
                # Create new park factor with fallback data
                park_factor = ParkFactor(
                    stadium_name=stadium_name,
                    year=datetime.now().year
                )
                
                # Only use non-None values from fallback data
                for key, value in fallback_data.items():
                    if value is not None:
                        setattr(park_factor, key, value)
                
                # Log this usage of fallback data
                self._log_update(False, f"Used fallback data for {stadium_name} - NEEDS LIVE DATA")
            else:
                # As a last resort, create with neutral factors
                logger.warning(f"No data available for {stadium_name}, using neutral factors")
                
                park_factor = ParkFactor(
                    stadium_name=stadium_name,
                    year=datetime.now().year,
                    runs_factor=100.0,  # Neutral
                    hr_factor=100.0,    # Neutral
                    hits_factor=100.0,  # Neutral
                    doubles_factor=100.0,
                    triples_factor=100.0,
                    hr_left_factor=100.0,
                    hr_center_factor=100.0,
                    hr_right_factor=100.0,
                    elevation=500.0,     # Average elevation (will be updated with real data)
                    temperature_effect=0.8,
                    wind_effect=1.0,
                    humidity_effect=0.8,
                    left_handed_advantage=0.0,
                    right_handed_advantage=0.0
                )
                
                # Flag this in the logs
                self._log_update(False, f"Missing data for {stadium_name} - REQUIRES ATTENTION")
            
        # Save to database
        db.session.add(park_factor)
        
        try:
            db.session.commit()
            logger.info(f"Created default park factor for {stadium_name}")
            
            # Log the creation
            log_entry = DataUpdateLog(
                task='create_park_factor',
                success=True,
                details=f"Created default park factor for {stadium_name}"
            )
            db.session.add(log_entry)
            db.session.commit()
            
            return True
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error creating park factor for {stadium_name}: {e}")
            return False
    
    def calculate_weather_adjusted_factors(self, game_id):
        """
        Calculate weather-adjusted park factors for a specific game
        
        Args:
            game_id: Database ID of the game
            
        Returns:
            dict: Weather-adjusted park factors
        """
        try:
            # Get the game
            game = db.session.query(Game).get(game_id)
            if not game or not game.stadium:
                logger.warning(f"No game found with ID {game_id} or no stadium set")
                return None
            
            # Get the park factor
            park_factor = db.session.query(ParkFactor).filter_by(stadium_name=game.stadium).first()
            if not park_factor:
                logger.warning(f"No park factor found for stadium {game.stadium}")
                return None
            
            # Get the latest weather condition
            from .weather_service import WeatherService
            weather_service = WeatherService()
            weather = weather_service.get_latest_weather(game_id)
            
            if not weather:
                logger.warning(f"No weather data found for game {game_id}")
                # Return unadjusted factors as a dictionary
                adjusted_factors = {}
                adjusted_factors['stadium_name'] = park_factor.stadium_name
                adjusted_factors['runs_factor'] = park_factor.runs_factor
                adjusted_factors['hr_factor'] = park_factor.hr_factor
                adjusted_factors['hits_factor'] = park_factor.hits_factor
                adjusted_factors['hr_left_factor'] = park_factor.hr_left_factor if park_factor.hr_left_factor else park_factor.hr_factor
                adjusted_factors['hr_right_factor'] = park_factor.hr_right_factor if park_factor.hr_right_factor else park_factor.hr_factor
                adjusted_factors['elevation'] = park_factor.elevation
                
                # No weather adjustments available
                adjusted_factors['weather_adjusted_run_factor'] = park_factor.runs_factor
                adjusted_factors['weather_adjusted_hr_factor_left'] = adjusted_factors['hr_left_factor']
                adjusted_factors['weather_adjusted_hr_factor_right'] = adjusted_factors['hr_right_factor']
                
                return adjusted_factors
            
            # Create adjusted run factor
            run_factor = park_factor.runs_factor
            
            # Apply temperature adjustment
            if weather.temperature:
                temperature_adjustment = 1.0
                if weather.temperature > 75:  # Warmer weather generally increases scoring
                    temperature_adjustment += (weather.temperature - 75) / 20.0 * 0.05
                elif weather.temperature < 55:  # Colder weather generally decreases scoring
                    temperature_adjustment -= (55 - weather.temperature) / 20.0 * 0.05
                
                run_factor *= temperature_adjustment
            
            # Apply wind adjustment
            if weather.wind_speed and weather.wind_direction:
                wind_adjustment = 1.0
                
                # Wind blowing out increases scoring, wind blowing in decreases it
                if weather.wind_direction.lower() in ['out', 'outfield', 'from home']:
                    wind_adjustment += (weather.wind_speed / 10.0) * 0.04
                elif weather.wind_direction.lower() in ['in', 'infield', 'to home']:
                    wind_adjustment -= (weather.wind_speed / 10.0) * 0.04
                
                run_factor *= wind_adjustment
            
            # Calculate HR factors with weather adjustments
            hr_factor_left = park_factor.hr_left_factor
            hr_factor_right = park_factor.hr_right_factor
            
            # Apply similar adjustments to HR factors
            if weather.temperature:
                hr_temp_adjustment = 1.0
                if weather.temperature > 75:
                    hr_temp_adjustment += (weather.temperature - 75) / 20.0 * 0.07
                elif weather.temperature < 55:
                    hr_temp_adjustment -= (55 - weather.temperature) / 20.0 * 0.07
                
                hr_factor_left *= hr_temp_adjustment
                hr_factor_right *= hr_temp_adjustment
            
            # Create adjusted factors dictionary
            adjusted_factors = {}
            adjusted_factors['stadium_name'] = park_factor.stadium_name
            adjusted_factors['runs_factor'] = park_factor.runs_factor
            adjusted_factors['hr_factor'] = park_factor.hr_factor
            adjusted_factors['hits_factor'] = park_factor.hits_factor
            adjusted_factors['hr_left_factor'] = park_factor.hr_left_factor
            adjusted_factors['hr_right_factor'] = park_factor.hr_right_factor
            adjusted_factors['elevation'] = park_factor.elevation
            
            # Add weather-adjusted values
            adjusted_factors['weather_adjusted_run_factor'] = run_factor
            adjusted_factors['weather_adjusted_hr_factor_left'] = hr_factor_left
            adjusted_factors['weather_adjusted_hr_factor_right'] = hr_factor_right
            
            # Add weather information for reference
            adjusted_factors['current_weather'] = {
                'temperature': weather.temperature,
                'wind_speed': weather.wind_speed,
                'wind_direction': weather.wind_direction,
                'humidity': weather.humidity,
                'description': weather.weather_description
            }
            
            return adjusted_factors
            
        except Exception as e:
            logger.error(f"Error calculating weather-adjusted factors: {e}")
            return None