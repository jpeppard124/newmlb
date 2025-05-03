import logging
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from app import db
from models import ApiKey, DataUpdateLog, Game, Team
from init_apikeys import save_api_key

# Set up logging
logger = logging.getLogger(__name__)

# Create Blueprint
admin_bp = Blueprint('admin', __name__)

@admin_bp.route('/admin')
def admin_panel():
    """Admin panel index page"""
    try:
        # Get API keys
        api_keys = db.session.query(ApiKey).all()
        
        # Get update logs
        update_logs = db.session.query(DataUpdateLog).order_by(DataUpdateLog.timestamp.desc()).limit(20).all()
        
        # Get stats
        game_count = db.session.query(Game).count()
        team_count = db.session.query(Team).count()
        
        return render_template(
            'admin/index.html',
            api_keys=api_keys,
            update_logs=update_logs,
            stats={
                'game_count': game_count,
                'team_count': team_count
            }
        )
    
    except Exception as e:
        logger.error(f"Error loading admin panel: {e}")
        return render_template('admin/index.html', error=str(e))

@admin_bp.route('/admin/api_keys', methods=['GET', 'POST'])
def manage_api_keys():
    """Manage API keys"""
    if request.method == 'POST':
        try:
            service = request.form.get('service')
            key = request.form.get('key')
            
            if not service or not key:
                flash('Service and key are required', 'danger')
                return redirect(url_for('admin.manage_api_keys'))
            
            # Save API key
            save_api_key(service, key)
            
            flash(f'API key for {service} saved successfully', 'success')
            return redirect(url_for('admin.manage_api_keys'))
        
        except Exception as e:
            logger.error(f"Error saving API key: {e}")
            flash(f'Error saving API key: {str(e)}', 'danger')
            return redirect(url_for('admin.manage_api_keys'))
    
    # GET request
    try:
        # Get all API keys
        api_keys = db.session.query(ApiKey).all()
        
        return render_template(
            'admin/api_keys.html',
            api_keys=api_keys
        )
    
    except Exception as e:
        logger.error(f"Error loading API keys page: {e}")
        return render_template('admin/api_keys.html', error=str(e))

@admin_bp.route('/admin/api_keys/<int:key_id>/deactivate', methods=['POST'])
def deactivate_api_key(key_id):
    """Deactivate an API key"""
    try:
        api_key = db.session.query(ApiKey).filter_by(id=key_id).first()
        
        if not api_key:
            flash('API key not found', 'danger')
            return redirect(url_for('admin.manage_api_keys'))
        
        # Deactivate key
        api_key.active = False
        db.session.commit()
        
        flash(f'API key for {api_key.service} deactivated successfully', 'success')
        return redirect(url_for('admin.manage_api_keys'))
    
    except Exception as e:
        logger.error(f"Error deactivating API key: {e}")
        flash(f'Error deactivating API key: {str(e)}', 'danger')
        return redirect(url_for('admin.manage_api_keys'))

@admin_bp.route('/admin/api_keys/<int:key_id>/activate', methods=['POST'])
def activate_api_key(key_id):
    """Activate an API key"""
    try:
        api_key = db.session.query(ApiKey).filter_by(id=key_id).first()
        
        if not api_key:
            flash('API key not found', 'danger')
            return redirect(url_for('admin.manage_api_keys'))
        
        # Activate key
        api_key.active = True
        db.session.commit()
        
        flash(f'API key for {api_key.service} activated successfully', 'success')
        return redirect(url_for('admin.manage_api_keys'))
    
    except Exception as e:
        logger.error(f"Error activating API key: {e}")
        flash(f'Error activating API key: {str(e)}', 'danger')
        return redirect(url_for('admin.manage_api_keys'))

