import logging
from config import Config

logger = logging.getLogger(__name__)

class ConfidenceScorer:
    """
    Calculates confidence scores for predictions based on data quality and model certainty
    """
    def __init__(self):
        self.config = Config()
        
    def calculate_confidence(self, predictions, features):
        """
        Calculate confidence scores for the predictions
        
        Args:
            predictions: Dictionary of prediction values
            features: Dictionary of game features
            
        Returns:
            dict: Confidence scores for different prediction types
        """
        # Calculate base confidence on data quality
        base_confidence = self._calculate_base_confidence(features)
        
        # Calculate win probability confidence
        home_win_probability = predictions['home_win_probability']
        home_win_confidence = self._calculate_win_confidence(home_win_probability, base_confidence, features)
        
        # Calculate total runs confidence
        total_runs = predictions['predicted_total_runs']
        total_runs_confidence = self._calculate_total_runs_confidence(total_runs, base_confidence, features)
        
        return {
            'home_win_confidence': home_win_confidence,
            'total_runs_confidence': total_runs_confidence,
            'base_confidence': base_confidence
        }
    
    def is_prediction_confident(self, confidence_score):
        """
        Determine if a prediction meets the confidence threshold
        
        Args:
            confidence_score: Confidence score (0-1)
            
        Returns:
            bool: Whether the prediction is confident
        """
        return confidence_score >= self.config.MODEL_CONFIDENCE_THRESHOLD
    
    def _calculate_base_confidence(self, features):
        """
        Calculate a base confidence score based on data quality
        
        Args:
            features: Dictionary of game features
            
        Returns:
            float: Base confidence score (0-1)
        """
        confidence_factors = []
        
        # Check if we have player stats
        have_home_batting = features['home_team_batting_avg'] != 0.250  # Not default
        have_away_batting = features['away_team_batting_avg'] != 0.250  # Not default
        have_home_pitching = features['home_team_era'] != 4.00  # Not default
        have_away_pitching = features['away_team_era'] != 4.00  # Not default
        
        # Add factors based on data availability
        confidence_factors.append(0.7 if have_home_batting else 0.3)
        confidence_factors.append(0.7 if have_away_batting else 0.3)
        confidence_factors.append(0.7 if have_home_pitching else 0.3)
        confidence_factors.append(0.7 if have_away_pitching else 0.3)
        
        # Check if we have weather data
        has_weather = 'temperature' in features and features['temperature'] != 72.0  # Not default
        confidence_factors.append(0.6 if has_weather else 0.4)
        
        # Average the factors
        base_confidence = sum(confidence_factors) / len(confidence_factors)
        
        return base_confidence
    
    def _calculate_win_confidence(self, win_probability, base_confidence, features):
        """
        Calculate confidence score for win probability prediction
        
        Args:
            win_probability: Predicted win probability
            base_confidence: Base confidence score
            features: Dictionary of game features
            
        Returns:
            float: Win probability confidence score (0-1)
        """
        # Extreme probabilities (close to 0 or 1) are less reliable
        prob_factor = 1.0 - (4.0 * abs(win_probability - 0.5) ** 2)
        
        # Recent team data improves confidence
        data_recency_factor = 0.8  # Assume moderately recent for now
        
        # Combine factors (weighted average)
        confidence = (
            base_confidence * 0.5 +
            prob_factor * 0.3 +
            data_recency_factor * 0.2
        )
        
        # Cap to range 0-1
        return max(0.0, min(1.0, confidence))
    
    def _calculate_total_runs_confidence(self, total_runs, base_confidence, features):
        """
        Calculate confidence score for total runs prediction
        
        Args:
            total_runs: Predicted total runs
            base_confidence: Base confidence score
            features: Dictionary of game features
            
        Returns:
            float: Total runs confidence score (0-1)
        """
        # Extreme run totals are less reliable
        runs_factor = 1.0 - (abs(total_runs - 9.0) / 10.0)
        runs_factor = max(0.4, runs_factor)  # Floor at 0.4
        
        # Weather unpredictability reduces confidence
        weather_factor = 0.8  # Assume moderate predictability
        if 'precipitation_chance' in features and features['precipitation_chance'] > 0.3:
            weather_factor *= 0.8
        if 'wind_speed' in features and features['wind_speed'] > 15:
            weather_factor *= 0.9
        
        # Combine factors (weighted average)
        confidence = (
            base_confidence * 0.5 +
            runs_factor * 0.3 +
            weather_factor * 0.2
        )
        
        # Cap to range 0-1
        return max(0.0, min(1.0, confidence))