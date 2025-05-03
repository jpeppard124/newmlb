from datetime import datetime
from app import db

# Junction table for Game-Umpire many-to-many relationship
game_umpire = db.Table('game_umpire',
    db.Column('game_id', db.Integer, db.ForeignKey('game.id'), primary_key=True),
    db.Column('umpire_id', db.Integer, db.ForeignKey('umpire_stats.id'), primary_key=True),
    db.Column('position', db.String(20)),  # e.g., 'home_plate', 'first_base', etc.
    db.Column('assigned_at', db.DateTime, default=datetime.utcnow)
)

class Team(db.Model):
    """MLB Team information"""
    id = db.Column(db.Integer, primary_key=True)
    team_id = db.Column(db.String(50), unique=True, nullable=False)  # MLB team ID
    name = db.Column(db.String(100), nullable=False)
    abbreviation = db.Column(db.String(10), nullable=False)
    stadium = db.Column(db.String(100))  # Team's home stadium
    stadium_location = db.Column(db.String(100))  # Stadium location for weather lookup
    home_games = db.relationship('Game', foreign_keys='Game.home_team_id', backref='home_team', lazy=True)
    away_games = db.relationship('Game', foreign_keys='Game.away_team_id', backref='away_team', lazy=True)
    
    def __repr__(self):
        return f'<Team {self.name}>'

class Game(db.Model):
    """MLB Game information"""
    id = db.Column(db.Integer, primary_key=True)
    game_id = db.Column(db.String(50), unique=True, nullable=False)  # MLB game ID
    game_datetime = db.Column(db.DateTime, nullable=False)
    home_team_id = db.Column(db.Integer, db.ForeignKey('team.id'), nullable=False)
    away_team_id = db.Column(db.Integer, db.ForeignKey('team.id'), nullable=False)
    stadium = db.Column(db.String(100))
    status = db.Column(db.String(20), default='scheduled')  # scheduled, in_progress, final
    home_score = db.Column(db.Integer)
    away_score = db.Column(db.Integer)
    weather_conditions = db.relationship('WeatherCondition', backref='game', lazy=True)
    odds = db.relationship('Odds', backref='game', lazy=True)
    predictions = db.relationship('Prediction', backref='game', lazy=True)
    # Umpire relationship is defined via the game_umpire junction table in the UmpireStats model
    
    def __repr__(self):
        return f'<Game {self.away_team.abbreviation} @ {self.home_team.abbreviation} on {self.game_datetime}>'

