import logging
import numpy as np
from scipy.stats import multivariate_normal

logger = logging.getLogger(__name__)

class CorrelationModeler:
    """
    Models correlations between different betting markets and outcomes
    Useful for parlay optimization and understanding related outcomes
    """
    def __init__(self):
        # Initialize correlation matrix between different markets
        # Format: [home_win, away_win, over, under, home_spread, away_spread]
        self.correlation_matrix = np.array([
            [1.0, -1.0, 0.3, -0.3, 0.7, -0.7],   # home_win
            [-1.0, 1.0, -0.3, 0.3, -0.7, 0.7],   # away_win
            [0.3, -0.3, 1.0, -1.0, 0.1, -0.1],   # over
            [-0.3, 0.3, -1.0, 1.0, -0.1, 0.1],   # under
            [0.7, -0.7, 0.1, -0.1, 1.0, -1.0],   # home_spread
            [-0.7, 0.7, -0.1, 0.1, -1.0, 1.0]    # away_spread
        ])
        
        # Market types in order corresponding to correlation matrix
        self.market_types = ['home_win', 'away_win', 'over', 'under', 'home_spread', 'away_spread']
    
    def calculate_correlated_probability(self, outcome_probabilities, selected_outcomes):
        """
        Calculate the joint probability of selected outcomes considering correlations
        
        Args:
            outcome_probabilities: Dict of individual outcome probabilities
            selected_outcomes: List of selected outcomes for a parlay
            
        Returns:
            float: Joint probability considering correlations
        """
        # Extract probabilities and indexes for selected outcomes
        probs = []
        indexes = []
        
        for outcome in selected_outcomes:
            if outcome in outcome_probabilities and outcome in self.market_types:
                probs.append(outcome_probabilities[outcome])
                indexes.append(self.market_types.index(outcome))
        
        if not probs:
            return 0.0
        
        # If only one selection, return its probability
        if len(probs) == 1:
            return probs[0]
        
        # Extract relevant correlation submatrix
        sub_correlation = self.correlation_matrix[np.ix_(indexes, indexes)]
        
        # Convert probabilities to z-scores
        z_scores = np.array([self._prob_to_z(p) for p in probs])
        
        try:
            # Calculate multivariate normal CDF
            mvn = multivariate_normal(mean=np.zeros(len(indexes)), cov=sub_correlation)
            joint_prob = mvn.cdf(z_scores)
            return joint_prob
        except:
            # Fallback to simple product if numerical issues
            logger.warning("Numerical issues in MVN calculation, falling back to product")
            return np.prod(probs)
    
    def get_optimal_parlay(self, game_predictions, max_selections=3):
        """
        Find the optimal parlay combination based on edge and correlations
        
        Args:
            game_predictions: List of game prediction objects
            max_selections: Maximum number of selections in the parlay
            
        Returns:
            tuple: (selected_outcomes, expected_value, joint_probability)
        """
        # Extract all possible selections with positive expected value
        all_selections = []
        
        for prediction in game_predictions:
            game_id = prediction.game_id
            
            # Check moneyline value
            if prediction.home_moneyline_value > 0:
                all_selections.append({
                    'game_id': game_id,
                    'market': 'home_win',
                    'ev': prediction.home_moneyline_value,
                    'probability': prediction.home_win_probability
                })
            if prediction.away_moneyline_value > 0:
                all_selections.append({
                    'game_id': game_id,
                    'market': 'away_win',
                    'ev': prediction.away_moneyline_value,
                    'probability': 1 - prediction.home_win_probability
                })
            
            # Check total runs value
            if prediction.over_value > 0:
                # Estimate over probability (simplified)
                over_prob = 0.5 + (prediction.over_value / 200)
                all_selections.append({
                    'game_id': game_id,
                    'market': 'over',
                    'ev': prediction.over_value,
                    'probability': over_prob
                })
            if prediction.under_value > 0:
                # Estimate under probability (simplified)
                under_prob = 0.5 + (prediction.under_value / 200)
                all_selections.append({
                    'game_id': game_id,
                    'market': 'under',
                    'ev': prediction.under_value,
                    'probability': under_prob
                })
        
        # Sort by expected value
        all_selections.sort(key=lambda x: x['ev'], reverse=True)
        
        # If no selections have positive EV, return empty
        if not all_selections:
            return [], 0, 0
        
        # Find the best combination (simplified approach)
        best_ev = 0
        best_selections = []
        best_joint_prob = 0
        
        # Start with the highest EV selection
        if all_selections:
            best_selections = [all_selections[0]]
            best_joint_prob = all_selections[0]['probability']
            best_ev = all_selections[0]['ev']
        
        # Try adding more selections if available
        for i in range(1, min(len(all_selections), max_selections)):
            # Add the next highest EV selection
            current_selections = all_selections[:i+1]
            
            # Check that we don't have multiple markets from the same game
            game_ids = [s['game_id'] for s in current_selections]
            if len(game_ids) != len(set(game_ids)):
                continue  # Skip if we have duplicate games
            
            # Calculate joint probability considering correlations
            probs = {s['market']: s['probability'] for s in current_selections}
            markets = [s['market'] for s in current_selections]
            joint_prob = self.calculate_correlated_probability(probs, markets)
            
            # Calculate expected value of the parlay
            individual_odds = [(1 / s['probability']) - 1 for s in current_selections]
            parlay_odds = np.prod([1 + odd for odd in individual_odds]) - 1
            parlay_ev = (joint_prob * parlay_odds) - (1 - joint_prob)
            
            # Update best parlay if this is better
            if parlay_ev > best_ev:
                best_ev = parlay_ev
                best_selections = current_selections
                best_joint_prob = joint_prob
        
        return best_selections, best_ev, best_joint_prob
    
    def _prob_to_z(self, prob):
        """Convert a probability to a z-score"""
        from scipy.stats import norm
        return norm.ppf(prob)
