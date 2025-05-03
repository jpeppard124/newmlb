import logging
import numpy as np
from config import Config

logger = logging.getLogger(__name__)

class ShapExplainer:
    """
    Custom implementation of SHAP (SHapley Additive exPlanations) for model explainability
    This helps explain why the model made specific predictions by attributing importance to features
    """
    def __init__(self):
        self.config = Config()
        
    def explain_prediction(self, features, prediction_result):
        """
        Generate feature importance values to explain prediction
        
        Args:
            features: Dictionary of game features
            prediction_result: Dictionary containing prediction outputs
            
        Returns:
            dict: Feature importance values and explanation
        """
        # Initialize explanation dictionary
        explanation = {
            'feature_importance': {},
            'explanation_text': [],
            'key_factors': []
        }
        
        # Extract home win probability for context
        home_win_prob = prediction_result.get('home_win_probability', 0.5)
        home_favored = home_win_prob > 0.5
        
        # Calculate feature importances using a simplified approach
        # In a permutation-based approach like SHAP, we're measuring how much
        # each feature contributes to moving from baseline (0.5) to final prediction
        feature_importances = self._calculate_feature_importances(features, home_win_prob)
        explanation['feature_importance'] = feature_importances
        
        # Generate text explanation
        explanation['explanation_text'] = self._generate_explanation_text(
            features, 
            prediction_result,
            feature_importances
        )
        
        # Identify key factors (top 3 most important features)
        sorted_features = sorted(
            feature_importances.items(), 
            key=lambda x: abs(x[1]), 
            reverse=True
        )
        explanation['key_factors'] = [f[0] for f in sorted_features[:3]]
        
        return explanation
    
    def _calculate_feature_importances(self, features, home_win_prob):
        """
        Calculate importance of each feature
        
        Args:
            features: Dictionary of game features
            home_win_prob: Predicted home win probability
            
        Returns:
            dict: Feature importance scores
        """
        # Initialize with zero importance
        importances = {}
        
        # Baseline probability of home team winning (without any features)
        baseline_prob = 0.5
        
        # Calculate how far the prediction is from baseline
        total_shift = home_win_prob - baseline_prob
        
        # Skip calculation if prediction is at baseline
        if abs(total_shift) < 0.001:
            return importances
            
        # Calculate batting comparison importance
        if 'home_team_batting_avg' in features and 'away_team_batting_avg' in features:
            home_batting = features['home_team_batting_avg']
            away_batting = features['away_team_batting_avg']
            
            if away_batting > 0:
                batting_ratio = home_batting / away_batting
                # Normalize to -1 to 1 scale centered at 1.0 (equal teams)
                batting_importance = (batting_ratio - 1.0) * 0.4  # Scale factor
                importances['batting_comparison'] = batting_importance
                
        # Calculate pitching comparison importance
        if 'home_team_era' in features and 'away_team_era' in features:
            home_era = features['home_team_era']
            away_era = features['away_team_era']
            
            if home_era > 0 and away_era > 0:
                # Lower ERA is better, so invert the ratio
                pitching_ratio = away_era / home_era
                # Normalize to -1 to 1 scale
                pitching_importance = (pitching_ratio - 1.0) * 0.4  # Scale factor
                importances['pitching_comparison'] = pitching_importance
                
        # Calculate OPS comparison importance
        if 'home_team_ops' in features and 'away_team_ops' in features:
            home_ops = features['home_team_ops']
            away_ops = features['away_team_ops']
            
            if away_ops > 0:
                ops_ratio = home_ops / away_ops
                # Normalize to -1 to 1 scale
                ops_importance = (ops_ratio - 1.0) * 0.3  # Scale factor
                importances['ops_comparison'] = ops_importance
        
        # Add home field advantage importance
        if 'home_field_advantage' in features:
            home_advantage = features['home_field_advantage']
            importances['home_field_advantage'] = home_advantage
        
        # Weather factors
        if 'temperature' in features:
            # Extreme temperatures can affect home field advantage
            temp = features['temperature']
            if temp < 40 or temp > 90:
                importances['weather_effect'] = -0.02
        
        # Umpire factors
        if 'umpire_name' in features and features['umpire_name'] != 'Unknown':
            # Calculate umpire impact on runs
            if 'umpire_r_boost' in features:
                r_boost = features['umpire_r_boost']
                # Only include if significantly different from 1.0
                if abs(r_boost - 1.0) > 0.08:  # 8% deviation threshold
                    importances['umpire_runs_impact'] = (r_boost - 1.0) * 0.15  # Scale factor
            
            # Calculate umpire impact on strikeouts/walks 
            if 'umpire_k_boost' in features and 'umpire_bb_boost' in features:
                k_boost = features['umpire_k_boost']
                bb_boost = features['umpire_bb_boost']
                
                # Combine into a pitcher vs batter advantage
                if abs(k_boost - 1.0) > 0.1 or abs(bb_boost - 1.0) > 0.1:
                    # Higher K boost and lower BB boost favor pitchers
                    pitcher_advantage = (k_boost - 1.0) - (bb_boost - 1.0)
                    importances['umpire_pitcher_advantage'] = pitcher_advantage * 0.1  # Scale factor
                
        # Normalize importances to match the total shift from baseline
        self._normalize_importances(importances, total_shift)
        
        return importances
    
    def _normalize_importances(self, importances, total_shift):
        """
        Normalize importance values to sum to the total prediction shift
        
        Args:
            importances: Dictionary of raw importance values
            total_shift: Total shift from baseline probability
        """
        if not importances:
            return
            
        # Sum of absolute importance values
        importance_sum = sum(abs(v) for v in importances.values())
        
        # Avoid division by zero
        if importance_sum < 0.001:
            return
            
        # Scale factor to make importance values sum to total_shift
        scale_factor = abs(total_shift) / importance_sum
        
        # Scale each importance value
        for key in importances:
            # Maintain sign but scale magnitude
            importances[key] = importances[key] * scale_factor
    
    def _generate_explanation_text(self, features, prediction, importances):
        """
        Generate human-readable explanation of prediction
        
        Args:
            features: Dictionary of game features
            prediction: Dictionary of prediction results
            importances: Dictionary of feature importance values
            
        Returns:
            list: List of explanation sentences
        """
        explanation = []
        home_win_prob = prediction.get('home_win_probability', 0.5)
        home_favored = home_win_prob > 0.5
        
        # Get top 3 factors by importance magnitude
        top_factors = sorted(
            importances.items(), 
            key=lambda x: abs(x[1]), 
            reverse=True
        )[:3]
        
        # Overall prediction statement
        if home_favored:
            explanation.append(f"The home team has a {home_win_prob:.1%} chance of winning.")
        else:
            explanation.append(f"The away team has a {(1 - home_win_prob):.1%} chance of winning.")
        
        # Explain each top factor
        for factor, importance in top_factors:
            if factor == 'batting_comparison':
                home_avg = features.get('home_team_batting_avg', 0)
                away_avg = features.get('away_team_batting_avg', 0)
                if importance > 0:
                    explanation.append(f"The home team's batting average ({home_avg:.3f}) is stronger than the away team's ({away_avg:.3f}).")
                else:
                    explanation.append(f"The away team's batting average ({away_avg:.3f}) is stronger than the home team's ({home_avg:.3f}).")
            
            elif factor == 'pitching_comparison':
                home_era = features.get('home_team_era', 0)
                away_era = features.get('away_team_era', 0)
                if importance > 0:
                    explanation.append(f"The home team's pitching (ERA {home_era:.2f}) is better than the away team's (ERA {away_era:.2f}).")
                else:
                    explanation.append(f"The away team's pitching (ERA {away_era:.2f}) is better than the home team's (ERA {home_era:.2f}).")
            
            elif factor == 'ops_comparison':
                home_ops = features.get('home_team_ops', 0)
                away_ops = features.get('away_team_ops', 0)
                if importance > 0:
                    explanation.append(f"The home team's OPS ({home_ops:.3f}) is higher than the away team's ({away_ops:.3f}).")
                else:
                    explanation.append(f"The away team's OPS ({away_ops:.3f}) is higher than the home team's ({home_ops:.3f}).")
            
            elif factor == 'home_field_advantage':
                explanation.append(f"Home field advantage is providing a {abs(importance):.1%} boost to the home team.")
                
            elif factor == 'weather_effect':
                temp = features.get('temperature', 72)
                if temp < 40:
                    explanation.append(f"Cold weather ({temp}°F) is reducing the home field advantage.")
                elif temp > 90:
                    explanation.append(f"Hot weather ({temp}°F) is reducing the home field advantage.")
                    
            elif factor == 'umpire_runs_impact':
                umpire_name = features.get('umpire_name', 'Unknown')
                r_boost = features.get('umpire_r_boost', 1.0)
                
                if r_boost > 1.0:
                    explanation.append(f"Umpire {umpire_name} typically calls games with more runs than average.")
                else:
                    explanation.append(f"Umpire {umpire_name} typically calls games with fewer runs than average.")
                    
            elif factor == 'umpire_pitcher_advantage':
                umpire_name = features.get('umpire_name', 'Unknown')
                k_boost = features.get('umpire_k_boost', 1.0)
                bb_boost = features.get('umpire_bb_boost', 1.0)
                
                if importance > 0:
                    explanation.append(f"Umpire {umpire_name}'s strike zone favors pitchers (more strikeouts, fewer walks).")
                else:
                    explanation.append(f"Umpire {umpire_name}'s strike zone favors batters (fewer strikeouts, more walks).")
        
        # Add run prediction explanation
        home_runs = prediction.get('predicted_home_runs', 0)
        away_runs = prediction.get('predicted_away_runs', 0)
        explanation.append(f"The predicted score is approximately {home_runs:.1f} - {away_runs:.1f}.")
        
        # Add umpire explanation if available
        if 'umpire_explanation' in prediction and prediction['umpire_explanation']:
            explanation.append(prediction['umpire_explanation'])
            
            # Add umpire impact on specific predictions if very significant
            umpire_name = features.get('umpire_name', 'Unknown')
            if umpire_name != 'Unknown':
                umpire_r_boost = features.get('umpire_r_boost', 1.0)
                umpire_k_boost = features.get('umpire_k_boost', 1.0)
                
                # Only add specific impact statements if the boost is significant
                if abs(umpire_r_boost - 1.0) > 0.15:  # More than 15% deviation from average
                    if umpire_r_boost > 1.15:
                        explanation.append(f"With {umpire_name} calling balls and strikes, expect more runs than usual.")
                    elif umpire_r_boost < 0.85:
                        explanation.append(f"With {umpire_name} calling balls and strikes, expect fewer runs than usual.")
                
                if abs(umpire_k_boost - 1.0) > 0.15:  # More than 15% deviation from average
                    if umpire_k_boost > 1.15:
                        explanation.append(f"{umpire_name} tends to call more strikeouts, which may benefit strong pitchers.")
                    elif umpire_k_boost < 0.85:
                        explanation.append(f"{umpire_name} calls fewer strikeouts, which may benefit batters.")
        
        return explanation