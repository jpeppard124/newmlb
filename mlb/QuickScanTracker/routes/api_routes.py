import logging
from flask import Blueprint, request, jsonify
from app import db
from models import Game, Team, Prediction, PerformanceLog, Odds
from services.odds_service import OddsService
from services.weather_service import WeatherService
from services.statcast_service import StatcastService
from services.sportsdataio_service import SportsDataIOService
from prediction.engine import PredictionEngine
from prediction.performance_tracker import PerformanceTracker
from datetime import datetime, timedelta

# Set up logging
logger = logging.getLogger(__name__)

# Create Blueprint
api_bp = Blueprint('api', __name__)

# Initialize services
odds_service = OddsService()
weather_service = WeatherService()
statcast_service = StatcastService()
sports_data_service = SportsDataIOService()
prediction_engine = PredictionEngine()
performance_tracker = PerformanceTracker()

@api_bp.route('/games', methods=['GET'])
def get_games():
    """Get upcoming games"""
    try:
        # Get date range parameters
        days = int(request.args.get('days', 3))
        today = datetime.now().date()
        end_date = today + timedelta(days=days)
        
        # Query games
        games = db.session.query(Game).filter(
            Game.game_datetime >= datetime.combine(today, datetime.min.time()),
            Game.game_datetime < datetime.combine(end_date, datetime.min.time())
        ).order_by(Game.game_datetime).all()
        
        # Format response
        games_data = []
        for game in games:
            games_data.append({
                'id': game.id,
                'game_id': game.game_id,
                'game_datetime': game.game_datetime.isoformat(),
                'home_team': game.home_team.name,
                'away_team': game.away_team.name,
                'stadium': game.stadium,
                'status': game.status
            })
        
        return jsonify({
            'status': 'success',
            'count': len(games_data),
            'games': games_data
        })
    
    except Exception as e:
        logger.error(f"API error getting games: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@api_bp.route('/predictions', methods=['GET'])
def get_predictions():
    """Get predictions for games"""
    try:
        # Get game ID parameter (optional)
        game_id = request.args.get('game_id')
        
        # Query predictions
        if game_id:
            predictions = db.session.query(Prediction).filter_by(
                game_id=game_id
            ).order_by(Prediction.timestamp.desc()).all()
        else:
            # Default to last 24 hours of predictions
            cutoff = datetime.now() - timedelta(hours=24)
            predictions = db.session.query(Prediction).filter(
                Prediction.timestamp >= cutoff
            ).order_by(Prediction.timestamp.desc()).all()
        
        # Format response
        predictions_data = []
        for prediction in predictions:
            game = db.session.query(Game).filter_by(id=prediction.game_id).first()
            
            if not game:
                continue
                
            predictions_data.append({
                'id': prediction.id,
                'game_id': prediction.game_id,
                'timestamp': prediction.timestamp.isoformat(),
                'home_team': game.home_team.name,
                'away_team': game.away_team.name,
                'home_win_probability': prediction.home_win_probability,
                'predicted_home_runs': prediction.predicted_home_runs,
                'predicted_away_runs': prediction.predicted_away_runs,
                'predicted_total_runs': prediction.predicted_total_runs,
                'home_win_confidence': prediction.home_win_confidence,
                'total_runs_confidence': prediction.total_runs_confidence,
                'recommended_bet': prediction.recommended_bet
            })
        
        return jsonify({
            'status': 'success',
            'count': len(predictions_data),
            'predictions': predictions_data
        })
    
    except Exception as e:
        logger.error(f"API error getting predictions: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@api_bp.route('/generate_predictions', methods=['GET', 'POST'])
def generate_predictions():
    """Generate predictions for all upcoming games"""
    try:
        # For better performance and reliability, we'll generate predictions for a few games at a time
        days_ahead = int(request.args.get('days', 3))
        max_games = int(request.args.get('max_games', 10))  # Limit number of games in one batch
        
        # Get upcoming games that don't have recent predictions
        current_date = datetime.now()
        six_hours_ago = current_date - timedelta(hours=6)
        
        # Query games without recent predictions
        games_without_predictions = db.session.query(Game).filter(
            Game.game_datetime >= current_date,
            Game.game_datetime <= current_date + timedelta(days=days_ahead),
            Game.status == 'scheduled',
            ~Game.id.in_(
                db.session.query(Prediction.game_id).filter(
                    Prediction.timestamp >= six_hours_ago
                )
            )
        ).limit(max_games).all()
        
        count = 0
        if games_without_predictions:
            logger.info(f"Generating predictions for {len(games_without_predictions)} games")
            
            # Generate predictions one by one to avoid long-running transactions
            for game in games_without_predictions:
                try:
                    prediction = prediction_engine.generate_prediction(game.id)
                    if prediction:
                        count += 1
                except Exception as game_error:
                    logger.error(f"Error generating prediction for game {game.id}: {game_error}")
                    # Continue with other games even if one fails
                    continue
        
        message = f'Generated {count} new predictions'
        if count < len(games_without_predictions):
            message += f' (skipped {len(games_without_predictions) - count} due to errors)'
        
        # If it's a GET request, redirect to index page
        if request.method == 'GET':
            from flask import redirect, url_for, flash
            flash(message, "success" if count > 0 else "warning")
            return redirect(url_for('main.index'))
        
        # Otherwise return JSON response for API consumers
        return jsonify({
            'status': 'success',
            'message': message,
            'count': count,
            'total_games': len(games_without_predictions)
        })
    
    except Exception as e:
        logger.error(f"API error generating predictions: {e}")
        # If it's a GET request, redirect to index page with error
        if request.method == 'GET':
            from flask import redirect, url_for, flash
            flash(f"Error generating predictions: {e}", "danger")
            return redirect(url_for('main.index'))
            
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@api_bp.route('/generate_prediction/<int:game_id>', methods=['GET', 'POST'])
def generate_single_prediction(game_id):
    """Generate prediction for a specific game"""
    try:
        # Check if the game exists
        game = db.session.query(Game).filter_by(id=game_id).first()
        if not game:
            if request.method == 'GET':
                from flask import redirect, url_for, flash
                flash(f"Game with ID {game_id} not found", "danger")
                return redirect(url_for('main.index'))
            return jsonify({
                'status': 'error',
                'message': f'Game with ID {game_id} not found'
            }), 404
        
        # Generate prediction
        prediction = prediction_engine.generate_prediction(game_id)
        
        if prediction:
            # If it's a GET request, redirect to game details
            if request.method == 'GET':
                from flask import redirect, url_for, flash
                flash(f"Prediction successfully generated for {game.away_team.name} @ {game.home_team.name}", "success")
                return redirect(url_for('main.game_detail', game_id=game_id))
                
            # Otherwise return JSON for API consumers
            return jsonify({
                'status': 'success',
                'message': f'Generated prediction for game {game_id}',
                'prediction': {
                    'id': prediction.id,
                    'game_id': prediction.game_id,
                    'timestamp': prediction.timestamp.isoformat(),
                    'home_team': game.home_team.name,
                    'away_team': game.away_team.name,
                    'home_win_probability': prediction.home_win_probability,
                    'predicted_home_runs': prediction.predicted_home_runs,
                    'predicted_away_runs': prediction.predicted_away_runs,
                    'predicted_total_runs': prediction.predicted_total_runs,
                    'home_win_confidence': prediction.home_win_confidence,
                    'total_runs_confidence': prediction.total_runs_confidence,
                    'recommended_bet': prediction.recommended_bet,
                    'home_moneyline_value': prediction.home_moneyline_value,
                    'away_moneyline_value': prediction.away_moneyline_value,
                    'over_value': prediction.over_value,
                    'under_value': prediction.under_value
                }
            })
        else:
            if request.method == 'GET':
                from flask import redirect, url_for, flash
                flash(f"Failed to generate prediction for game {game_id}", "danger")
                return redirect(url_for('main.index'))
                
            return jsonify({
                'status': 'error',
                'message': f'Failed to generate prediction for game {game_id}'
            }), 500
    
    except Exception as e:
        logger.error(f"API error generating prediction for game {game_id}: {e}")
        
        if request.method == 'GET':
            from flask import redirect, url_for, flash
            flash(f"Error generating prediction: {e}", "danger")
            return redirect(url_for('main.index'))
            
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@api_bp.route('/update_odds', methods=['POST'])
def update_odds():
    """Update odds from all sources"""
    try:
        # Update odds
        odds_service.update_all_odds()
        
        return jsonify({
            'status': 'success',
            'message': 'Odds updated successfully'
        })
    
    except Exception as e:
        logger.error(f"API error updating odds: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@api_bp.route('/update_weather', methods=['POST'])
def update_weather():
    """Update weather forecasts for upcoming games"""
    try:
        # Update weather
        days_ahead = int(request.args.get('days', 3))
        weather_service.update_all_game_weather(days_ahead=days_ahead)
        
        return jsonify({
            'status': 'success',
            'message': 'Weather forecasts updated successfully'
        })
    
    except Exception as e:
        logger.error(f"API error updating weather: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@api_bp.route('/update_stats', methods=['POST'])
def update_stats():
    """Update player and team statistics"""
    try:
        # Update stats
        statcast_service.update_player_stats()
        
        return jsonify({
            'status': 'success',
            'message': 'Player statistics updated successfully'
        })
    
    except Exception as e:
        logger.error(f"API error updating stats: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@api_bp.route('/update_games', methods=['GET', 'POST'])
def update_games():
    """Update MLB games for the upcoming days"""
    try:
        # Log the execution - debugging
        logger.info("Update games endpoint called - method: %s", request.method)
        
        # Get parameters
        days_ahead = int(request.args.get('days', 7))
        
        # Update games
        games_updated = sports_data_service.update_games(days_ahead=days_ahead)
        logger.info(f"Games updated: {games_updated}")
        
        # If it's a GET request, redirect to index page
        if request.method == 'GET':
            from flask import redirect, url_for, flash
            flash(f"Updated {games_updated} games for the next {days_ahead} days", "success")
            return redirect(url_for('main.index'))
        
        # Otherwise return JSON response for API consumers
        return jsonify({
            'status': 'success',
            'message': f'Updated {games_updated} games for the next {days_ahead} days',
            'count': games_updated
        })
    
    except Exception as e:
        logger.error(f"API error updating games: {e}")
        
        # If it's a GET request, redirect to index page with error
        if request.method == 'GET':
            from flask import redirect, url_for, flash
            flash(f"Error updating games: {e}", "danger")
            return redirect(url_for('main.index'))
            
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@api_bp.route('/performance', methods=['GET'])
def get_performance():
    """Get model performance metrics"""
    try:
        # Get parameters
        days = int(request.args.get('days', 30))
        bet_type = request.args.get('bet_type', 'all_bets')
        
        # Get performance data
        performance_by_type = performance_tracker.get_performance_by_bet_type(days=days)
        
        # Format response
        performance_data = {
            'days': days,
            'performance_by_type': performance_by_type
        }
        
        return jsonify({
            'status': 'success',
            'performance': performance_data
        })
    
    except Exception as e:
        logger.error(f"API error getting performance: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@api_bp.route('/update_performance', methods=['POST'])
def update_performance():
    """Update performance metrics"""
    try:
        # Update performance for yesterday
        yesterday = (datetime.now() - timedelta(days=1)).date()
        performance = performance_tracker.update_daily_performance(date=yesterday)
        
        return jsonify({
            'status': 'success',
            'message': 'Performance metrics updated successfully',
            'performance': performance
        })
    
    except Exception as e:
        logger.error(f"API error updating performance: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@api_bp.route('/game_odds/<int:game_id>', methods=['GET'])
def get_game_odds(game_id):
    """Get all available odds for a specific game"""
    try:
        # Check if game exists
        game = db.session.query(Game).filter_by(id=game_id).first()
        if not game:
            return jsonify({
                'status': 'error',
                'message': f'Game with ID {game_id} not found'
            }), 404
            
        # Query all odds for this game
        odds_list = db.session.query(Odds).filter_by(game_id=game_id).all()
        
        if not odds_list:
            return jsonify({
                'status': 'error',
                'message': f'No odds found for game ID {game_id}'
            }), 404
            
        # Format response
        odds_data = []
        for odds in odds_list:
            odds_data.append({
                'id': odds.id,
                'source': odds.source,
                'sportsbook': odds.sportsbook,
                'timestamp': odds.timestamp.isoformat(),
                'home_moneyline': odds.home_moneyline,
                'away_moneyline': odds.away_moneyline,
                'home_spread': odds.home_spread,
                'home_spread_odds': odds.home_spread_odds,
                'away_spread_odds': odds.away_spread_odds,
                'total_over_under': odds.total_over_under,
                'over_odds': odds.over_odds,
                'under_odds': odds.under_odds
            })
            
        # Get team names for context
        game_info = {
            'id': game.id,
            'game_id': game.game_id,
            'home_team': game.home_team.name,
            'away_team': game.away_team.name,
            'game_datetime': game.game_datetime.isoformat(),
            'status': game.status
        }
        
        return jsonify({
            'status': 'success',
            'game': game_info,
            'count': len(odds_data),
            'odds': odds_data
        })
        
    except Exception as e:
        logger.error(f"API error getting odds for game {game_id}: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@api_bp.route('/record_game_result', methods=['POST'])
def record_game_result():
    """Record the actual result of a completed game"""
    try:
        # Get parameters
        data = request.get_json()
        game_id = data.get('game_id')
        home_score = data.get('home_score')
        away_score = data.get('away_score')
        
        if not game_id or home_score is None or away_score is None:
            return jsonify({
                'status': 'error',
                'message': 'Missing required parameters'
            }), 400
        
        # Record result
        success = prediction_engine.record_actual_results(
            game_id=game_id,
            home_score=home_score,
            away_score=away_score
        )
        
        if success:
            return jsonify({
                'status': 'success',
                'message': 'Game result recorded successfully'
            })
        else:
            return jsonify({
                'status': 'error',
                'message': 'Failed to record game result'
            }), 500
    
    except Exception as e:
        logger.error(f"API error recording game result: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500
