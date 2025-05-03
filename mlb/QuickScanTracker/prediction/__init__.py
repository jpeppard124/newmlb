from .engine import PredictionEngine
from .bayesian_calibration import BayesianCalibrator
from .confidence_scoring import ConfidenceScorer

# Create singleton instance
prediction_engine = PredictionEngine()