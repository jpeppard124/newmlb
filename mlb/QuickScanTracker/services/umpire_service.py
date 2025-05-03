"""
Umpire Data Service

This service fetches and processes umpire data from Swish Analytics and other sources.
It incorporates umpire assignments into game predictions once they're available (1-3 hours before games).
"""

import logging
import requests
import time
import random
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
import trafilatura
from app import db
from models import Game, UmpireStats, DataUpdateLog, game_umpire
from config import Config
from .data_service_interface import DataServiceInterface

logger = logging.getLogger(__name__)

class UmpireService(DataServiceInterface):
    """Service for managing umpire data and assignments"""
    
    def __init__(self):
        super().__init__()
        self.config = Config()
        self.swish_analytics_url = "https://swishanalytics.com/mlb/mlb-umpire-factors"
        
        # Map for umpire names and common variations
        self.umpire_name_map = {
            # Add common variations of umpire names here
            "CB Bucknor": ["C.B. Bucknor", "C. B. Bucknor", "CB Bucknor"],
            "Joe West": ["Joe West", "Joseph West"],
            # Add more as needed
        }
    
    def ensure_data(self, days_ahead=1):
        """
        Ensure all games have umpire data if available
        
        This method is called by the data integrity system.
        Since umpire assignments are available 1-3 hours before games,
        we only check today's and tomorrow's games.
        
        Args:
            days_ahead: Number of days to look ahead (default is 1 for today/tomorrow)
            
        Returns:
            bool: Whether umpire data was updated
        """
        with db.session.no_autoflush:
            logger.info("Checking for new umpire assignments")
            
            # Get today's and tomorrow's games
            today = datetime.now()
            tomorrow = today + timedelta(days=1)
            
            upcoming_games = db.session.query(Game).filter(
                Game.game_datetime >= today,
                Game.game_datetime <= tomorrow
            ).all()
            
            # Filter for games within 6 hours from now (umpires are typically assigned 1-3 hours before)
            games_soon = [g for g in upcoming_games if (g.game_datetime - today).total_seconds() <= 21600]
            
            if not games_soon:
                logger.info("No games within the next 6 hours")
                return False
            
            logger.info(f"Checking umpire assignments for {len(games_soon)} upcoming games")
            
            # Check for umpire assignments
            assignments_updated = self._update_umpire_assignments(games_soon)
            
            if assignments_updated:
                # If we got new assignments, update any missing umpire stats
                self._update_umpire_statistics()
                logger.info("Umpire data updated successfully")
                
                # Log the update
                self._log_update('update_umpire_data', True, 
                                 f"Updated umpire data for upcoming games")
            
            return assignments_updated
    
    def _update_umpire_assignments(self, games):
        """
        Check for and update umpire assignments for upcoming games from official MLB sources
        
        Args:
            games: List of upcoming Game objects
            
        Returns:
            bool: Whether any assignments were updated
        """
        try:
            logger.info("Checking for umpire assignments from official MLB sources")
            
            # Track updated games
            updated_count = 0
            
            # Iterate through each upcoming game to find umpire assignments
            for game in games:
                # First check MLB.com game preview
                umpire_assigned = self._scrape_mlb_preview_for_umpires(game)
                
                # If not found, try MLB API
                if not umpire_assigned:
                    umpire_assigned = self._scrape_mlb_api_for_umpires(game)
                
                # If still not found, try Swish Analytics 
                if not umpire_assigned:
                    umpire_assigned = self._scrape_swish_for_umpires(game)
                
                # If any source successfully returned umpire data
                if umpire_assigned:
                    updated_count += 1
                else:
                    # Log the fact we couldn't find data for this game
                    logger.info(f"No umpire data available yet for game {game.id}: {game.home_team.name} vs {game.away_team.name}")
                    
            # Report results
            if updated_count > 0:
                logger.info(f"Found umpire assignments for {updated_count} games from official sources")
            else:
                logger.info("No new umpire assignments found at this time - this is normal more than 3 hours before game time")
                
            return updated_count > 0
            
        except Exception as e:
            logger.error(f"Error updating umpire assignments: {e}")
            return False
    
    def _scrape_mlb_preview_for_umpires(self, game):
        """
        Scrape MLB.com game preview page for umpire assignments
        
        Args:
            game: Game object
            
        Returns:
            bool: Whether an umpire was assigned
        """
        # Check if this game already has an umpire assigned
        game_has_umpire = len(game.umpires) > 0
        
        if game_has_umpire:
            logger.info(f"Game {game.id} already has umpire(s) assigned")
            return True
            
        # Only check games happening soon (within 3 hours)
        game_soon = (game.game_datetime - datetime.now()).total_seconds() < 10800  # 3 hours in seconds
        if not game_soon:
            logger.debug(f"Game {game.id} is not happening soon, skipping umpire preview check")
            return False
            
        try:
            # Format game date
            game_date = game.game_date.strftime("%Y-%m-%d")
            away_team_name = game.away_team.name.lower().replace(' ', '-')
            home_team_name = game.home_team.name.lower().replace(' ', '-')
            
            # MLB.com uses team names in URLs - construct the URL
            preview_url = f"https://www.mlb.com/gameday/{away_team_name}-vs-{home_team_name}/{game_date}"
            
            logger.info(f"Checking MLB preview at {preview_url} for umpire assignments")
            
            # Get the page content
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            response = requests.get(preview_url, headers=headers, timeout=10)
            
            if not response.ok:
                logger.error(f"Failed to download MLB preview page: {response.status_code}")
                return False
                
            # Parse HTML and extract umpire information
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Look for umpire section - MLB.com typically has this in a section with "umpires" in the text
            umpire_section = None
            
            # Look for umpire information in various formats
            for section in soup.find_all(['section', 'div']):
                if section.text and 'umpire' in section.text.lower():
                    umpire_section = section
                    break
                    
            if not umpire_section:
                logger.info(f"No umpire information found in MLB preview for game {game.id}")
                return False
                
            # Extract umpire names
            umpire_names = []
            
            # Process umpire section to find names
            for item in umpire_section.find_all(['li', 'p', 'div']):
                text = item.text.strip()
                
                # Look for patterns like "Home: Joe West" or "HP: Joe West"
                if ':' in text and ('home' in text.lower() or 'hp' in text.lower()):
                    umpire_name = text.split(':', 1)[1].strip()
                    umpire_names.append(umpire_name)
                    break
                    
            if not umpire_names:
                logger.info(f"Could not extract umpire names from preview for game {game.id}")
                return False
                
            # Use the first umpire (home plate) we found
            umpire_name = umpire_names[0]
            
            # Find or create the umpire in our database
            umpire = UmpireStats.query.filter(UmpireStats.name == umpire_name).first()
            
            if not umpire:
                logger.info(f"Creating new umpire record for {umpire_name}")
                umpire = UmpireStats(
                    name=umpire_name,
                    k_boost=1.0,  # Neutral default
                    bb_boost=1.0,  # Neutral default
                    r_boost=1.0,   # Neutral default
                    games_called=0  # Will be updated later
                )
                db.session.add(umpire)
                db.session.flush()  # Get ID without committing transaction
                
            # Create the association in the junction table
            db.session.execute(
                game_umpire.insert().values(
                    game_id=game.id,
                    umpire_id=umpire.id,
                    position='home_plate',
                    assigned_at=datetime.utcnow()
                )
            )
            
            db.session.commit()
            logger.info(f"Assigned home plate umpire {umpire.name} to game {game.id} from MLB preview")
            return True
            
        except Exception as e:
            logger.error(f"Error scraping MLB preview for game {game.id}: {e}")
            db.session.rollback()
            return False
            
    def _scrape_mlb_api_for_umpires(self, game):
        """
        Check MLB API for umpire assignments
        
        Args:
            game: Game object
            
        Returns:
            bool: Whether an umpire was assigned
        """
        # Skip if umpire already assigned
        if len(game.umpires) > 0:
            return True
            
        try:
            # MLB Stats API endpoint - would need MLB API credentials in production
            game_date = game.game_date.strftime("%Y-%m-%d")
            
            # Log that we're checking the API
            logger.info(f"Checking MLB API for umpire data for game {game.id} on {game_date}")
            
            # This would be a real API call in production
            # For now, we'll return False to indicate no data found via this source
            # This will allow us to fall back to other data sources
            return False
            
        except Exception as e:
            logger.error(f"Error checking MLB API for umpires: {e}")
            return False
            
    def _scrape_swish_for_umpires(self, game):
        """
        Check Swish Analytics for umpire assignments
        
        Args:
            game: Game object
            
        Returns:
            bool: Whether an umpire was assigned
        """
        # Skip if umpire already assigned
        if len(game.umpires) > 0:
            return True
            
        try:
            # Check if game is happening today (Swish typically only shows today's games)
            today = datetime.now().date()
            game_date = game.game_date
            
            if game_date != today:
                logger.debug(f"Game {game.id} is not today, skipping Swish Analytics check")
                return False
                
            logger.info(f"Checking Swish Analytics for umpire data for game {game.id}")
            
            # In production, this would scrape the Swish Analytics page for today's games
            # For now, this is a placeholder
            
            # We'd look for a match between the teams in the game and teams on the Swish page
            # When found, we would extract the umpire name and update our database
            
            # Return False to indicate no umpire data found via this method
            return False
            
        except Exception as e:
            logger.error(f"Error checking Swish Analytics for umpires: {e}")
            return False
    
    def _update_umpire_statistics(self):
        """
        Update umpire statistics from Swish Analytics
        
        This method scrapes the Swish Analytics umpire page to get the latest umpire statistics.
        """
        try:
            logger.info("Updating umpire statistics from Swish Analytics")
            
            # In a production implementation, this would scrape the Swish Analytics page
            # and update umpire statistics in the database
            
            # Get existing umpires in the database
            existing_umpires = {u.name: u for u in db.session.query(UmpireStats).all()}
            
            # Scrape the Swish Analytics page
            umpire_data = self._scrape_swish_analytics()
            
            if not umpire_data:
                logger.warning("No umpire data found from Swish Analytics")
                return False
            
            # Update umpire statistics in the database
            for umpire_name, stats in umpire_data.items():
                # Check if umpire exists in database
                if umpire_name in existing_umpires:
                    # Update existing umpire
                    umpire = existing_umpires[umpire_name]
                    for key, value in stats.items():
                        if hasattr(umpire, key):
                            setattr(umpire, key, value)
                else:
                    # Create new umpire
                    stats['name'] = umpire_name
                    new_umpire = UmpireStats(**stats)
                    db.session.add(new_umpire)
            
            # Commit changes
            db.session.commit()
            logger.info(f"Updated statistics for {len(umpire_data)} umpires")
            return True
            
        except Exception as e:
            logger.error(f"Error updating umpire statistics: {e}")
            db.session.rollback()
            return False
    
    def _scrape_swish_analytics(self):
        """
        Scrape umpire data from Swish Analytics
        
        Returns:
            dict: Dictionary of umpire data
        """
        try:
            logger.info(f"Scraping umpire data from {self.swish_analytics_url}")
            
            # Get the page content
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            response = requests.get(self.swish_analytics_url, headers=headers)
            
            if not response.ok:
                logger.error(f"Failed to download Swish Analytics page: {response.status_code}")
                return {}
            
            # Parse the HTML
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Extract umpire data from the table
            umpire_data = {}
            
            # Find the umpire table - this selector would need to be adjusted based on the actual page structure
            table = soup.find('table', {'class': 'umpire-factors-table'}) 
            
            # If we can't find the table with the expected class, try to find any table
            if not table:
                logger.warning("Could not find umpire table with expected class, trying generic table search")
                tables = soup.find_all('table')
                if tables:
                    # Use the table most likely to contain umpire data (usually the largest one)
                    table = max(tables, key=lambda t: len(t.find_all('tr')))
            
            if not table:
                logger.error("Could not find any table with umpire data")
                
                # As a fallback, try using trafilatura to get the raw text and look for patterns
                downloaded = trafilatura.fetch_url(self.swish_analytics_url)
                text = trafilatura.extract(downloaded)
                
                if text and "K Boost" in text and "BB Boost" in text:
                    logger.info("Found umpire data in raw text, attempting to parse")
                    # Parse raw text - this is a simplified parser and would need to be refined
                    lines = text.split('\n')
                    current_umpire = None
                    
                    for line in lines:
                        if not line.strip():
                            continue
                            
                        # Look for lines that might be umpire names (typically just Name without numbers)
                        if all(not c.isdigit() for c in line) and len(line.split()) <= 3 and line not in ["K Boost", "BB Boost", "R Boost"]:
                            current_umpire = line.strip()
                            if current_umpire and current_umpire not in umpire_data:
                                umpire_data[current_umpire] = {
                                    'k_boost': 1.0,
                                    'bb_boost': 1.0,
                                    'r_boost': 1.0,
                                    'ba_boost': 1.0,
                                    'obp_boost': 1.0,
                                    'slg_boost': 1.0,
                                    'games_called': 0
                                }
                        
                        # Look for lines with boost values
                        elif current_umpire and "Boost" in line:
                            parts = line.split()
                            if len(parts) >= 2 and parts[-1].replace('.', '', 1).isdigit():
                                value = float(parts[-1])
                                
                                if "K Boost" in line:
                                    umpire_data[current_umpire]['k_boost'] = value
                                elif "BB Boost" in line:
                                    umpire_data[current_umpire]['bb_boost'] = value
                                elif "R Boost" in line: 
                                    umpire_data[current_umpire]['r_boost'] = value
                                elif "BA Boost" in line:
                                    umpire_data[current_umpire]['ba_boost'] = value
                                elif "OBP Boost" in line:
                                    umpire_data[current_umpire]['obp_boost'] = value
                                elif "SLG Boost" in line:
                                    umpire_data[current_umpire]['slg_boost'] = value
                
                if umpire_data:
                    logger.info(f"Extracted {len(umpire_data)} umpires from raw text")
                    return umpire_data
                
                return {}
            
            # Extract data from the table
            rows = table.find_all('tr')
            
            # Skip header row
            for row in rows[1:]:
                cells = row.find_all('td')
                
                # Make sure we have enough cells
                if len(cells) < 7:
                    continue
                
                # Extract umpire name and stats
                umpire_name = cells[0].get_text().strip()
                
                # Skip empty names
                if not umpire_name:
                    continue
                
                # Extract stats - cell indices would need to be adjusted based on actual table structure
                try:
                    k_boost = float(cells[1].get_text().strip())
                    bb_boost = float(cells[2].get_text().strip()) 
                    r_boost = float(cells[3].get_text().strip())
                    ba_boost = float(cells[4].get_text().strip())
                    obp_boost = float(cells[5].get_text().strip())
                    slg_boost = float(cells[6].get_text().strip())
                    games_called = int(cells[7].get_text().strip()) if len(cells) > 7 else 0
                except (ValueError, IndexError):
                    # If we can't parse some values, use defaults
                    k_boost = 1.0
                    bb_boost = 1.0
                    r_boost = 1.0
                    ba_boost = 1.0
                    obp_boost = 1.0
                    slg_boost = 1.0
                    games_called = 0
                
                # Store the umpire data
                umpire_data[umpire_name] = {
                    'k_boost': k_boost,
                    'bb_boost': bb_boost,
                    'r_boost': r_boost,
                    'ba_boost': ba_boost,
                    'obp_boost': obp_boost,
                    'slg_boost': slg_boost,
                    'games_called': games_called
                }
            
            logger.info(f"Extracted data for {len(umpire_data)} umpires")
            return umpire_data
            
        except Exception as e:
            logger.error(f"Error scraping Swish Analytics: {e}")
            return {}
    
    def get_umpire_for_game(self, game_id):
        """
        Get the umpire assigned to a specific game
        
        Args:
            game_id: ID of the game
            
        Returns:
            UmpireStats: Umpire stats object or None
        """
        # Query the game to get associated umpires
        game = Game.query.get(game_id)
        if not game:
            logger.warning(f"Game with ID {game_id} not found")
            return None
            
        # Get the home plate umpire (assuming first umpire in the list or with position='home_plate')
        if game.umpires:
            # Check if we have position information in the junction table
            for ump_assoc in db.session.query(game_umpire).filter_by(game_id=game_id).all():
                if ump_assoc.position == 'home_plate':
                    return UmpireStats.query.get(ump_assoc.umpire_id)
            
            # If no specific home plate umpire, return the first umpire
            return game.umpires[0] if game.umpires else None
        
        return None
    
    def _log_update(self, task, success, details):
        """
        Log data update operation to database
        
        Args:
            task: Type of update (e.g., 'update_umpire_data')
            success: Whether the update was successful
            details: Details or error message
        """
        log_entry = DataUpdateLog(
            task=task,
            success=success,
            details=details
        )
        db.session.add(log_entry)
        
        try:
            db.session.commit()
        except Exception as e:
            logger.error(f"Error logging update: {e}")
            db.session.rollback()
    
    def get_umpire_factors(self, game_id):
        """
        Get umpire adjustment factors for a specific game
        
        These factors are used to adjust prediction models based on the umpire's
        tendencies (strikeout rate, walk rate, runs per game, etc.)
        
        Args:
            game_id: ID of the game
            
        Returns:
            dict: Dictionary of umpire adjustment factors
        """
        try:
            # Get the game
            game = db.session.query(Game).filter(Game.id == game_id).first()
            
            if not game:
                logger.error(f"Game {game_id} not found")
                # Return MLB league averages with data source labeled
                return {
                    'name': 'Not assigned',
                    'games_called': 0,
                    'k_boost': 1.0,
                    'bb_boost': 1.0,
                    'r_boost': 1.0,
                    'ba_boost': 1.0,
                    'obp_boost': 1.0,
                    'slg_boost': 1.0,
                    'data_source': 'MLB League Average (game not found)'
                }
            
            # Check if game is happening soon - umpires are usually assigned 2-3 hours before game time
            game_soon = (game.game_datetime - datetime.now()).total_seconds() < 10800  # 3 hours
            
            # Get the umpire for this game
            umpire = self.get_umpire_for_game(game_id)
            
            # If no umpire and game is soon, try to refresh umpire data
            if not umpire and game_soon:
                logger.info(f"Game {game_id} is happening soon, checking for umpire data")
                self._update_umpire_assignments([game])
                umpire = self.get_umpire_for_game(game_id)  # Try again after update
            
            if not umpire:
                logger.warning(f"No umpire assigned for game {game_id}")
                # Return MLB league averages with data source labeled
                return {
                    'name': 'Not assigned',
                    'games_called': 0,
                    'k_boost': 1.0,
                    'bb_boost': 1.0,
                    'r_boost': 1.0,
                    'ba_boost': 1.0,
                    'obp_boost': 1.0,
                    'slg_boost': 1.0,
                    'data_source': 'MLB League Average (umpire not yet assigned)'
                }
            
            # Check if we need to update umpire stats
            if umpire.k_boost == 1.0 and umpire.bb_boost == 1.0 and umpire.r_boost == 1.0:
                logger.info(f"Updating stats for umpire {umpire.name}")
                self._update_umpire_statistics()
                # Refresh umpire data
                umpire = db.session.query(UmpireStats).filter(UmpireStats.id == umpire.id).first()
                
            # Return the umpire's adjustment factors with safety checks for null values
            factors = {
                'name': umpire.name,
                'games_called': umpire.games_called or 0,
                'k_boost': umpire.k_boost or 1.0,
                'bb_boost': umpire.bb_boost or 1.0,
                'r_boost': umpire.r_boost or 1.0,
                'ba_boost': umpire.ba_boost or 1.0,
                'obp_boost': umpire.obp_boost or 1.0,
                'slg_boost': umpire.slg_boost or 1.0,
                'data_source': f'Swish Analytics (Umpire: {umpire.name})'
            }
            
            logger.info(f"Umpire factors for game {game_id}: {umpire.name}, K: {umpire.k_boost}, R: {umpire.r_boost}")
            return factors
            
        except Exception as e:
            logger.error(f"Error getting umpire factors for game {game_id}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            
            # Return MLB league averages with error indicated
            return {
                'name': 'Error',
                'games_called': 0,
                'k_boost': 1.0,
                'bb_boost': 1.0,
                'r_boost': 1.0,
                'ba_boost': 1.0,
                'obp_boost': 1.0,
                'slg_boost': 1.0,
                'data_source': 'MLB League Average (error retrieving umpire data)'
            }