import logging
from flask import Blueprint, render_template, request, jsonify, redirect, url_for
from app import db
from models import Game, Team, Prediction, PerformanceLog
from services.odds_service import OddsService
from services.sportsdataio_service import SportsDataIOService
from services.weather_service import WeatherService
from prediction.engine import PredictionEngine
from prediction.performance_tracker import PerformanceTracker
from datetime import datetime, timedelta

# Set up logging
logger = logging.getLogger(__name__)

# Create Blueprint
main_bp = Blueprint('main', __name__)

# Initialize services
odds_service = OddsService()
sports_data_service = SportsDataIOService()
weather_service = WeatherService()
prediction_engine = PredictionEngine()
performance_tracker = PerformanceTracker()

@main_bp.route('/')
def index():
    """Home page with overview of upcoming games and predictions"""
    # Get today's date
    today = datetime.now().date()
    days_ahead = 7  # Show games for the next week
    
    try:
        # Get upcoming games for the next week
        upcoming_games = db.session.query(Game).filter(
            Game.game_datetime >= datetime.now(),
            Game.game_datetime < datetime.now() + timedelta(days=days_ahead),
            Game.status != 'final'
        ).order_by(Game.game_datetime).all()
        
        logger.info(f"Found {len(upcoming_games)} upcoming games")
        
        # Get the latest prediction for each game
        game_predictions = {}
        for game in upcoming_games:
            prediction = db.session.query(Prediction).filter(
                Prediction.game_id == game.id
            ).order_by(Prediction.timestamp.desc()).first()
            
            if prediction:
                game_predictions[game.id] = prediction
        
        # Get performance summary (last 7 days)
        performance_summary = db.session.query(PerformanceLog).filter(
            PerformanceLog.date >= (today - timedelta(days=7)),
            PerformanceLog.bet_type == 'all_bets'
        ).order_by(PerformanceLog.date.desc()).all()
        
        # Calculate overall ROI - with additional safety for empty data
        total_profit = sum([log.profit_loss for log in performance_summary]) if performance_summary else 0
        total_bets = sum([log.total_bets for log in performance_summary]) if performance_summary else 0
        overall_roi = (total_profit / total_bets * 100) if total_bets > 0 else 0
        
        return render_template(
            'index.html',
            upcoming_games=upcoming_games,
            game_predictions=game_predictions,
            performance_summary=performance_summary,
            overall_roi=overall_roi,
            today=today
        )
    
    except Exception as e:
        logger.error(f"Error loading index page: {e}")
        # Return a simplified template to avoid any potential template errors
        return render_template(
            'index.html', 
            error=str(e), 
            upcoming_games=[],
            game_predictions={},
            performance_summary=[],
            overall_roi=0,
            today=today
        )

@main_bp.route('/predictions')
def predictions():
    """Page showing detailed predictions"""
    days = int(request.args.get('days', 3))
    
    try:
        # Get current date
        today = datetime.now().date()
        end_date = today + timedelta(days=days)
        
        # Get upcoming games
        upcoming_games = db.session.query(Game).filter(
            Game.game_datetime >= datetime.combine(today, datetime.min.time()),
            Game.game_datetime < datetime.combine(end_date, datetime.min.time())
        ).order_by(Game.game_datetime).all()
        
        # Get the latest prediction for each game
        game_predictions = {}
        for game in upcoming_games:
            prediction = db.session.query(Prediction).filter(
                Prediction.game_id == game.id
            ).order_by(Prediction.timestamp.desc()).first()
            
            if prediction:
                game_predictions[game.id] = prediction
        
        return render_template(
            'predictions.html',
            upcoming_games=upcoming_games,
            game_predictions=game_predictions,
            days=days
        )
    
    except Exception as e:
        logger.error(f"Error loading predictions page: {e}")
        return render_template('predictions.html', error=str(e), upcoming_games=[])

