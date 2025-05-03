import os
import logging
from datetime import datetime
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase
from werkzeug.middleware.proxy_fix import ProxyFix

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)

# Create the app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET")
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)  # needed for url_for to generate with https

# Configure the database
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL")
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_recycle": 300,
    "pool_pre_ping": True,
}
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# Initialize the app with the extension
db.init_app(app)

# Add custom Jinja filters
@app.template_filter('date')
def format_date(value):
    """Format a date to YYYY-MM-DD"""
    if isinstance(value, datetime):
        return value.strftime('%Y-%m-%d')
    return value

@app.template_filter('time')
def format_time(value):
    """Format a time to HH:MM"""
    if isinstance(value, datetime):
        return value.strftime('%H:%M')
    return value

@app.template_filter('abs')
def abs_filter(value):
    """Get the absolute value"""
    return abs(value)

@app.template_filter('min')
def min_filter(value, limit):
    """Return the minimum of two values"""
    return min(value, limit)

with app.app_context():
    # Import models
    import models  # noqa: F401
    
    # Import and register blueprints for routes
    from routes.main_routes import main_bp
    from routes.api_routes import api_bp
    from routes.admin_routes import admin_bp
    
    app.register_blueprint(main_bp)
    app.register_blueprint(api_bp, url_prefix='/api')
    app.register_blueprint(admin_bp)
    
    # Create all database tables
    db.create_all()
    
    # Import the scheduler but don't start it automatically
    from tasks.scheduler_manager import get_scheduler
    
    # Make the scheduler available as an app property but don't auto-start tasks
    app.scheduler = get_scheduler()
    # Don't start the scheduler automatically
    
    logger.info("MLB Betting Engine application initialized successfully")
