from app import app, db
from models import ApiKey

# Create a Flask application context
with app.app_context():
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