@main_bp.route('/performance')
def performance():
    """Page showing model performance and ROI trends"""
    days = int(request.args.get('days', 30))
    
    try:
        # Get performance by bet type
        performance_by_type = performance_tracker.get_performance_by_bet_type(days=days)
        
        # Get performance trend data
        # We'll pass this to the template and use it with Chart.js
        performance_trends = {
            'dates': [],
            'daily_roi': [],
            'cumulative_roi': [],
            'daily_profit': [],
            'cumulative_profit': []
        }
        
        # Get performance logs
        today = datetime.now().date()
        start_date = today - timedelta(days=days)
        
        logs = db.session.query(PerformanceLog).filter(
            PerformanceLog.date >= start_date,
            PerformanceLog.date <= today,
            PerformanceLog.bet_type == 'all_bets'
        ).order_by(PerformanceLog.date).all()
        
        # Process logs for chart data
        cumulative_profit = 0
        total_bets = 0
        
        for log in logs:
            performance_trends['dates'].append(log.date.strftime('%Y-%m-%d'))
            performance_trends['daily_roi'].append(log.roi)
            performance_trends['daily_profit'].append(log.profit_loss)
            
            # Calculate cumulative metrics
            cumulative_profit += log.profit_loss
            total_bets += log.total_bets
            
            performance_trends['cumulative_profit'].append(cumulative_profit)
            
            # Calculate cumulative ROI
            if total_bets > 0:
                cumulative_roi = (cumulative_profit / total_bets) * 100
            else:
                cumulative_roi = 0
            
            performance_trends['cumulative_roi'].append(cumulative_roi)
        
        return render_template(
            'performance.html',
            performance_by_type=performance_by_type,
            performance_trends=performance_trends,
            days=days
        )
    
    except Exception as e:
        logger.error(f"Error loading performance page: {e}")
        return render_template('performance.html', error=str(e))

@main_bp.route('/game/<int:game_id>')
def game_detail(game_id):
    """Detailed view for a specific game"""
    try:
        # Get game data
        game = db.session.query(Game).filter_by(id=game_id).first()
        if not game:
            return render_template('index.html', error="Game not found")
        
        # Get latest prediction
        prediction = db.session.query(Prediction).filter_by(
            game_id=game_id
        ).order_by(Prediction.timestamp.desc()).first()
        
        # Get weather data - use stored data from database for consistency
        weather = weather_service.get_latest_weather(game_id)
        
        # If no weather in database or data is old, fetch fresh weather
        if not weather or (datetime.now() - weather.timestamp).total_seconds() > 1800:  # 30 minutes
            # Remove old weather data to ensure fresh data
            if weather:
                db.session.delete(weather)
                db.session.commit()
            # Fetch new weather data from API
            weather_service.fetch_weather_for_game(game_id)
            # Get the updated weather from database
            weather = weather_service.get_latest_weather(game_id)
        
        # Get odds data
        odds = odds_service.get_best_odds(game_id)
        
        # Get park factors data
        from services.park_factor_service import ParkFactorService
        park_service = ParkFactorService()
        
        # Try to get weather-adjusted park factors first, otherwise fallback to basic park factors
        park_factors = None
        if game.stadium:
            park_factors = park_service.calculate_weather_adjusted_factors(game_id)
            if not park_factors:
                park_factors = park_service.get_park_factor(game.stadium)
        
        # Get team stats
        home_team_stats = sports_data_service.get_team_batting_stats(game.home_team_id)
        away_team_stats = sports_data_service.get_team_batting_stats(game.away_team_id)
        
        # Get pitcher stats
        pitcher_stats = sports_data_service.get_starting_pitcher_stats(game_id)
        
        # Sanitize prediction data for template
        # This ensures we don't pass any problematic data that could cause template rendering issues
        safe_prediction = None
        if prediction:
            # Create a dictionary with all needed attributes, both from the model and for the template
            safe_prediction = {
                # Basic prediction fields
                'id': prediction.id,
                'game_id': prediction.game_id,
                'timestamp': prediction.timestamp,
                'home_win_probability': prediction.home_win_probability,
                'predicted_home_runs': prediction.predicted_home_runs,
                'predicted_away_runs': prediction.predicted_away_runs,
                'predicted_total_runs': prediction.predicted_total_runs,
                'home_win_confidence': prediction.home_win_confidence,
                'total_runs_confidence': prediction.total_runs_confidence,
                
                # Betting value fields
                'home_moneyline_value': prediction.home_moneyline_value,
                'away_moneyline_value': prediction.away_moneyline_value,
                'over_value': prediction.over_value,
                'under_value': prediction.under_value,
                'recommended_bet': prediction.recommended_bet,
                
                # Temporarily disable feature importance
                'feature_importance': None,
                
                # Optional fields
                'actual_home_score': prediction.actual_home_score,
                'actual_away_score': prediction.actual_away_score,
                'prediction_successful': prediction.prediction_successful
            }
        
        # Extract home and away pitcher data for the template
        home_pitcher = None
        away_pitcher = None
        if pitcher_stats:
            home_pitcher = pitcher_stats.get('home_pitcher')
            away_pitcher = pitcher_stats.get('away_pitcher')
            
        # Calculate implied probability if odds are available
        if odds:
            # Convert American odds to implied probability for the home team
            home_odds = odds.get('home_moneyline', -110)
            # Ensure home_odds is a numeric value
            try:
                # Convert to int if it's a string
                if isinstance(home_odds, str) and home_odds.strip():
                    home_odds = int(home_odds)
                # If it's a dict or other non-numeric type, use default
                if not isinstance(home_odds, (int, float)):
                    home_odds = -110
                    
                # Calculate implied probability
                if home_odds > 0:
                    home_implied_prob = 100 / (home_odds + 100)
                else:
                    home_implied_prob = abs(home_odds) / (abs(home_odds) + 100)
                
                # Add implied probability to odds object for template
                odds['home_implied_probability'] = home_implied_prob
            except (TypeError, ValueError) as e:
                # Handle conversion errors
                logger.error(f"Error processing odds: {e}")
                odds['home_implied_probability'] = 0.5  # Default to 50% if calculation fails
        
        return render_template(
            'game_detail.html',
            game=game,
            prediction=prediction if safe_prediction is None else safe_prediction,
            weather=weather,
            odds=odds,
            home_team_stats=home_team_stats,
            away_team_stats=away_team_stats,
            pitcher_stats=pitcher_stats,
            home_pitcher=home_pitcher,
            away_pitcher=away_pitcher,
            park_factors=park_factors
        )
    
    except Exception as e:
        logger.error(f"Error loading game detail: {e}")
        return render_template('index.html', error=str(e))

