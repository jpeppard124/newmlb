"""
Data Service Interface - Template for implementing new data services with integrity checks

This module defines a base class and interface for all data services that want to 
automatically register with the data integrity system.

Usage:
    1. Create a new service that inherits from DataServiceInterface
    2. Override the ensure_data method to implement data integrity checks
    3. The data integrity system will automatically discover and run the ensure_data method
"""

import logging
from datetime import datetime
from app import db
from models import DataUpdateLog

logger = logging.getLogger(__name__)

class DataServiceInterface:
    """Base class for data services that ensure data integrity"""
    
    def __init__(self):
        """Initialize the data service"""
        pass
    
    def ensure_data(self, days_ahead=7):
        """
        Ensure data completeness and integrity for this service
        
        This method should be implemented by all data services that want to 
        participate in the automated data integrity system.
        
        Args:
            days_ahead: Number of days in the future to ensure data for (default: 7)
            
        Returns:
            bool: Whether the data check was successful
        """
        # This is just a placeholder to be overridden by subclasses
        logger.warning("ensure_data method called on base class - this should be overridden")
        return False
    
    def _log_update(self, task, success, details):
        """
        Log a data update to the database
        
        Args:
            task: Name of the task (e.g., 'update_player_stats')
            success: Whether the update was successful
            details: Details about the update
        """
        log_entry = DataUpdateLog(
            task=task,
            success=success,
            details=details
        )
        db.session.add(log_entry)
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error logging update for {task}: {e}")