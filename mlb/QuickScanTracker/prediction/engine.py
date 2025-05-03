import logging
import numpy as np
import pandas as pd
from datetime import datetime
from app import db
from models import Game, Team, PlayerStats, Prediction, Odds, WeatherCondition, UmpireStats
from services.umpire_service import UmpireService
from .bayesian_calibration import BayesianCalibrator
from .confidence_scoring import ConfidenceScorer
from .shap_analysis import ShapExplainer
from config import Config

logger = logging.getLogger(__name__)

class PredictionEngine:
    """
    Core prediction engine that generates game predictions using statistical models
    """
    def __init__(self):
        self.config = Config()
        self.bayesian_calibrator = BayesianCalibrator()
        self.confidence_scorer = ConfidenceScorer()
        self.shap_explainer = ShapExplainer()
        self.umpire_service = UmpireService()
        
    def generate_prediction(self, game_id):
        """
        Generate a prediction for a specific game
        
        Args:
            game_id: Database ID of the game
            
        Returns:
            Prediction: The generated prediction object
        """
        try:
            logger.info(f"Generating prediction for game {game_id}")
            
            # Fetch the game from the database
            game = db.session.query(Game).get(game_id)
            if not game:
                logger.error(f"Game with ID {game_id} not found")
                return None
            
            # Extract features for prediction
            features = self._extract_features(game)
            if not features:
                logger.error(f"Failed to extract features for game {game_id}")
                return None
            
            # Generate raw predictions
            raw_predictions = self._generate_raw_predictions(features)
            
            # Calibrate predictions using Bayesian methods
            calibrated_predictions = self.bayesian_calibrator.calibrate(raw_predictions, features)
            
            # Calculate confidence scores
            confidence_scores = self.confidence_scorer.calculate_confidence(calibrated_predictions, features)
            
            # Get odds data for value calculation
            odds_data = self._get_odds_data(game_id)
            
            # Calculate betting value
            betting_values = self._calculate_betting_value(calibrated_predictions, odds_data)
            
            # Determine the recommended bet
            recommended_bet = self._determine_recommended_bet(betting_values, confidence_scores)
            
            # Convert any NumPy values to native Python types to avoid database issues
            home_win_probability = float(calibrated_predictions['home_win_probability'])
            predicted_home_runs = float(calibrated_predictions['predicted_home_runs'])
            predicted_away_runs = float(calibrated_predictions['predicted_away_runs'])
            predicted_total_runs = float(calibrated_predictions['predicted_total_runs'])
            home_win_confidence = float(confidence_scores['home_win_confidence'])
            total_runs_confidence = float(confidence_scores['total_runs_confidence'])
            
            # Get betting values with safe float conversion
            home_moneyline_value = None
            if betting_values.get('home_moneyline_value') is not None:
                home_moneyline_value = float(betting_values.get('home_moneyline_value'))
                
            away_moneyline_value = None
            if betting_values.get('away_moneyline_value') is not None:
                away_moneyline_value = float(betting_values.get('away_moneyline_value'))
                
            over_value = None
            if betting_values.get('over_value') is not None:
                over_value = float(betting_values.get('over_value'))
                
            under_value = None
            if betting_values.get('under_value') is not None:
                under_value = float(betting_values.get('under_value'))
            
            # Create a prediction record
            # Generate SHAP values to explain the prediction
            explain_data = {
                'home_win_probability': home_win_probability,
                'predicted_home_runs': predicted_home_runs,
                'predicted_away_runs': predicted_away_runs
            }
            
            # Add umpire explanation if available
            umpire_explanation = raw_predictions.get('umpire_explanation')
            if umpire_explanation:
                logger.info(f"Adding umpire data to prediction explanation: {umpire_explanation}")
                explain_data['umpire_explanation'] = umpire_explanation
            
            explanation = self.shap_explainer.explain_prediction(features, explain_data)
            
            prediction = Prediction(
                game_id=game_id,
                home_win_probability=home_win_probability,
                predicted_home_runs=predicted_home_runs,
                predicted_away_runs=predicted_away_runs,
                predicted_total_runs=predicted_total_runs,
                home_win_confidence=home_win_confidence,
                total_runs_confidence=total_runs_confidence,
                home_moneyline_value=home_moneyline_value,
                away_moneyline_value=away_moneyline_value,
                over_value=over_value,
                under_value=under_value,
                recommended_bet=recommended_bet,
                feature_importance=explanation['feature_importance'],
                explanation_text=explanation['explanation_text']
            )
            
            db.session.add(prediction)
            db.session.commit()
            
            logger.info(f"Successfully generated prediction for game {game_id}")
            return prediction
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error generating prediction: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None
    
    def _extract_features(self, game):
        """
        Extract features for prediction model
        
        Args:
            game: Game object
            
        Returns:
            dict: Feature dictionary for prediction
        """
        try:
            features = {}
            
            # Game information
            features['game_id'] = game.id
            features['game_datetime'] = game.game_datetime
            features['home_team_id'] = game.home_team_id
            features['away_team_id'] = game.away_team_id
            features['stadium'] = game.stadium
            
            # Extract team stats
            home_team_stats = self._get_team_stats(game.home_team_id)
            away_team_stats = self._get_team_stats(game.away_team_id)
            
            features['home_team_batting_avg'] = home_team_stats.get('batting_avg', 0.250)
            features['home_team_era'] = home_team_stats.get('era', 4.00)
            features['home_team_ops'] = home_team_stats.get('ops', 0.700)
            features['home_team_whip'] = home_team_stats.get('whip', 1.30)
            
            features['away_team_batting_avg'] = away_team_stats.get('batting_avg', 0.250)
            features['away_team_era'] = away_team_stats.get('era', 4.00)
            features['away_team_ops'] = away_team_stats.get('ops', 0.700)
            features['away_team_whip'] = away_team_stats.get('whip', 1.30)
            
            # Add home field advantage
            features['home_field_advantage'] = 0.06  # Historical MLB home field advantage
            
            # Add weather data if available
            weather = self._get_weather_data(game.id)
            if weather:
                features['temperature'] = weather.temperature
                features['wind_speed'] = weather.wind_speed
                features['wind_direction'] = weather.wind_direction
                features['humidity'] = weather.humidity
                features['precipitation_chance'] = weather.precipitation_chance
                features['weather_description'] = weather.weather_description
            else:
                # Default weather values
                features['temperature'] = 72.0  # Neutral temperature
                features['wind_speed'] = 5.0  # Light wind
                features['wind_direction'] = "Variable"
                features['humidity'] = 50.0  # Moderate humidity
                features['precipitation_chance'] = 0.0  # No rain
                features['weather_description'] = "Clear"
            
            # Add park factors if available
            park_factors = self._get_park_factors(game)
            if park_factors:
                # Include basic park factors
                features['park_runs_factor'] = park_factors.get('runs_factor', 100.0) / 100.0
                features['park_hr_factor'] = park_factors.get('hr_factor', 100.0) / 100.0
                
                # Include weather-adjusted park factors if available
                if 'weather_adjusted_run_factor' in park_factors:
                    features['park_adjusted_runs_factor'] = park_factors.get('weather_adjusted_run_factor', 100.0) / 100.0
                
                if 'weather_adjusted_hr_factor_left' in park_factors and 'weather_adjusted_hr_factor_right' in park_factors:
                    features['park_adjusted_hr_factor_left'] = park_factors.get('weather_adjusted_hr_factor_left', 100.0) / 100.0
                    features['park_adjusted_hr_factor_right'] = park_factors.get('weather_adjusted_hr_factor_right', 100.0) / 100.0
                
                # Directional HR factors
                features['park_hr_left_factor'] = park_factors.get('hr_left_factor', 100.0) / 100.0
                features['park_hr_center_factor'] = park_factors.get('hr_center_factor', 100.0) / 100.0
                features['park_hr_right_factor'] = park_factors.get('hr_right_factor', 100.0) / 100.0
                
                # Handedness advantages
                features['park_left_handed_advantage'] = park_factors.get('left_handed_advantage', 0.0) / 100.0
                features['park_right_handed_advantage'] = park_factors.get('right_handed_advantage', 0.0) / 100.0
            else:
                # Default neutral park factors
                features['park_runs_factor'] = 1.0
                features['park_hr_factor'] = 1.0
                features['park_hr_left_factor'] = 1.0
                features['park_hr_center_factor'] = 1.0
                features['park_hr_right_factor'] = 1.0
                features['park_left_handed_advantage'] = 0.0
                features['park_right_handed_advantage'] = 0.0
                
            # Add umpire factors if available
            umpire_factors = self._get_umpire_factors(game.id)
            if umpire_factors:
                features['umpire_k_boost'] = umpire_factors.get('k_boost', 1.0)
                features['umpire_bb_boost'] = umpire_factors.get('bb_boost', 1.0)
                features['umpire_r_boost'] = umpire_factors.get('r_boost', 1.0)
                features['umpire_ba_boost'] = umpire_factors.get('ba_boost', 1.0)
                features['umpire_obp_boost'] = umpire_factors.get('obp_boost', 1.0)
                features['umpire_slg_boost'] = umpire_factors.get('slg_boost', 1.0)
                features['umpire_games_called'] = umpire_factors.get('games_called', 0)
                features['umpire_name'] = umpire_factors.get('name', 'Unknown')
            else:
                # Default neutral umpire factors
                features['umpire_k_boost'] = 1.0
                features['umpire_bb_boost'] = 1.0
                features['umpire_r_boost'] = 1.0
                features['umpire_ba_boost'] = 1.0
                features['umpire_obp_boost'] = 1.0
                features['umpire_slg_boost'] = 1.0
                features['umpire_games_called'] = 0
                features['umpire_name'] = 'Unknown'
            
            return features
            
        except Exception as e:
            logger.error(f"Error extracting features: {e}")
            return None
    
    def _get_team_stats(self, team_id):
        """
        Get aggregated team statistics
        
        Args:
            team_id: Database ID of the team
            
        Returns:
            dict: Aggregated team stats
        """
        try:
            # Get player stats for the team
            player_stats = db.session.query(PlayerStats).filter_by(team_id=team_id).all()
            
            if not player_stats:
                logger.warning(f"No player stats found for team {team_id}")
                return {}
            
            # Initialize stats
            team_stats = {
                'batting_avg': 0.0,
                'ops': 0.0,
                'era': 0.0,
                'whip': 0.0
            }
            
            # Variables for averaging
            total_batters = 0
            total_pitchers = 0
            
            # Calculate batting stats
            for player in player_stats:
                if player.position not in ['P', 'RP', 'SP', 'CL']:
                    # Batter
                    if player.avg is not None:
                        team_stats['batting_avg'] += player.avg
                        total_batters += 1
                    
                    if player.ops is not None:
                        team_stats['ops'] += player.ops
                        
                else:
                    # Pitcher
                    if player.era is not None:
                        team_stats['era'] += player.era
                        total_pitchers += 1
                    
                    if player.whip is not None:
                        team_stats['whip'] += player.whip
            
            # Calculate averages
            if total_batters > 0:
                team_stats['batting_avg'] /= total_batters
                team_stats['ops'] /= total_batters
            
            if total_pitchers > 0:
                team_stats['era'] /= total_pitchers
                team_stats['whip'] /= total_pitchers
            
            return team_stats
            
        except Exception as e:
            logger.error(f"Error getting team stats: {e}")
            return {}
    
    def _get_weather_data(self, game_id):
        """
        Get latest weather data for a game
        
        Args:
            game_id: Database ID of the game
            
        Returns:
            WeatherCondition: Weather data for the game
        """
        return db.session.query(WeatherCondition).filter_by(game_id=game_id).order_by(
            WeatherCondition.timestamp.desc()).first()
    
    def _get_odds_data(self, game_id):
        """
        Get latest odds data for a game
        
        Args:
            game_id: Database ID of the game
            
        Returns:
            dict: Dictionary of best odds for different bet types
        """
        from services.odds_service import OddsService
        odds_service = OddsService()
        return odds_service.get_best_odds(game_id)
        
    def _get_park_factors(self, game):
        """
        Get park factors for a game's stadium, adjusted for weather if available
        
        Args:
            game: Game object
            
        Returns:
            dict: Park factors for the stadium
        """
        try:
            if not game.stadium:
                logger.warning(f"No stadium set for game {game.id}")
                return None
                
            # Get park factors from service
            from services.park_factor_service import ParkFactorService
            park_service = ParkFactorService()
            
            # Try to get weather-adjusted factors first
            adjusted_factors = park_service.calculate_weather_adjusted_factors(game.id)
            if adjusted_factors:
                return adjusted_factors
                
            # Fall back to basic park factors
            return park_service.get_park_factor(game.stadium)
            
        except Exception as e:
            logger.error(f"Error getting park factors: {e}")
            return None
            
    def _get_umpire_factors(self, game_id):
        """
        Get umpire adjustment factors for a specific game
        
        Args:
            game_id: Database ID of the game
            
        Returns:
            dict: Dictionary of umpire adjustment factors
        """
        try:
            # Get umpire factors from the UmpireService
            umpire_factors = self.umpire_service.get_umpire_factors(game_id)
            
            if umpire_factors:
                logger.info(f"Using umpire factors for game {game_id}: {umpire_factors}")
                return umpire_factors
            
            # If we're in testing mode and no umpire is assigned, try to assign one
            if self.config.TESTING:
                logger.info(f"In testing mode - checking for umpire assignment for game {game_id}")
                # Call ensure_data to potentially assign an umpire in testing mode
                updated = self.umpire_service.ensure_data(days_ahead=1)
                
                if updated:
                    # Try again after assignment
                    umpire_factors = self.umpire_service.get_umpire_factors(game_id)
                    if umpire_factors:
                        logger.info(f"Successfully assigned umpire for game {game_id} in testing mode")
                        return umpire_factors
                    else:
                        logger.warning(f"Failed to assign umpire for game {game_id} even after ensure_data")
                else:
                    logger.warning(f"No umpire update occurred for game {game_id}")
            
            # If no umpire data is available, return None
            logger.warning(f"No umpire data available for game {game_id}")
            return None
                
        except Exception as e:
            logger.error(f"Error getting umpire factors: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None
    
    def _generate_raw_predictions(self, features):
        """
        Generate raw predictions based on features
        
        Args:
            features: Dictionary of game features
            
        Returns:
            dict: Raw prediction values
        """
        # In a real implementation, this would use an ML model
        # For now, we'll use a simplified statistical approach
        
        # Extract key features
        home_batting = features['home_team_batting_avg']
        away_batting = features['away_team_batting_avg']
        home_pitching = features['home_team_era']
        away_pitching = features['away_team_era']
        home_ops = features['home_team_ops']
        away_ops = features['away_team_ops']
        home_advantage = features['home_field_advantage']
        
        # Extract umpire factors if available
        umpire_k_boost = features.get('umpire_k_boost', 1.0)
        umpire_bb_boost = features.get('umpire_bb_boost', 1.0)
        umpire_r_boost = features.get('umpire_r_boost', 1.0)
        umpire_ba_boost = features.get('umpire_ba_boost', 1.0)
        umpire_obp_boost = features.get('umpire_obp_boost', 1.0)
        umpire_slg_boost = features.get('umpire_slg_boost', 1.0)
        
        # Log umpire influence
        umpire_name = features.get('umpire_name', 'Unknown')
        if umpire_name != 'Unknown':
            logger.info(f"Using umpire factors for {umpire_name}: R-Boost: {umpire_r_boost}, BA-Boost: {umpire_ba_boost}")
        
        # Simple win probability model - with safety checks for division by zero
        home_win_factors = [1.0]  # Start with neutral factor
        
        # Add batting comparison if valid, adjusted by umpire batting average boost
        if away_batting > 0:
            # Apply umpire's batting average boost - this affects both teams but we use it as a relative factor
            adjusted_home_batting = home_batting * umpire_ba_boost
            adjusted_away_batting = away_batting * umpire_ba_boost
            home_win_factors.append(adjusted_home_batting / adjusted_away_batting)
        
        # Add pitching comparison if valid - higher ERA means worse pitching
        # Adjust by umpire K and BB boost factors since they affect pitching performance
        if home_pitching > 0 and away_pitching > 0:
            # Pitchers who get more strikeouts (boosted by umpire) will have lower ERAs
            # Pitchers who give up more walks (boosted by umpire) will have higher ERAs
            # These adjustments are simplified and would be more sophisticated in a real model
            home_pitching_adjusted = home_pitching * (1 / umpire_k_boost) * umpire_bb_boost 
            away_pitching_adjusted = away_pitching * (1 / umpire_k_boost) * umpire_bb_boost
            home_win_factors.append(away_pitching_adjusted / home_pitching_adjusted)
        
        # Add OPS comparison if valid, adjusted by umpire OBP and SLG boosts
        if away_ops > 0:
            # Apply umpire's OBP and SLG boosts to the OPS calculation
            adjusted_home_ops = home_ops * ((umpire_obp_boost + umpire_slg_boost) / 2)
            adjusted_away_ops = away_ops * ((umpire_obp_boost + umpire_slg_boost) / 2)
            home_win_factors.append(adjusted_home_ops / adjusted_away_ops)
        
        # Always add home field advantage
        home_win_factors.append(1 + home_advantage)
        
        # Multiply factors and normalize to probability
        home_win_raw = np.prod(home_win_factors)
        home_win_probability = home_win_raw / (home_win_raw + 1)
        
        # More balanced runs model based on team stats and league averages
        league_avg_runs = 4.5  # MLB average runs per team per game
        
        # Apply umpire's run scoring boost to league average
        league_avg_runs_adjusted = league_avg_runs * umpire_r_boost
        
        # Add variance to create more realistic scores - in real model this would be based on statistical distributions
        # Allow a wider initial range based on team quality
        team_quality_factor_home = 1.0
        team_quality_factor_away = 1.0
        
        # Calculate team quality factors using OPS and ERA, which are strong indicators of run production
        if home_ops > 0 and away_ops > 0:
            # Teams with higher OPS score more runs
            league_avg_ops = 0.720  # MLB average OPS
            team_quality_factor_home *= (home_ops / league_avg_ops)
            team_quality_factor_away *= (away_ops / league_avg_ops)
            
        if home_pitching > 0 and away_pitching > 0:
            # Teams with lower ERA allow fewer runs to opponents
            league_avg_era = 4.20  # MLB average ERA
            team_quality_factor_home *= (league_avg_era / home_pitching)  # Inverted as lower ERA is better
            team_quality_factor_away *= (league_avg_era / away_pitching)
            
        # Apply quality factors to create a range of initial run values
        home_runs_raw = league_avg_runs_adjusted * team_quality_factor_home
        away_runs_raw = league_avg_runs_adjusted * team_quality_factor_away
        
        # Allow more extreme adjustments to create variety in scores
        # Batting adjustment - now max 30% up or down, affected by umpire BA boost
        if away_batting > 0 and home_batting > 0:
            # Apply umpire's BA boost
            adjusted_home_batting = home_batting * umpire_ba_boost
            adjusted_away_batting = away_batting * umpire_ba_boost
            batting_ratio = min(max(adjusted_home_batting / adjusted_away_batting, 0.7), 1.3)
            home_runs_raw *= batting_ratio
        
        # OPS has more predictive power for runs, affected by umpire OBP and SLG boosts
        if away_ops > 0 and home_ops > 0:
            # Apply umpire's OBP and SLG boosts to OPS
            adjusted_home_ops = home_ops * ((umpire_obp_boost + umpire_slg_boost) / 2)
            adjusted_away_ops = away_ops * ((umpire_obp_boost + umpire_slg_boost) / 2)
            ops_ratio = min(max(adjusted_home_ops / adjusted_away_ops, 0.7), 1.3)
            home_runs_raw *= ops_ratio
        
        # Pitching adjustment - now max 35% up or down, affected by umpire K and BB boosts
        if away_pitching > 0 and home_pitching > 0:
            # Adjust ERA based on umpire K and BB tendencies
            home_pitching_adjusted = home_pitching * (1 / umpire_k_boost) * umpire_bb_boost
            away_pitching_adjusted = away_pitching * (1 / umpire_k_boost) * umpire_bb_boost
            # Lower ERA means better pitching, so invert the ratio
            pitching_ratio = min(max(away_pitching_adjusted / home_pitching_adjusted, 0.65), 1.35)
            away_runs_raw *= (1 / pitching_ratio)  # Adjust away runs inversely
        
        # Home field advantage - typically worth ~0.4 runs
        home_runs_raw += 0.4  # Add instead of multiply to avoid compounding effects
        
        # Add additional logging for umpire adjustments
        if umpire_name != 'Unknown':
            logger.info(f"Umpire {umpire_name} adjusting runs: Before adj: Home {home_runs_raw/umpire_r_boost:.2f}, Away {away_runs_raw/umpire_r_boost:.2f}, " +
                       f"After: Home {home_runs_raw:.2f}, Away {away_runs_raw:.2f}")
        
        # Ensure runs stay in realistic MLB range - now with wider range (1-10 runs per team)
        # This will allow for more variety in final scores
        home_runs_raw = min(max(home_runs_raw, 1.0), 10.0)
        away_runs_raw = min(max(away_runs_raw, 1.0), 10.0)
        
        # Round to 1 decimal place
        predicted_home_runs = round(home_runs_raw, 1)
        predicted_away_runs = round(away_runs_raw, 1)
        predicted_total_runs = round(predicted_home_runs + predicted_away_runs, 1)
        
        # Add umpire data to the explanation
        umpire_explanation = ""
        if umpire_name != 'Unknown':
            # Basic explanation about runs and strikeouts
            umpire_explanation = f"Umpire {umpire_name} tends to call {'more' if umpire_r_boost > 1.0 else 'fewer'} runs " + \
                               f"({umpire_r_boost:.2f}x average) and {'increases' if umpire_k_boost > 1.0 else 'decreases'} " + \
                               f"strikeout rate ({umpire_k_boost:.2f}x average)."
            
            # Add detail on batting average impact if significant
            if abs(umpire_ba_boost - 1.0) > 0.05:
                umpire_explanation += f" Games with this umpire see {'higher' if umpire_ba_boost > 1.0 else 'lower'} " + \
                                     f"batting averages ({umpire_ba_boost:.2f}x league norm)."
                                     
            # Add detail on walks if significant
            if abs(umpire_bb_boost - 1.0) > 0.08:
                umpire_explanation += f" {umpire_name} calls {'more' if umpire_bb_boost > 1.0 else 'fewer'} walks " + \
                                     f"than typical umpires ({umpire_bb_boost:.2f}x average)."
                                     
            # Add information about games called
            if 'umpire_games_called' in features and features['umpire_games_called'] > 50:
                umpire_explanation += f" This analysis is based on {features['umpire_games_called']} games called by {umpire_name}."
        
        return {
            'home_win_probability': home_win_probability,
            'predicted_home_runs': predicted_home_runs,
            'predicted_away_runs': predicted_away_runs,
            'predicted_total_runs': predicted_total_runs,
            'umpire_explanation': umpire_explanation if umpire_name != 'Unknown' else None
        }
    
    def _calculate_betting_value(self, predictions, odds_data):
        """
        Calculate the betting value for different bet types
        
        Args:
            predictions: Dictionary of calibrated predictions
            odds_data: Dictionary of betting odds
            
        Returns:
            dict: Value percentages for different bet types
        """
        if not odds_data:
            logger.warning("No odds data available for value calculation")
            return {}
        
        values = {}
        
        # Calculate moneyline values
        if 'home_moneyline' in odds_data and 'away_moneyline' in odds_data:
            home_ml = odds_data['home_moneyline']['value']
            away_ml = odds_data['away_moneyline']['value']
            
            # Calculate implied probabilities from odds
            from services.odds_service import OddsService
            odds_service = OddsService()
            home_implied_prob = odds_service.calculate_implied_probability(home_ml)
            away_implied_prob = odds_service.calculate_implied_probability(away_ml)
            
            # Calculate edge percentages
            home_win_prob = predictions['home_win_probability']
            away_win_prob = 1 - home_win_prob
            
            home_value = (home_win_prob - home_implied_prob) * 100
            away_value = (away_win_prob - away_implied_prob) * 100
            
            values['home_moneyline_value'] = round(home_value, 2)
            values['away_moneyline_value'] = round(away_value, 2)
        
        # Calculate totals values
        if 'total_over_under' in odds_data:
            total_line = odds_data['total_over_under']['value']
            over_odds = odds_data['total_over_under']['over_odds']
            under_odds = odds_data['total_over_under']['under_odds']
            
            # Calculate implied probabilities from odds
            from services.odds_service import OddsService
            odds_service = OddsService()
            over_implied_prob = odds_service.calculate_implied_probability(over_odds)
            under_implied_prob = odds_service.calculate_implied_probability(under_odds)
            
            # Calculate probabilities of over/under based on our prediction
            # A simple normal distribution assumption with standard deviation of 2.5 runs
            predicted_total = predictions['predicted_total_runs']
            std_dev = 2.5
            
            # Instead of using scipy, we'll implement a simpler approximation
            # of the normal CDF function for portability
            def normal_cdf(x, mean, std_dev):
                """Approximation of normal CDF using error function"""
                import math
                z = (x - mean) / (std_dev * math.sqrt(2))
                return 0.5 * (1 + math.erf(z))
            
            # Calculate over/under probabilities
            over_prob = 1 - normal_cdf(total_line, predicted_total, std_dev)
            under_prob = normal_cdf(total_line, predicted_total, std_dev)
            
            # Calculate edge percentages
            over_value = (over_prob - over_implied_prob) * 100
            under_value = (under_prob - under_implied_prob) * 100
            
            values['over_value'] = round(over_value, 2)
            values['under_value'] = round(under_value, 2)
        
        return values
    
    def _determine_recommended_bet(self, betting_values, confidence_scores):
        """
        Determine the recommended bet based on value and confidence
        
        Args:
            betting_values: Dictionary of betting values
            confidence_scores: Dictionary of confidence scores
            
        Returns:
            str: Recommended bet description
        """
        # Extract values
        home_ml_value = betting_values.get('home_moneyline_value', -100)
        away_ml_value = betting_values.get('away_moneyline_value', -100)
        over_value = betting_values.get('over_value', -100)
        under_value = betting_values.get('under_value', -100)
        
        # Extract confidence scores
        home_win_confidence = confidence_scores.get('home_win_confidence', 0)
        total_runs_confidence = confidence_scores.get('total_runs_confidence', 0)
        
        # Set minimum edge percentage for a bet recommendation
        min_edge = self.config.MIN_EDGE_PERCENTAGE
        
        # Track the best bet
        best_bet = None
        best_value = min_edge
        
        # Check moneyline bets if confidence is sufficient
        if home_win_confidence >= self.config.MODEL_CONFIDENCE_THRESHOLD:
            if home_ml_value > best_value:
                best_bet = "Home Moneyline"
                best_value = home_ml_value
            
            if away_ml_value > best_value:
                best_bet = "Away Moneyline"
                best_value = away_ml_value
        
        # Check totals bets if confidence is sufficient
        if total_runs_confidence >= self.config.MODEL_CONFIDENCE_THRESHOLD:
            if over_value > best_value:
                best_bet = "Over"
                best_value = over_value
            
            if under_value > best_value:
                best_bet = "Under"
                best_value = under_value
        
        # If no bet has sufficient edge, don't recommend any
        if best_value <= min_edge:
            return "No Bet - Edge too small"
        
        # If confidence is low, add a warning
        confidence_threshold = self.config.MODEL_CONFIDENCE_THRESHOLD
        if (best_bet in ["Home Moneyline", "Away Moneyline"] and home_win_confidence < confidence_threshold) or \
           (best_bet in ["Over", "Under"] and total_runs_confidence < confidence_threshold):
            return f"{best_bet} (Low Confidence)"
        
        return best_bet