@main_bp.route('/about')
def about():
    """About page with information about the model and methodology"""
    return render_template('about.html')

@main_bp.route('/debug')
def debug_page():
    """Debug page to troubleshoot template rendering"""
    # Get today's date
    today = datetime.now().date()
    days_ahead = 7  # Show games for the next week
    
    try:
        # Get upcoming games for the next week
        upcoming_games = db.session.query(Game).filter(
            Game.game_datetime >= datetime.now(),
            Game.game_datetime < datetime.now() + timedelta(days=days_ahead),
            Game.status != 'final'
        ).order_by(Game.game_datetime).all()
        
        logger.info(f"Found {len(upcoming_games)} upcoming games for debug page")
        
        # Return the debug template
        return render_template(
            'debug.html',
            upcoming_games=upcoming_games,
            today=today
        )
    
    except Exception as e:
        logger.error(f"Error loading debug page: {e}")
        return render_template('debug.html', error=str(e), upcoming_games=[])

@main_bp.route('/simple')
def simple_index():
    """Simple index page with no complex elements to show games only"""
    # Get today's date
    today = datetime.now().date()
    days_ahead = 7  # Show games for the next week
    
    try:
        # Get upcoming games for the next week
        upcoming_games = db.session.query(Game).filter(
            Game.game_datetime >= datetime.now(),
            Game.game_datetime < datetime.now() + timedelta(days=days_ahead),
            Game.status != 'final'
        ).order_by(Game.game_datetime).all()
        
        logger.info(f"Found {len(upcoming_games)} upcoming games for simple index")
        
        # Return the simple index template
        return render_template(
            'simple_index.html',
            upcoming_games=upcoming_games,
            today=today
        )
    
    except Exception as e:
        logger.error(f"Error loading simple index: {e}")
        return render_template('simple_index.html', error=str(e), upcoming_games=[])

@main_bp.route('/game/<int:game_id>/generate-prediction')
def generate_prediction(game_id):
    """Generate a new prediction for a game"""
    try:
        # Use the globally instantiated prediction engine
        # Generate prediction
        logger.info(f"Generating prediction for game {game_id}")
        prediction = prediction_engine.generate_prediction(game_id)
        
        if prediction:
            logger.info(f"Successfully generated prediction for game {game_id}")
            return redirect(url_for('main.game_detail', game_id=game_id))
        else:
            logger.error(f"Failed to generate prediction for game {game_id}")
            return render_template('index.html', error="Failed to generate prediction. Please try again later.")
    
    except Exception as e:
        logger.error(f"Error generating prediction: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return render_template('index.html', error=f"Error generating prediction: {str(e)}")

@main_bp.route('/game/<int:game_id>/update-odds')
def update_odds(game_id):
    """Fetch and update odds for a specific game"""
    try:
        # Get game
        game = db.session.query(Game).filter_by(id=game_id).first()
        
        if not game:
            logger.error(f"Game not found: {game_id}")
            return render_template('index.html', error="Game not found")
        
        # Get game date in format YYYY-MM-DD
        game_date = game.game_datetime.strftime('%Y-%m-%d')
        
        # Fetch odds from API
        logger.info(f"Updating odds for game date {game_date}")
        success = odds_service.update_odds_for_date(game_date)
        
        if success:
            logger.info(f"Successfully updated odds for {game_date}")
            return redirect(url_for('main.game_detail', game_id=game_id))
        else:
            logger.error(f"Failed to update odds for {game_date}")
            return render_template('index.html', error="Failed to update odds. Please check your Odds API key.")
    
    except Exception as e:
        logger.error(f"Error updating odds: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return render_template('index.html', error=f"Error updating odds: {str(e)}")
