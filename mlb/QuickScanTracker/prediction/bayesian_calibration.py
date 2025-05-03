import logging
from config import Config

logger = logging.getLogger(__name__)

class BayesianCalibrator:
    """
    Applies Bayesian calibration to raw prediction probabilities
    This helps ensure predicted probabilities match actual frequencies
    """
    def __init__(self):
        self.config = Config()
        self.prior_strength = self.config.BAYESIAN_PRIOR_STRENGTH
        
    def calibrate(self, raw_predictions, features):
        """
        Calibrate raw predictions using Bayesian updating
        
        Args:
            raw_predictions: Dictionary with raw model predictions
            features: Game features used for context
            
        Returns:
            dict: Calibrated predictions
        """
        # Initialize calibrated predictions with raw values
        calibrated = raw_predictions.copy()
        
        # Adjust home win probability with prior
        prior_home_win = self._adjust_home_win_prior(features)
        calibrated['home_win_probability'] = self._bayesian_update(
            raw_predictions['home_win_probability'],
            prior_home_win,
            0.7,  # Weight for model prediction
            0.3   # Weight for prior
        )
        
        # Adjust home runs prediction with prior
        prior_home_runs = self._adjust_runs_prior(features, 'home')
        calibrated['predicted_home_runs'] = self._bayesian_update(
            raw_predictions['predicted_home_runs'],
            prior_home_runs,
            0.8,  # Weight for model prediction
            0.2   # Weight for prior
        )
        
        # Adjust away runs prediction with prior
        prior_away_runs = self._adjust_runs_prior(features, 'away')
        calibrated['predicted_away_runs'] = self._bayesian_update(
            raw_predictions['predicted_away_runs'],
            prior_away_runs,
            0.8,  # Weight for model prediction
            0.2   # Weight for prior
        )
        
        # Adjust total runs prediction for consistency
        calibrated['predicted_total_runs'] = calibrated['predicted_home_runs'] + calibrated['predicted_away_runs']
        
        return calibrated
    
    def _bayesian_update(self, model_prediction, prior, model_weight, prior_weight):
        """
        Perform a Bayesian update/weighted average between the model prediction and prior
        
        Args:
            model_prediction: Prediction from the model
            prior: Prior belief
            model_weight: Weight given to the model
            prior_weight: Weight given to the prior
            
        Returns:
            float: Updated prediction
        """
        assert model_weight + prior_weight == 1.0, "Weights must sum to 1.0"
        
        # Weighted average of model prediction and prior
        updated = (model_prediction * model_weight) + (prior * prior_weight)
        
        return updated
    
    def _adjust_home_win_prior(self, features):
        """
        Adjust the home win prior based on contextual features
        
        Args:
            features: Game features dictionary
            
        Returns:
            float: Adjusted prior probability
        """
        # Base home win prior (historical MLB home team win percentage)
        base_prior = 0.54
        
        # Adjust for weather if available
        if 'temperature' in features and 'wind_speed' in features:
            # Extreme temperatures can reduce home field advantage
            temp = features['temperature']
            if temp < 40 or temp > 90:
                base_prior -= 0.02
            
            # High winds can reduce home field advantage (more random outcomes)
            wind = features['wind_speed']
            if wind > 15:
                base_prior -= 0.01
        
        return base_prior
    
    def _adjust_runs_prior(self, features, team_type):
        """
        Adjust the runs prior based on contextual features
        
        Args:
            features: Game features dictionary
            team_type: 'home' or 'away'
            
        Returns:
            float: Adjusted prior runs
        """
        # League average runs per team per game
        league_avg_runs = 4.5
        
        # Adjust for weather if available
        if 'temperature' in features:
            # Higher temperatures generally lead to more runs
            temp = features['temperature']
            temp_adjustment = 0.0
            
            if temp > 85:
                temp_adjustment = 0.3  # Hot weather, more runs
            elif temp < 45:
                temp_adjustment = -0.3  # Cold weather, fewer runs
            
            league_avg_runs += temp_adjustment
        
        # Home teams score slightly more runs on average
        if team_type == 'home':
            league_avg_runs += 0.2
        
        return league_avg_runs