@admin_bp.route('/admin/update_scheduler', methods=['POST'])
def update_scheduler():
    """Update scheduler settings"""
    try:
        # Get form data
        odds_interval = int(request.form.get('odds_interval', 15))
        weather_interval = int(request.form.get('weather_interval', 1))
        stats_interval = int(request.form.get('stats_interval', 12))
        
        # Update scheduler
        # TODO: Implement scheduler configuration update
        
        flash('Scheduler settings updated successfully', 'success')
        return redirect(url_for('admin.admin_panel'))
    
    except Exception as e:
        logger.error(f"Error updating scheduler settings: {e}")
        flash(f'Error updating scheduler settings: {str(e)}', 'danger')
        return redirect(url_for('admin.admin_panel'))

@admin_bp.route('/admin/logs')
def view_logs():
    """View system logs"""
    try:
        # Get update logs
        logs = db.session.query(DataUpdateLog).order_by(DataUpdateLog.timestamp.desc()).limit(100).all()
        
        return render_template(
            'admin/logs.html',
            logs=logs
        )
    
    except Exception as e:
        logger.error(f"Error loading logs page: {e}")
        return render_template('admin/logs.html', error=str(e))

@admin_bp.route('/admin/tasks/update_games', methods=['POST'])
def admin_update_games():
    """Admin endpoint to update games"""
    try:
        # Import services
        from services.sportsdataio_service import SportsDataIOService
        
        # Initialize service
        service = SportsDataIOService()
        
        # Update games
        count = service.update_games()
        
        flash(f'Successfully updated {count} games', 'success')
        return redirect(url_for('admin.admin_panel'))
    
    except Exception as e:
        logger.error(f"Error updating games: {e}")
        flash(f'Error updating games: {str(e)}', 'danger')
        return redirect(url_for('admin.admin_panel'))

@admin_bp.route('/admin/tasks/update_odds', methods=['POST'])
def admin_update_odds():
    """Admin endpoint to update odds"""
    try:
        # Import services
        from services.odds_service import OddsService
        
        # Initialize service
        service = OddsService()
        
        # Update odds
        service.update_all_odds()
        
        flash('Successfully updated odds', 'success')
        return redirect(url_for('admin.admin_panel'))
    
    except Exception as e:
        logger.error(f"Error updating odds: {e}")
        flash(f'Error updating odds: {str(e)}', 'danger')
        return redirect(url_for('admin.admin_panel'))

@admin_bp.route('/admin/tasks/update_weather', methods=['POST'])
def admin_update_weather():
    """Admin endpoint to update weather"""
    try:
        # Import services
        from services.weather_service import WeatherService
        
        # Initialize service
        service = WeatherService()
        
        # Update weather
        service.update_all_game_weather()
        
        flash('Successfully updated weather forecasts', 'success')
        return redirect(url_for('admin.admin_panel'))
    
    except Exception as e:
        logger.error(f"Error updating weather: {e}")
        flash(f'Error updating weather: {str(e)}', 'danger')
        return redirect(url_for('admin.admin_panel'))

@admin_bp.route('/admin/tasks/update_stats', methods=['POST'])
def admin_update_stats():
    """Admin endpoint to update stats"""
    try:
        # Import services
        from services.sportsdataio_service import SportsDataIOService
        
        # Initialize service
        service = SportsDataIOService()
        
        # Update stats
        service.update_player_stats()
        
        flash('Successfully updated player statistics', 'success')
        return redirect(url_for('admin.admin_panel'))
    
    except Exception as e:
        logger.error(f"Error updating stats: {e}")
        flash(f'Error updating stats: {str(e)}', 'danger')
        return redirect(url_for('admin.admin_panel'))

@admin_bp.route('/admin/tasks/generate_predictions', methods=['POST'])
def admin_generate_predictions():
    """Admin endpoint to generate predictions"""
    try:
        # Import services
        from prediction.engine import PredictionEngine
        
        # Initialize engine
        engine = PredictionEngine()
        
        # Generate predictions
        count = engine.generate_all_predictions()
        
        flash(f'Successfully generated {count} predictions', 'success')
        return redirect(url_for('admin.admin_panel'))
    
    except Exception as e:
        logger.error(f"Error generating predictions: {e}")
        flash(f'Error generating predictions: {str(e)}', 'danger')
        return redirect(url_for('admin.admin_panel'))