class WeatherCondition(db.Model):
    """Weather data for a game"""
    id = db.Column(db.Integer, primary_key=True)
    game_id = db.Column(db.Integer, db.ForeignKey('game.id'), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    temperature = db.Column(db.Float)  # in Fahrenheit
    humidity = db.Column(db.Float)  # percentage
    wind_speed = db.Column(db.Float)  # mph
    wind_direction = db.Column(db.String(20))  # N, NE, E, etc.
    precipitation_chance = db.Column(db.Float)  # percentage
    weather_description = db.Column(db.String(100))
    
    def __repr__(self):
        return f'<Weather for Game #{self.game_id}: {self.temperature}°F, {self.wind_speed} mph {self.wind_direction}>'

class Odds(db.Model):
    """Betting odds for a game from various sportsbooks"""
    id = db.Column(db.Integer, primary_key=True)
    game_id = db.Column(db.Integer, db.ForeignKey('game.id'), nullable=False)
    source = db.Column(db.String(50), nullable=False)  # e.g., 'oddsapi', 'discoverylab'
    sportsbook = db.Column(db.String(50), nullable=False)  # e.g., 'DraftKings', 'FanDuel'
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    home_moneyline = db.Column(db.Integer)
    away_moneyline = db.Column(db.Integer)
    home_spread = db.Column(db.Float)
    home_spread_odds = db.Column(db.Integer)
    away_spread_odds = db.Column(db.Integer)
    total_over_under = db.Column(db.Float)
    over_odds = db.Column(db.Integer)
    under_odds = db.Column(db.Integer)
    
    def __repr__(self):
        return f'<Odds for Game #{self.game_id} from {self.sportsbook}>'

class PlayerStats(db.Model):
    """Player statistics from Statcast and other sources"""
    id = db.Column(db.Integer, primary_key=True)
    player_id = db.Column(db.String(20), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    team_id = db.Column(db.Integer, db.ForeignKey('team.id'))
    position = db.Column(db.String(10))
    date = db.Column(db.Date, nullable=False)
    
    # Batting metrics
    pa = db.Column(db.Integer)  # Plate appearances
    ab = db.Column(db.Integer)  # At bats
    hits = db.Column(db.Integer)
    hr = db.Column(db.Integer)  # Home runs
    avg = db.Column(db.Float)  # Batting average
    obp = db.Column(db.Float)  # On-base percentage
    slg = db.Column(db.Float)  # Slugging percentage
    ops = db.Column(db.Float)  # On-base plus slugging
    woba = db.Column(db.Float)  # Weighted on-base average
    xwoba = db.Column(db.Float)  # Expected weighted on-base average
    barrel_pct = db.Column(db.Float)  # Barrel percentage
    
    # Pitching metrics
    innings_pitched = db.Column(db.Float)
    strikeouts = db.Column(db.Integer)
    walks = db.Column(db.Integer)
    era = db.Column(db.Float)  # Earned run average
    whip = db.Column(db.Float)  # Walks + Hits per Inning Pitched
    fip = db.Column(db.Float)  # Fielding Independent Pitching
    xfip = db.Column(db.Float)  # Expected Fielding Independent Pitching
    
    team = db.relationship('Team', backref=db.backref('player_stats', lazy=True))
    
    def __repr__(self):
        return f'<PlayerStats {self.name} on {self.date}>'

class Prediction(db.Model):
    """Model predictions for a game"""
    id = db.Column(db.Integer, primary_key=True)
    game_id = db.Column(db.Integer, db.ForeignKey('game.id'), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Win probability
    home_win_probability = db.Column(db.Float)
    
    # Run predictions
    predicted_home_runs = db.Column(db.Float)
    predicted_away_runs = db.Column(db.Float)
    predicted_total_runs = db.Column(db.Float)
    
    # Model confidence scores (0-1 scale)
    home_win_confidence = db.Column(db.Float)
    total_runs_confidence = db.Column(db.Float)
    
    # Value metrics - calculated based on current best odds
    home_moneyline_value = db.Column(db.Float)  # Expected value percentage
    away_moneyline_value = db.Column(db.Float)
    over_value = db.Column(db.Float)
    under_value = db.Column(db.Float)
    
    # Recommended bets
    recommended_bet = db.Column(db.String(100))  # e.g., 'Home Moneyline', 'Under'
    
    # Feature importance metrics
    feature_importance = db.Column(db.JSON)  # SHAP values for key features
    explanation_text = db.Column(db.JSON)  # Human-readable explanation of prediction
    
    # Performance tracking
    actual_home_score = db.Column(db.Integer)
    actual_away_score = db.Column(db.Integer)
    prediction_successful = db.Column(db.Boolean)
    bet_roi = db.Column(db.Float)  # ROI for recommended bet if it was placed
    brier_score = db.Column(db.Float)  # Measure of probability calibration (lower is better)
    total_runs_error = db.Column(db.Float)  # Absolute error in total runs prediction
    
    def __repr__(self):
        return f'<Prediction for Game #{self.game_id} at {self.timestamp}>'

class PerformanceLog(db.Model):
    """Model performance tracking"""
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False)
    bet_type = db.Column(db.String(50), nullable=False)  # e.g., 'moneyline', 'over/under'
    total_bets = db.Column(db.Integer, default=0)
    winning_bets = db.Column(db.Integer, default=0)
    profit_loss = db.Column(db.Float, default=0.0)  # In units
    roi = db.Column(db.Float)  # Return on Investment percentage
    
    def __repr__(self):
        return f'<Performance {self.bet_type} on {self.date}: ROI {self.roi}%>'

class UmpireStats(db.Model):
    """Umpire statistics for strike zone tendencies"""
    id = db.Column(db.Integer, primary_key=True)
    umpire_id = db.Column(db.String(20), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    games_called = db.Column(db.Integer)
    
    # Traditional statistics
    kzone_size = db.Column(db.Float)  # Strike zone size relative to average (1.0 = average)
    runs_per_game = db.Column(db.Float)  # Average runs in games called
    strikeouts_per_game = db.Column(db.Float)  # Average strikeouts in games called
    
    # Swish Analytics boost factors
    k_boost = db.Column(db.Float, default=1.0)  # StriKeout boost factor
    bb_boost = db.Column(db.Float, default=1.0)  # Base on Balls (walk) boost factor
    r_boost = db.Column(db.Float, default=1.0)  # Run scoring boost factor
    ba_boost = db.Column(db.Float, default=1.0)  # Batting Average boost factor
    obp_boost = db.Column(db.Float, default=1.0)  # On Base Percentage boost factor
    slg_boost = db.Column(db.Float, default=1.0)  # SLuGging percentage boost factor
    
    # Timestamps for data tracking
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Game relationships
    games = db.relationship('Game', secondary='game_umpire', backref='umpires')
    
    def __repr__(self):
        return f'<Umpire {self.name}: K-Boost {self.k_boost}, R-Boost {self.r_boost}>'

class DataUpdateLog(db.Model):
    """Log of data update operations"""
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    task = db.Column(db.String(50), nullable=False)  # Type of update (e.g., 'update_teams', 'update_odds')
    success = db.Column(db.Boolean, default=True)
    details = db.Column(db.String(500))  # Details or error message

    def __repr__(self):
        status = "Success" if self.success else "Failed"
        return f'<DataUpdateLog {self.task} {status} {self.timestamp}>'
        
class ApiKey(db.Model):
    """API Keys stored in the database"""
    id = db.Column(db.Integer, primary_key=True)
    service = db.Column(db.String(50), unique=True, nullable=False)  # e.g., 'odds_api', 'weather_api'
    key = db.Column(db.String(200), nullable=False)
    active = db.Column(db.Boolean, default=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        # Don't show the actual key in logs or debug output
        key_preview = self.key[:4] + "****" if self.key else None
        return f'<ApiKey for {self.service}: {key_preview}>'


class ParkFactor(db.Model):
    """
    Park factors data for MLB stadiums
    Park factors measure how much a specific stadium affects offensive statistics
    A value of 100 is neutral, >100 favors hitters, <100 favors pitchers
    """
    id = db.Column(db.Integer, primary_key=True)
    stadium_name = db.Column(db.String(100), nullable=False, unique=True)
    year = db.Column(db.Integer, nullable=False, default=datetime.now().year)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Overall park factors
    runs_factor = db.Column(db.Float, default=100.0)  # Overall run scoring environment
    hr_factor = db.Column(db.Float, default=100.0)  # Home run factor
    hits_factor = db.Column(db.Float, default=100.0)  # Overall hits factor
    doubles_factor = db.Column(db.Float, default=100.0)  # Doubles factor
    triples_factor = db.Column(db.Float, default=100.0)  # Triples factor
    
    # Directional home run factors
    hr_left_factor = db.Column(db.Float, default=100.0)  # HR factor to left field
    hr_center_factor = db.Column(db.Float, default=100.0)  # HR factor to center field
    hr_right_factor = db.Column(db.Float, default=100.0)  # HR factor to right field
    
    # Weather and environment related
    elevation = db.Column(db.Float)  # Stadium elevation in feet
    temperature_effect = db.Column(db.Float, default=0.0)  # How much temperature affects scoring
    wind_effect = db.Column(db.Float, default=0.0)  # Wind impact on scoring
    humidity_effect = db.Column(db.Float, default=0.0)  # Humidity impact on scoring
    
    # Handedness advantages
    left_handed_advantage = db.Column(db.Float, default=0.0)  # Impact for left-handed batters
    right_handed_advantage = db.Column(db.Float, default=0.0)  # Impact for right-handed batters
    
    # Weather-adjusted values (calculated at runtime, not stored)
    weather_adjusted_run_factor = None
    weather_adjusted_hr_factor = None
    weather_adjusted_hr_left = None
    weather_adjusted_hr_right = None

    
    def __repr__(self):
        return f'<ParkFactor {self.stadium_name} ({self.year}): Runs {self.runs_factor}, HR {self.hr_factor}>'
    
    @classmethod
    def get_by_stadium(cls, stadium_name):
        """
        Get park factors for a specific stadium
        
        Args:
            stadium_name: Name of the stadium
            
        Returns:
            ParkFactor object or None if not found
        """
        return cls.query.filter_by(stadium_name=stadium_name).order_by(cls.year.desc()).first()
    
    def get_factor_dict(self):
        """
        Get a dictionary of park factors for this stadium
        
        Returns:
            dict: Dictionary of park factors
        """
        return {
            'stadium_name': self.stadium_name,
            'year': self.year,
            'runs_factor': self.runs_factor,
            'hr_factor': self.hr_factor,
            'hits_factor': self.hits_factor,
            'doubles_factor': self.doubles_factor,
            'triples_factor': self.triples_factor,
            'hr_left_factor': self.hr_left_factor,
            'hr_center_factor': self.hr_center_factor,
            'hr_right_factor': self.hr_right_factor,
            'elevation': self.elevation,
            'temperature_effect': self.temperature_effect,
            'wind_effect': self.wind_effect,
            'humidity_effect': self.humidity_effect,
            'left_handed_advantage': self.left_handed_advantage,
            'right_handed_advantage': self.right_handed_advantage
        }
    
    def get_run_adjustment(self, temperature=None, wind_speed=None, wind_direction=None, humidity=None):
        """
        Calculate run scoring adjustment based on park factor and current weather conditions
        
        Args:
            temperature: Current temperature in Fahrenheit
            wind_speed: Current wind speed in mph
            wind_direction: Wind direction (e.g., 'in', 'out', 'left', 'right')
            humidity: Current humidity percentage
            
        Returns:
            float: Adjustment factor for run scoring (1.0 is neutral)
        """
        # Base adjustment from park run factor (convert from index to multiplier)
        adjustment = self.runs_factor / 100.0
        
        # Apply temperature adjustment if provided
        if temperature is not None and self.temperature_effect != 0:
            # Temperature effects are typically stronger in extremes
            if temperature > 90:  # Hot weather
                adjustment += (temperature - 90) * 0.001 * self.temperature_effect
            elif temperature < 50:  # Cold weather
                adjustment -= (50 - temperature) * 0.001 * self.temperature_effect
        
        # Apply wind adjustment if provided
        if wind_speed is not None and wind_direction is not None and self.wind_effect != 0:
            # Wind blowing out typically increases scoring, wind blowing in decreases
            if wind_direction.lower() in ['out', 'outfield']:
                adjustment += (wind_speed / 10.0) * 0.01 * self.wind_effect
            elif wind_direction.lower() in ['in', 'infield']:
                adjustment -= (wind_speed / 10.0) * 0.01 * self.wind_effect
        
        # Apply humidity adjustment if provided
        if humidity is not None and self.humidity_effect != 0:
            # Higher humidity typically decreases ball flight distance
            if humidity > 70:
                adjustment -= (humidity - 70) * 0.0005 * self.humidity_effect
            elif humidity < 30:
                adjustment += (30 - humidity) * 0.0005 * self.humidity_effect
        
        return adjustment
    
    def get_home_run_adjustment(self, batter_handedness=None, pull_tendency=None, 
                                temperature=None, wind_speed=None, wind_direction=None):
        """
        Calculate home run adjustment based on park factors, batter profile, and weather
        
        Args:
            batter_handedness: 'L' for left-handed, 'R' for right-handed
            pull_tendency: Value from 0-1 indicating how much batter pulls the ball
            temperature: Current temperature in Fahrenheit
            wind_speed: Current wind speed in mph
            wind_direction: Wind direction (e.g., 'in', 'out', 'left', 'right')
            
        Returns:
            float: Adjustment factor for home runs (1.0 is neutral)
        """
        # Base adjustment from park HR factor
        adjustment = self.hr_factor / 100.0
        
        # Apply directional and handedness adjustments if provided
        if batter_handedness and pull_tendency:
            # Left-handed batters pulling the ball will hit to right field
            if batter_handedness == 'L':
                # Apply right field HR factor and left-handed advantage
                right_field_adjustment = self.hr_right_factor / 100.0
                handedness_adjustment = self.left_handed_advantage / 100.0
                
                # Weight by pull tendency
                directional_adjustment = (right_field_adjustment * pull_tendency) + \
                                        (self.hr_center_factor / 100.0 * (1 - pull_tendency))
                
                adjustment = (adjustment + directional_adjustment + handedness_adjustment) / 3.0
                
            # Right-handed batters pulling the ball will hit to left field
            elif batter_handedness == 'R':
                # Apply left field HR factor and right-handed advantage
                left_field_adjustment = self.hr_left_factor / 100.0
                handedness_adjustment = self.right_handed_advantage / 100.0
                
                # Weight by pull tendency
                directional_adjustment = (left_field_adjustment * pull_tendency) + \
                                        (self.hr_center_factor / 100.0 * (1 - pull_tendency))
                
                adjustment = (adjustment + directional_adjustment + handedness_adjustment) / 3.0
        
        # Apply temperature adjustment if provided
        if temperature is not None:
            # Higher temperatures typically increase HR rate
            if temperature > 80:
                adjustment += (temperature - 80) * 0.002
            elif temperature < 50:
                adjustment -= (50 - temperature) * 0.002
        
        # Apply wind adjustment if provided
        if wind_speed is not None and wind_direction is not None:
            # Wind blowing out typically increases HRs, wind blowing in decreases
            if wind_direction.lower() in ['out', 'outfield']:
                adjustment += (wind_speed / 10.0) * 0.03
            elif wind_direction.lower() in ['in', 'infield']:
                adjustment -= (wind_speed / 10.0) * 0.03
            
            # Consider crosswinds for pull hitters
            if batter_handedness and pull_tendency and pull_tendency > 0.6:
                if (batter_handedness == 'L' and wind_direction.lower() == 'right') or \
                   (batter_handedness == 'R' and wind_direction.lower() == 'left'):
                    adjustment += (wind_speed / 10.0) * 0.02 * pull_tendency
        
        return adjustment
