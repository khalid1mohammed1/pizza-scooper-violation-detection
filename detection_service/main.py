import pika, pickle, cv2, time
import numpy as np
from datetime import datetime
from ultralytics import YOLO
import sys
import os

# Set up system paths to access config and logic modules
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

import config 
from violation_logic import check_violation_status

# Initialize YOLO model and RabbitMQ connections
model = YOLO(config.MODEL_PATH)
connection = pika.BlockingConnection(pika.ConnectionParameters(host=config.RABBITMQ_HOST))
channel = connection.channel()
channel.queue_declare(queue=config.FRAMES_QUEUE)
channel.queue_declare(queue=config.STREAM_QUEUE)

# Global trackers for violation management
violation_tracker = {} # Tracking last violation time per object ID
frame_skip_counter = 0 

def is_in_carton_zone(box):
    """
    Check if the detected object is within the packaging zone to filter false alerts
    """
    x1, y1, x2, y2 = box
    if x1 < 250 and y1 < 450:
        return True
    return False

def callback(ch, method, properties, body):
    """
    Main processing logic: detects objects and enforces hygiene rules using per-ID cooldown
    """
    global frame_skip_counter

    frame_skip_counter += 1
    if frame_skip_counter % 1 != 0:
        ch.basic_ack(delivery_tag=method.delivery_tag)
        return

    data = pickle.loads(body)
    frame, frame_id = data["frame"], data["frame_id"]

    # Execute YOLO tracking with ByteTrack
    results = model.track(frame, persist=True, conf=0.25, tracker="bytetrack.yaml", verbose=False)
    
    detections, pizza_boxes = [], []

    if results[0].boxes.id is not None:
        for box, obj_id, cls in zip(results[0].boxes.xyxy, results[0].boxes.id, results[0].boxes.cls):
            label = model.names[int(cls)].lower()
            x1, y1, x2, y2 = map(int, box)
            track_id = int(obj_id)

            if label == "person" and is_in_carton_zone((x1, y1, x2, y2)):
                continue

            detections.append({"label": label, "box": (x1, y1, x2, y2), "id": track_id})

            # Draw labels and bounding boxes for visualization
            if label == "person": color = (255, 255, 255); display_name = f"WORKER #{track_id}"
            elif label == "scooper": color = (0, 255, 0); display_name = f"SCOOPER #{track_id}"
            elif label == "pizza":
                color = (255, 0, 0); display_name = f"PIZZA #{track_id}"
                pizza_boxes.append((x1, y1, x2, y2))
            elif label == "hand": color = (0, 255, 255); display_name = f"HAND #{track_id}"
            else: color = (200, 200, 200); display_name = f"{label.upper()} #{track_id}"

            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
            cv2.putText(frame, display_name, (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)

    # Define dynamic Region of Interest for pizza contact check
    dynamic_roi = None
    if pizza_boxes:
        rx1, ry1 = min(b[0] for b in pizza_boxes)-30, min(b[1] for b in pizza_boxes)-30
        rx2, ry2 = max(b[2] for b in pizza_boxes)+30, max(b[3] for b in pizza_boxes)+30
        dynamic_roi = (rx1, ry1, rx2, ry2)

    # Validate hygiene status
    is_violating_now, violating_id = check_violation_status(detections, dynamic_roi)

    final_v = False
    current_time = time.time()

    # Enforce Cooldown period per specific Hand/Worker ID
    if is_violating_now and violating_id is not None:
        last_recorded = violation_tracker.get(violating_id, 0)
        
        if (current_time - last_recorded) > config.COOLDOWN_SECONDS:
            final_v = True
            violation_tracker[violating_id] = current_time
            print(f"[{datetime.now().strftime('%H:%M:%S')}] REGISTERED VIOLATION FOR ID: {violating_id}")
        else:
            print(f"Duplicate detected for ID {violating_id} - cooling down...")

    # Display visual alert on the dashboard stream
    if final_v:
        cv2.rectangle(frame, (0, 0), (frame.shape[1], frame.shape[0]), (0, 0, 255), 15)
        cv2.putText(frame, "!!! HYGIENE VIOLATION !!!", (50, 50),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 0, 255), 3)

    # Encode and forward processed frame
    _, buffer = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
    
    stream_payload = {
        "frame": frame,
        "is_violating": final_v,
        "frame_id": frame_id,
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "detections": detections
    }
    
    channel.basic_publish(exchange='', routing_key=config.STREAM_QUEUE, body=pickle.dumps(stream_payload))
    ch.basic_ack(delivery_tag=method.delivery_tag)

print("EAGLE VISION ENGINE - INITIALIZED AND RUNNING...")
channel.basic_qos(prefetch_count=1)
channel.basic_consume(queue=config.FRAMES_QUEUE, on_message_callback=callback)
channel.start_consuming()