import cv2
import pika
import pickle
import time
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config 

# Resolve absolute video path (IMPORTANT)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
VIDEO_PATH = os.path.join(BASE_DIR, "..", "data", "videos", "test.mp4")

print("Video path:", VIDEO_PATH)
print("Video exists:", os.path.exists(VIDEO_PATH))

# Open Video

cap = cv2.VideoCapture(VIDEO_PATH)
print("Video opened:", cap.isOpened())

if not cap.isOpened():
    print("ERROR: Cannot open video. Check path!")
    exit(1)

# Connect to RabbitMQ

print("Connecting to RabbitMQ...")
connection = pika.BlockingConnection(pika.ConnectionParameters(host=config.RABBITMQ_HOST))
channel = connection.channel()
channel.queue_declare(queue="frames_queue")
print("Connected to RabbitMQ, queue declared.")

# Read & Send Frames

frame_id = 0

while True:
    ret, frame = cap.read()

    if not ret:
        print("No more frames. Exiting loop.")
        break
    time.sleep(0.04)
    frame_id += 1
    timestamp = time.time()

    message = {
        "frame_id": frame_id,
        "timestamp": timestamp,
        "frame": frame
    }

    channel.basic_publish(
        exchange="",
        routing_key="frames_queue",
        body=pickle.dumps(message)
    )

    print(f"Sent frame {frame_id}")

    time.sleep(0.03)  # ~30 FPS

# Cleanup

cap.release()
connection.close()
print("Frame Reader stopped cleanly.")
