import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import math
from config import DISTANCE_THRESHOLD, PROTEIN_ROI, PIZZA_ZONE_ROI

hand_status = {}

def is_inside_roi(box, roi):
    if roi is None: return False
    x1, y1, x2, y2 = box
    rx1, ry1, rx2, ry2 = roi
    cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
    return rx1 <= cx <= rx2 and ry1 <= cy <= ry2

def get_distance(box1, box2):
    c1 = ((box1[0] + box1[2]) / 2, (box1[1] + box1[3]) / 2)
    c2 = ((box2[0] + box2[2]) / 2, (box2[1] + box2[3]) / 2)
    return math.sqrt((c1[0] - c2[0])**2 + (c1[1] - c2[1])**2)

def check_violation_status(detections, dynamic_roi):
    """
    Revised logic to track specific hand IDs and return the violator ID
    """
    global hand_status
    hands_in_frame, pizzas = [], []
    scooper_in_protein_zone = False

    for det in detections:
        label, box = det["label"].lower(), det["box"]
        if label == "scooper" and is_inside_roi(box, PROTEIN_ROI):
            scooper_in_protein_zone = True

    for det in detections:
        label, box, track_id = det["label"].lower(), det["box"], det["id"]
        if label == "hand":
            if is_inside_roi(box, PROTEIN_ROI):
                hand_status[track_id] = not scooper_in_protein_zone # True if contaminated
            hands_in_frame.append(det)
        elif label == "pizza":
            pizzas.append(box)

    violation_triggered = False
    violating_id = None

    for hand in hands_in_frame:
        h_id = hand["id"]
        if hand_status.get(h_id, False):
            for p_box in pizzas:
                if get_distance(hand["box"], p_box) < DISTANCE_THRESHOLD:
                    violation_triggered = True
                    violating_id = h_id
                    hand_status[h_id] = False # Reset state
                    break
            if violation_triggered: break

    return violation_triggered, violating_id