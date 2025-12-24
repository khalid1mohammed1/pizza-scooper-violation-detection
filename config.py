import os

# Base directory setup
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Model path for YOLO
MODEL_PATH = os.path.join(BASE_DIR, "detection_service", "model", "yolo12m-v2.pt")

# Directories and files
SAVE_DIR = "violations_images"
DB_NAME = "violations.db"

# RabbitMQ settings
RABBITMQ_HOST = os.getenv('RABBITMQ_HOST', 'localhost')
FRAMES_QUEUE = 'frames_queue'
STREAM_QUEUE = 'stream_queue'

# ROI definitions
PROTEIN_ROI = [330, 250, 460, 680]
PIZZA_ZONE_ROI = [470, 180, 1050, 750]

# Logic thresholds
VIOLATION_CONFIRM_FRAMES = 3
COOLDOWN_SECONDS = 7
DISTANCE_THRESHOLD = 150

# Performance settings
FRAME_SKIP = 2

# Ensure save directory exists
if not os.path.exists(SAVE_DIR):
    os.makedirs(SAVE_DIR)
