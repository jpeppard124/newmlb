import logging
import requests
from datetime import datetime, timedelta
from .data_fetcher import DataFetcher
from app import db
from models import Odds, Game, Team, ApiKey
from config import Config

logger = logging.getLogger(__name__)

class OddsService(DataFetcher):
    """Service for fetching betting odds from OddsAPI and Discovery Lab"""
    def __init__(self):
        super().__init__()
        self.odds_api_base_url = self.config.ODDS_API_BASE_URL
        self.discovery_lab_base_url = self.config.DISCOVERY_LAB_BASE_URL
        
    @property
    def odds_api_key(self):
        """Get the Odds API key from the database or fallback to config"""
        api_key = db.session.query(ApiKey).filter_by(service='odds_api', active=True).first()
        if api_key:
            return api_key.key
        return self.config.ODDS_API_KEY
        
    @property
    def discovery_lab_key(self):
        """Get the Discovery Lab API key from the database or fallback to config"""
        api_key = db.session.query(ApiKey).filter_by(service='discovery_lab', active=True).first()
        if api_key:
            return api_key.key
        return self.config.DISCOVERY_LAB_API_KEY
    
    def fetch_odds_api_data(self):
        """Fetch current MLB odds from the Odds API"""
        # Check if we have a valid API key
        if not self.odds_api_key:
            logger.warning("No ODDS_API_KEY provided, cannot fetch data from The Odds API")
            return None
            
        url = f"{self.odds_api_base_url}/sports/baseball_mlb/odds"
        params = {
            'apiKey': self.odds_api_key,
            'regions': 'us',
            'markets': 'h2h,spreads,totals',
            'oddsFormat': 'american',
            'dateFormat': 'iso'
        }
        
        try:
            logger.info("Fetching odds from The Odds API")
            data = self._make_request(url, params=params)
            self._process_odds_api_data(data)
            return data
        except Exception as e:
            logger.error(f"Error fetching odds from The Odds API: {e}")
            raise
    
    def fetch_discovery_lab_data(self):
        """Fetch current MLB odds from Discovery Lab"""
        # Check if we have a valid API key
        if not self.discovery_lab_key:
            logger.warning("No DISCOVERY_LAB_API_KEY provided, cannot fetch data from Discovery Lab API")
            return None
            
        url = f"{self.discovery_lab_base_url}/mlb/odds"
        headers = {
            'Authorization': f'Bearer {self.discovery_lab_key}',
            'Content-Type': 'application/json'
        }
        
        try:
            logger.info("Fetching odds from Discovery Lab API")
            data = self._make_request(url, headers=headers)
            self._process_discovery_lab_data(data)
            return data
        except Exception as e:
            logger.error(f"Error fetching odds from Discovery Lab API: {e}")
            raise
    
    def update_all_odds(self):
        """Update odds from all available sources"""
        success = False
        
        # Try The Odds API if key is available
        if self.odds_api_key:
            try:
                self.fetch_odds_api_data()
                success = True
                logger.info("Successfully updated odds from The Odds API")
            except Exception as e:
                logger.error(f"Error updating odds from The Odds API: {e}")
        else:
            logger.warning("No ODDS_API_KEY provided - skipping The Odds API")
        
        # Try Discovery Lab API if key is available
        if self.discovery_lab_key:
            try:
                self.fetch_discovery_lab_data()
                success = True
                logger.info("Successfully updated odds from Discovery Lab API")
            except Exception as e:
                logger.error(f"Error updating odds from Discovery Lab API: {e}")
        else:
            logger.warning("No DISCOVERY_LAB_API_KEY provided - skipping Discovery Lab API")
            
        if success:
            logger.info("Successfully updated odds from at least one source")
        else:
            logger.warning("No odds data updated - both API keys missing or services failed")
            
    def update_odds_for_date(self, date_str):
        """Update odds for games on a specific date
        
        Args:
            date_str: Date string in YYYY-MM-DD format
            
        Returns:
            bool: True if update was successful, False otherwise
        """
        success = False
        logger.info(f"Updating odds for date: {date_str}")
        
        # Check if we have a valid API key
        if not self.odds_api_key:
            logger.warning("No ODDS_API_KEY provided, cannot fetch data from The Odds API")
            return False
            
        url = f"{self.odds_api_base_url}/sports/baseball_mlb/odds"
        params = {
            'apiKey': self.odds_api_key,
            'regions': 'us',
            'markets': 'h2h,spreads,totals',
            'oddsFormat': 'american',
            'dateFormat': 'iso',
            'date': date_str
        }
        
        try:
            logger.info(f"Fetching odds from The Odds API for date {date_str}")
            data = self._make_request(url, params=params)
            
            if data:
                self._process_odds_api_data(data)
                success = True
                logger.info(f"Successfully updated odds for date {date_str}")
            else:
                logger.warning(f"No odds data received for date {date_str}")
                
        except Exception as e:
            logger.error(f"Error fetching odds for date {date_str}: {e}")
            
        return success
    
    def get_best_odds(self, game_id):
        """
        Get the best available odds for a specific game
        
        Args:
            game_id: Database ID of the game
            
        Returns:
            dict: Best odds for the game across all sportsbooks
        """
        odds = db.session.query(Odds).filter_by(game_id=game_id).all()
        if not odds:
            logger.warning(f"No odds found for game_id {game_id}")
            return None
        
        # Initialize best odds dict
        best_odds = {
            'home_moneyline': {'value': -10000, 'sportsbook': ''},
            'away_moneyline': {'value': -10000, 'sportsbook': ''},
            'home_spread': {'value': 0, 'odds': -10000, 'sportsbook': ''},
            'total_over_under': {'value': 0, 'over_odds': -10000, 'under_odds': -10000, 'sportsbook': ''}
        }
        
        # Find best odds across all sportsbooks
        for odd in odds:
            # Best home moneyline (highest value)
            if odd.home_moneyline > best_odds['home_moneyline']['value']:
                best_odds['home_moneyline'] = {
                    'value': odd.home_moneyline,
                    'sportsbook': odd.sportsbook
                }
            
            # Best away moneyline (highest value)
            if odd.away_moneyline > best_odds['away_moneyline']['value']:
                best_odds['away_moneyline'] = {
                    'value': odd.away_moneyline,
                    'sportsbook': odd.sportsbook
                }
            
            # Best home spread odds (highest value)
            if odd.home_spread_odds > best_odds['home_spread']['odds']:
                best_odds['home_spread'] = {
                    'value': odd.home_spread,
                    'odds': odd.home_spread_odds,
                    'sportsbook': odd.sportsbook
                }
            
            # Best over odds (highest value)
            if odd.over_odds > best_odds['total_over_under']['over_odds']:
                best_odds['total_over_under'] = {
                    'value': odd.total_over_under,
                    'over_odds': odd.over_odds,
                    'under_odds': odd.under_odds,
                    'sportsbook': odd.sportsbook
                }
        
        return best_odds
    
    def calculate_implied_probability(self, american_odds):
        """
        Convert American odds to implied probability
        
        Args:
            american_odds: Odds in American format (e.g., -110, +150)
            
        Returns:
            float: Implied probability as a decimal (0-1)
        """
        if american_odds > 0:
            return 100 / (american_odds + 100)
        else:
            return abs(american_odds) / (abs(american_odds) + 100)
    
    def _process_odds_api_data(self, data):
        """
        Process and store odds data from The Odds API
        
        Args:
            data: JSON data from The Odds API
        """
        if not data:
            logger.warning("No data received from The Odds API")
            return
        
        for game_data in data:
            try:
                # Extract game information
                game_id = game_data.get('id')
                commence_time = datetime.fromisoformat(game_data.get('commence_time').replace('Z', '+00:00'))
                home_team = game_data.get('home_team')
                away_team = game_data.get('away_team')
                
                # Find or create teams
                home_team_obj = self._find_or_create_team(
                    team_id=home_team.lower().replace(' ', ''),
                    name=home_team,
                    abbreviation=home_team[:3].upper()
                )
                
                away_team_obj = self._find_or_create_team(
                    team_id=away_team.lower().replace(' ', ''),
                    name=away_team,
                    abbreviation=away_team[:3].upper()
                )
                
                # Find or create game
                game_obj = self._find_or_create_game(
                    game_id=game_id,
                    home_team_id=home_team_obj.id,
                    away_team_id=away_team_obj.id,
                    game_datetime=commence_time,
                    stadium=""  # The Odds API doesn't provide stadium info
                )
                
                # Process bookmaker odds
                for bookmaker in game_data.get('bookmakers', []):
                    sportsbook = bookmaker.get('title')
                    markets = bookmaker.get('markets', [])
                    
                    # Initialize odds values
                    home_moneyline = None
                    away_moneyline = None
                    home_spread = None
                    home_spread_odds = None
                    away_spread_odds = None
                    total_over_under = None
                    over_odds = None
                    under_odds = None
                    
                    # Extract moneyline odds
                    for market in markets:
                        if market.get('key') == 'h2h':
                            for outcome in market.get('outcomes', []):
                                if outcome.get('name') == home_team:
                                    home_moneyline = outcome.get('price')
                                elif outcome.get('name') == away_team:
                                    away_moneyline = outcome.get('price')
                        
                        # Extract spread odds
                        elif market.get('key') == 'spreads':
                            for outcome in market.get('outcomes', []):
                                if outcome.get('name') == home_team:
                                    home_spread = outcome.get('point')
                                    home_spread_odds = outcome.get('price')
                                elif outcome.get('name') == away_team:
                                    away_spread_odds = outcome.get('price')
                        
                        # Extract totals odds
                        elif market.get('key') == 'totals':
                            total_over_under = market.get('outcomes', [])[0].get('point')
                            for outcome in market.get('outcomes', []):
                                if outcome.get('name') == 'Over':
                                    over_odds = outcome.get('price')
                                elif outcome.get('name') == 'Under':
                                    under_odds = outcome.get('price')
                    
                    # Create or update odds record
                    odds = db.session.query(Odds).filter_by(
                        game_id=game_obj.id,
                        source='oddsapi',
                        sportsbook=sportsbook
                    ).first()
                    
                    if odds:
                        # Update existing record
                        odds.timestamp = datetime.utcnow()
                        odds.home_moneyline = home_moneyline
                        odds.away_moneyline = away_moneyline
                        odds.home_spread = home_spread
                        odds.home_spread_odds = home_spread_odds
                        odds.away_spread_odds = away_spread_odds
                        odds.total_over_under = total_over_under
                        odds.over_odds = over_odds
                        odds.under_odds = under_odds
                    else:
                        # Create new record
                        odds = Odds(
                            game_id=game_obj.id,
                            source='oddsapi',
                            sportsbook=sportsbook,
                            home_moneyline=home_moneyline,
                            away_moneyline=away_moneyline,
                            home_spread=home_spread,
                            home_spread_odds=home_spread_odds,
                            away_spread_odds=away_spread_odds,
                            total_over_under=total_over_under,
                            over_odds=over_odds,
                            under_odds=under_odds
                        )
                        db.session.add(odds)
                
                db.session.commit()
                
            except Exception as e:
                db.session.rollback()
                logger.error(f"Error processing game data from The Odds API: {e}")
    
    def _process_discovery_lab_data(self, data):
        """
        Process and store odds data from Discovery Lab
        
        Args:
            data: JSON data from Discovery Lab API
        """
        if not data:
            logger.warning("No data received from Discovery Lab API")
            return
            
        logger.info(f"Processing odds data from Discovery Lab: {len(data)} entries")
        
        try:
            # We need to adapt this based on the actual Discovery Lab API response format
            # Assuming it has a similar structure to other odds APIs
            for game_entry in data:
                try:
                    # Extract common fields - these field names would need to be adjusted
                    # based on the actual Discovery Lab API response format
                    game_id = game_entry.get('game_id')
                    
                    # Find the game in our database
                    # We may need to match based on teams and date if ID formats differ
                    game = None
                    
                    # Try to find by direct ID match first
                    if game_id:
                        game = db.session.query(Game).filter_by(game_id=str(game_id)).first()
                    
                    # If no game found and we have team information, try to match by teams and date
                    if not game and 'home_team' in game_entry and 'away_team' in game_entry:
                        home_team_name = game_entry.get('home_team')
                        away_team_name = game_entry.get('away_team')
                        game_date = game_entry.get('game_date')
                        
                        # Find teams
                        home_team = db.session.query(Team).filter(Team.name.ilike(f"%{home_team_name}%")).first()
                        away_team = db.session.query(Team).filter(Team.name.ilike(f"%{away_team_name}%")).first()
                        
                        if home_team and away_team and game_date:
                            # Try to parse date
                            try:
                                date_obj = datetime.fromisoformat(game_date)
                                # Find game on this date with these teams
                                game = db.session.query(Game).filter(
                                    Game.home_team_id == home_team.id,
                                    Game.away_team_id == away_team.id,
                                    Game.game_datetime >= date_obj,
                                    Game.game_datetime < date_obj + timedelta(days=1)
                                ).first()
                            except Exception as e:
                                logger.error(f"Error parsing game date: {e}")
                    
                    if not game:
                        logger.warning(f"Could not find matching game for Discovery Lab entry: {game_entry}")
                        continue
                    
                    # Process each sportsbook's odds
                    # Again, this structure depends on the actual API response format
                    for sportsbook_entry in game_entry.get('sportsbooks', []):
                        sportsbook_name = sportsbook_entry.get('name')
                        
                        # Extract odds information
                        home_moneyline = sportsbook_entry.get('home_moneyline')
                        away_moneyline = sportsbook_entry.get('away_moneyline')
                        home_spread = sportsbook_entry.get('home_spread')
                        home_spread_odds = sportsbook_entry.get('home_spread_odds')
                        away_spread_odds = sportsbook_entry.get('away_spread_odds')
                        total_over_under = sportsbook_entry.get('total')
                        over_odds = sportsbook_entry.get('over_odds')
                        under_odds = sportsbook_entry.get('under_odds')
                        
                        # Create or update odds record
                        odds = db.session.query(Odds).filter_by(
                            game_id=game.id,
                            source='discoverylab',
                            sportsbook=sportsbook_name
                        ).first()
                        
                        if odds:
                            # Update existing record
                            odds.timestamp = datetime.utcnow()
                            odds.home_moneyline = home_moneyline
                            odds.away_moneyline = away_moneyline
                            odds.home_spread = home_spread
                            odds.home_spread_odds = home_spread_odds
                            odds.away_spread_odds = away_spread_odds
                            odds.total_over_under = total_over_under
                            odds.over_odds = over_odds
                            odds.under_odds = under_odds
                        else:
                            # Create new record
                            odds = Odds(
                                game_id=game.id,
                                source='discoverylab',
                                sportsbook=sportsbook_name,
                                home_moneyline=home_moneyline,
                                away_moneyline=away_moneyline,
                                home_spread=home_spread,
                                home_spread_odds=home_spread_odds,
                                away_spread_odds=away_spread_odds,
                                total_over_under=total_over_under,
                                over_odds=over_odds,
                                under_odds=under_odds
                            )
                            db.session.add(odds)
                    
                except Exception as e:
                    logger.error(f"Error processing Discovery Lab game entry: {e}")
                    continue
            
            db.session.commit()
            logger.info("Successfully processed Discovery Lab odds data")
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error processing Discovery Lab data: {e}")
        
    def _find_or_create_team(self, team_id, name, abbreviation):
        """
        Find or create a team in the database
        
        Args:
            team_id: Unique team identifier
            name: Team name
            abbreviation: Team abbreviation
            
        Returns:
            Team: Team object from the database
        """
        # Try to find team by ID first
        team = db.session.query(Team).filter_by(team_id=team_id).first()
        
        # If not found, try by abbreviation
        if not team:
            team = db.session.query(Team).filter_by(abbreviation=abbreviation).first()
            
        # If still not found, try name contains
        if not team:
            team = db.session.query(Team).filter(Team.name.ilike(f"%{name}%")).first()
            
        if team:
            # Team exists, but make sure we have this format stored too
            if team.team_id != team_id:
                logger.info(f"Adding alternate team ID mapping: {team.team_id} -> {team_id} for {name}")
                # We could create a TeamMapping table for this in the future
                # For now, we'll keep the original team_id
            
            # Update team info if needed
            if team.name != name or team.abbreviation != abbreviation:
                team.name = name
                team.abbreviation = abbreviation
                db.session.commit()
        else:
            # Create new team
            logger.info(f"Creating new team: {team_id} ({name}, {abbreviation})")
            team = Team(
                team_id=team_id,
                name=name,
                abbreviation=abbreviation
            )
            db.session.add(team)
            db.session.commit()
            
        return team
        
    def _find_or_create_game(self, game_id, home_team_id, away_team_id, game_datetime, stadium=""):
        """
        Find or create a game in the database
        
        Args:
            game_id: Unique game identifier
            home_team_id: Database ID of the home team
            away_team_id: Database ID of the away team
            game_datetime: Scheduled game date and time
            stadium: Stadium name
            
        Returns:
            Game: Game object from the database
        """
        game = db.session.query(Game).filter_by(game_id=game_id).first()
        
        if game:
            # Update existing game
            game.home_team_id = home_team_id
            game.away_team_id = away_team_id
            game.game_datetime = game_datetime
            game.stadium = stadium
        else:
            # Create new game
            game = Game(
                game_id=game_id,
                home_team_id=home_team_id,
                away_team_id=away_team_id,
                game_datetime=game_datetime,
                stadium=stadium,
                status='scheduled'
            )
            db.session.add(game)
            db.session.commit()
            
        return game
        
    # Let the parent class handle the _make_request method
    # def _make_request(self, url, params=None, headers=None):
    #     """Make a GET request to the API"""
    #     response = requests.get(url, params=params, headers=headers)
    #     response.raise_for_status()
    #     return response.json()
