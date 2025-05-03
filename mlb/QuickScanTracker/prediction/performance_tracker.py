import logging
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from app import db
from models import Prediction, Game, PerformanceLog
from config import Config

logger = logging.getLogger(__name__)

class PerformanceTracker:
    """
    Tracks and analyzes prediction model performance over time
    Calculates metrics like ROI, accuracy, and Brier score
    """
    def __init__(self):
        self.config = Config()
        
    def track_prediction_results(self, days_back=7):
        """
        Track prediction results for games that have completed
        
        Args:
            days_back: Number of days to look back for completed games
            
        Returns:
            bool: Whether tracking was successful
        """
        try:
            logger.info(f"Tracking prediction results for the last {days_back} days")
            
            # Get date range
            end_date = datetime.now().date()
            start_date = end_date - timedelta(days=days_back)
            
            # Find completed games in date range
            completed_games = db.session.query(Game).filter(
                Game.game_datetime >= start_date,
                Game.game_datetime <= end_date,
                Game.status == 'final'
            ).all()
            
            if not completed_games:
                logger.info(f"No completed games found from {start_date} to {end_date}")
                return True
                
            logger.info(f"Found {len(completed_games)} completed games to analyze")
            
            # Track performance for each game
            successful_count = 0
            for game in completed_games:
                # Get the latest prediction for this game
                prediction = db.session.query(Prediction).filter_by(
                    game_id=game.id
                ).order_by(Prediction.timestamp.desc()).first()
                
                if prediction and prediction.actual_home_score is None:
                    # Update prediction with actual results
                    success = self._update_prediction_result(prediction, game)
                    if success:
                        successful_count += 1
            
            # Aggregate performance metrics
            if successful_count > 0:
                self._aggregate_performance_metrics(start_date, end_date)
                
            logger.info(f"Successfully tracked results for {successful_count} predictions")
            return True
            
        except Exception as e:
            logger.error(f"Error tracking prediction results: {e}")
            return False
    
    def _update_prediction_result(self, prediction, game):
        """
        Update a prediction with actual game results
        
        Args:
            prediction: Prediction object
            game: Game object with final score
            
        Returns:
            bool: Whether the update was successful
        """
        try:
            # Skip if game doesn't have final score
            if game.home_score is None or game.away_score is None:
                return False
                
            # Update prediction with actual scores
            prediction.actual_home_score = game.home_score
            prediction.actual_away_score = game.away_score
            
            # Determine if prediction was successful
            home_win_actual = game.home_score > game.away_score
            home_win_predicted = prediction.home_win_probability > 0.5
            prediction.prediction_successful = (home_win_actual == home_win_predicted)
            
            # Calculate Brier score (for probability calibration)
            # Brier score = (p - o)^2 where p is predicted probability and o is outcome (0 or 1)
            actual_outcome = 1 if home_win_actual else 0
            brier_score = (prediction.home_win_probability - actual_outcome) ** 2
            prediction.brier_score = brier_score
            
            # Calculate total runs accuracy
            predicted_total = prediction.predicted_home_runs + prediction.predicted_away_runs
            actual_total = game.home_score + game.away_score
            prediction.total_runs_error = abs(predicted_total - actual_total)
            
            # Calculate ROI for the recommended bet
            if prediction.recommended_bet:
                prediction.bet_roi = self._calculate_bet_roi(
                    prediction.recommended_bet,
                    prediction,
                    game
                )
            
            db.session.commit()
            return True
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error updating prediction result: {e}")
            return False
    
    def _calculate_bet_roi(self, bet_type, prediction, game):
        """
        Calculate ROI for a recommended bet
        
        Args:
            bet_type: Type of bet (e.g., 'Home Moneyline', 'Over')
            prediction: Prediction object
            game: Game object with final score
            
        Returns:
            float: ROI as a percentage (-100 to +infinity)
        """
        try:
            # Determine if bet won
            home_win_actual = game.home_score > game.away_score
            over_under_line = prediction.over_value if hasattr(prediction, 'over_value') else 8.5
            total_runs = game.home_score + game.away_score
            over_win = total_runs > over_under_line
            
            # Get associated odds
            bet_won = False
            bet_odds = None
            
            if bet_type == 'Home Moneyline':
                bet_won = home_win_actual
                bet_odds = getattr(prediction, 'home_moneyline_value', None)
                
            elif bet_type == 'Away Moneyline':
                bet_won = not home_win_actual
                bet_odds = getattr(prediction, 'away_moneyline_value', None)
                
            elif bet_type == 'Over':
                bet_won = over_win
                bet_odds = getattr(prediction, 'over_value', None)
                
            elif bet_type == 'Under':
                bet_won = not over_win
                bet_odds = getattr(prediction, 'under_value', None)
                
            # Calculate ROI
            if bet_won and bet_odds:
                # Convert American odds to ROI
                if bet_odds > 0:
                    roi = bet_odds  # Positive odds are already ROI percentage
                else:
                    roi = 100 / abs(bet_odds) * 100  # Convert negative odds to ROI
                return roi
            elif not bet_won:
                return -100.0  # Lost the entire bet
            
            return 0.0
            
        except Exception as e:
            logger.error(f"Error calculating bet ROI: {e}")
            return 0.0
    
    def _aggregate_performance_metrics(self, start_date, end_date):
        """
        Aggregate performance metrics and store in PerformanceLog
        
        Args:
            start_date: Start date for analysis
            end_date: End date for analysis
        """
        try:
            # Get all predictions with results in date range
            predictions = db.session.query(Prediction).join(
                Game, Prediction.game_id == Game.id
            ).filter(
                Game.game_datetime >= start_date,
                Game.game_datetime <= end_date,
                Game.status == 'final',
                Prediction.actual_home_score.isnot(None)
            ).all()
            
            if not predictions:
                logger.info(f"No completed predictions found to aggregate metrics")
                return
                
            # Aggregate metrics by bet type
            bet_types = ['Home Moneyline', 'Away Moneyline', 'Over', 'Under']
            
            for bet_type in bet_types:
                # Filter predictions for this bet type
                type_predictions = [p for p in predictions if p.recommended_bet == bet_type]
                
                if type_predictions:
                    total_bets = len(type_predictions)
                    winning_bets = sum(1 for p in type_predictions if p.prediction_successful)
                    
                    # Calculate average ROI
                    total_roi = sum(p.bet_roi for p in type_predictions if p.bet_roi is not None)
                    avg_roi = total_roi / total_bets if total_bets > 0 else 0.0
                    
                    # Calculate profit/loss in units
                    profit_loss = 0.0
                    for p in type_predictions:
                        if p.bet_roi is not None:
                            if p.bet_roi > 0:
                                profit_loss += p.bet_roi / 100.0  # Convert ROI to units
                            else:
                                profit_loss -= 1.0  # Lost bet is -1 unit
                    
                    # Store performance log
                    log_entry = PerformanceLog(
                        date=end_date,
                        bet_type=bet_type,
                        total_bets=total_bets,
                        winning_bets=winning_bets,
                        profit_loss=profit_loss,
                        roi=avg_roi
                    )
                    
                    db.session.add(log_entry)
            
            # Also add an 'all bets' entry
            if predictions:
                total_bets = len(predictions)
                winning_bets = sum(1 for p in predictions if p.prediction_successful)
                
                # Calculate average ROI
                total_roi = sum(p.bet_roi for p in predictions if p.bet_roi is not None)
                avg_roi = total_roi / total_bets if total_bets > 0 else 0.0
                
                # Calculate profit/loss in units
                profit_loss = 0.0
                for p in predictions:
                    if p.bet_roi is not None:
                        if p.bet_roi > 0:
                            profit_loss += p.bet_roi / 100.0  # Convert ROI to units
                        else:
                            profit_loss -= 1.0  # Lost bet is -1 unit
                
                # Store performance log
                log_entry = PerformanceLog(
                    date=end_date,
                    bet_type='all',
                    total_bets=total_bets,
                    winning_bets=winning_bets,
                    profit_loss=profit_loss,
                    roi=avg_roi
                )
                
                db.session.add(log_entry)
            
            db.session.commit()
            logger.info(f"Successfully aggregated performance metrics")
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error aggregating performance metrics: {e}")
    
    def calculate_overall_performance(self, days_back=30):
        """
        Calculate overall model performance for a time period
        
        Args:
            days_back: Number of days to analyze
            
        Returns:
            dict: Performance metrics
        """
        try:
            # Define date range
            end_date = datetime.now().date()
            start_date = end_date - timedelta(days=days_back)
            
            # Query performance logs in range
            logs = db.session.query(PerformanceLog).filter(
                PerformanceLog.date >= start_date,
                PerformanceLog.date <= end_date,
                PerformanceLog.bet_type == 'all'  # All bets aggregated
            ).order_by(PerformanceLog.date.asc()).all()
            
            if not logs:
                logger.info(f"No performance logs found for the last {days_back} days")
                return {}
                
            # Calculate overall metrics
            total_bets = sum(log.total_bets for log in logs)
            winning_bets = sum(log.winning_bets for log in logs)
            win_percentage = (winning_bets / total_bets * 100) if total_bets > 0 else 0.0
            profit_loss = sum(log.profit_loss for log in logs)
            
            # Calculate ROI
            roi = (profit_loss / total_bets * 100) if total_bets > 0 else 0.0
            
            # Calculate daily performance for chart
            dates = [log.date.strftime('%Y-%m-%d') for log in logs]
            daily_roi = [log.roi for log in logs]
            
            # Performance by bet type
            bet_type_logs = db.session.query(PerformanceLog).filter(
                PerformanceLog.date >= start_date,
                PerformanceLog.date <= end_date,
                PerformanceLog.bet_type != 'all'  # Specific bet types
            ).all()
            
            bet_type_performance = {}
            for log in bet_type_logs:
                if log.bet_type not in bet_type_performance:
                    bet_type_performance[log.bet_type] = {
                        'total_bets': 0,
                        'winning_bets': 0,
                        'profit_loss': 0.0
                    }
                
                # Add to cumulative stats
                bet_type_performance[log.bet_type]['total_bets'] += log.total_bets
                bet_type_performance[log.bet_type]['winning_bets'] += log.winning_bets
                bet_type_performance[log.bet_type]['profit_loss'] += log.profit_loss
            
            # Calculate win percentages and ROI for each bet type
            for bet_type, stats in bet_type_performance.items():
                if stats['total_bets'] > 0:
                    stats['win_percentage'] = stats['winning_bets'] / stats['total_bets'] * 100
                    stats['roi'] = stats['profit_loss'] / stats['total_bets'] * 100
                else:
                    stats['win_percentage'] = 0.0
                    stats['roi'] = 0.0
            
            # Assemble results
            performance = {
                'total_bets': total_bets,
                'winning_bets': winning_bets,
                'win_percentage': win_percentage,
                'profit_loss': profit_loss,
                'roi': roi,
                'dates': dates,
                'daily_roi': daily_roi,
                'bet_type_performance': bet_type_performance
            }
            
            return performance
            
        except Exception as e:
            logger.error(f"Error calculating overall performance: {e}")
            return {}
    
    def calculate_brier_score(self, days_back=30):
        """
        Calculate average Brier score for probability calibration assessment
        Brier score measures the accuracy of probability predictions
        Lower is better, with 0 being perfect and 0.25 being random guessing
        
        Args:
            days_back: Number of days to analyze
            
        Returns:
            float: Average Brier score
        """
        try:
            # Define date range
            end_date = datetime.now().date()
            start_date = end_date - timedelta(days=days_back)
            
            # Query predictions with Brier scores
            predictions = db.session.query(Prediction).join(
                Game, Prediction.game_id == Game.id
            ).filter(
                Game.game_datetime >= start_date,
                Game.game_datetime <= end_date,
                Game.status == 'final',
                Prediction.brier_score.isnot(None)
            ).all()
            
            if not predictions:
                logger.info(f"No predictions with Brier scores found for the last {days_back} days")
                return None
                
            # Calculate average Brier score
            brier_scores = [p.brier_score for p in predictions]
            avg_brier = sum(brier_scores) / len(brier_scores)
            
            return avg_brier
            
        except Exception as e:
            logger.error(f"Error calculating Brier score: {e}")
            return None