from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase
from datetime import datetime
import os

# Create a simple Flask app and database connection
class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)
app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL")
db.init_app(app)

# Define a simple ApiKey model
class ApiKey(db.Model):
    """API Keys stored in the database"""
    id = db.Column(db.Integer, primary_key=True)
    service = db.Column(db.String(50), unique=True, nullable=False)  # e.g., 'odds_api', 'weather_api'
    key = db.Column(db.String(200), nullable=False)
    active = db.Column(db.Boolean, default=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        key_preview = self.key[:4] + "****" if self.key else None
        return f'<ApiKey for {self.service}: {key_preview}>'

# Test the ApiKey model
with app.app_context():
    # Create the table if it doesn't exist
    db.create_all()
    
    try:
        # Test querying the ApiKey model
        existing_keys = db.session.query(ApiKey).all()
        print(f"Found {len(existing_keys)} existing API keys")

        # Test if we can add a new key
        test_key = ApiKey(
            service="test_service",
            key="test_key_123",
            active=True
        )
        db.session.add(test_key)
        db.session.commit()
        print("Successfully added a test key")

        # Clean up
        db.session.delete(test_key)
        db.session.commit()
        print("Successfully cleaned up test key")
        
    except Exception as e:
        print(f"Error testing ApiKey model: {e}")
        import traceback
        traceback.print_exc()