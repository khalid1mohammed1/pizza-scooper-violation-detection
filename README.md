# Eagle Vision: Pizza Scooper Violation Detection

### Real-Time Computer Vision System for Food Hygiene Enforcement

---

## Project Overview

I built Eagle Vision as a real-time computer vision system to enforce hygiene protocols in pizza preparation environments.
The system continuously monitors kitchen workers and detects cross-contamination violations, specifically when protein ingredients are handled without a scooper and the same contaminated hand subsequently touches pizza dough.

The core engineering challenge was not just detecting objects, but reasoning over time:

- Tracking multiple workers simultaneously
- Maintaining per-hand contamination states
- Preventing duplicate violation alerts for the same event

I solved this by combining YOLO12 object detection, ByteTrack multi-object tracking, and a stateful violation engine deployed within a scalable microservices architecture.

---

## Problem Statement & Objective

Manual hygiene monitoring in fast-paced kitchens is error-prone and inconsistent.
The objective of this system is to:

- Automatically detect hygiene violations in real time
- Attribute violations to specific hands/workers
- Reduce false positives through intelligent temporal logic
- Provide clear visual and logged evidence for auditing

The system is designed to operate reliably under high FPS video streams, occlusions, and crowded kitchen scenarios.

---

## System Architecture (High-Level Overview)

![System Architecture](./assets/architecture.png)

I designed the system using a decoupled microservices architecture to ensure scalability, fault isolation, and maintainability.

### Core Services

1. Frame Reader Service
2. RabbitMQ Message Broker
3. AI Detection & Violation Engine
4. Streaming Dashboard & Persistence Service

Each service runs independently and communicates asynchronously.

---

## Architecture Deep Dive (Most Important Section)

### 1. Frame Reader Service

- Captures frames from live cameras or video files
- Applies frame skipping to control system load under high FPS
- Publishes serialized frames to RabbitMQ
- Contains zero AI logic (pure producer)

This separation allows camera ingestion to scale independently from inference.

---

### 2. RabbitMQ - Message Broker

I chose RabbitMQ as the backbone of inter-service communication for the following reasons:

- Asynchronous processing: Decouples video ingestion from AI inference
- Scalability: Multiple detection workers can consume frames in parallel
- Backpressure handling: Prevents system overload during FPS spikes
- Reliability: Frames are buffered instead of dropped

RabbitMQ acts as a system stabilizer when processing load fluctuates.

---

### 3. AI Detection & Violation Engine (The Brain)

This service is the computational core of the system.

#### Object Detection

- Custom-trained YOLO12 (Ultralytics) model detects:
  - Hands
  - Scoopers
  - Protein ingredients
  - Pizza dough

#### Per-ID Tracking (Critical Design Choice)

- Integrated ByteTrack to assign persistent IDs to detected hands
- Enables temporal reasoning and per-worker logic
- Essential for reliable cooldown and contamination tracking

Without tracking, violations would be noisy and unreliable.

---

### 4. Streaming Dashboard & Persistence Service

- Flask-based web dashboard
- Displays live annotated video streams
- Logs violations to SQLite
- Provides historical records for auditing and analysis
- Supports heatmaps and movement analytics

![Dashboard Interface](./assets/dashboard.png)

---

## Core Logic - The "Secret Sauce"

### Per-Hand Contamination State

I implemented a state machine per tracked hand ID:

1. A predefined Protein ROI defines the sensitive ingredient zone
2. If a hand ID enters the Protein ROI:
   - AND no scooper is detected inside the same ROI
   - THEN that hand ID is marked as contaminated

This state persists across frames and is isolated per hand.

---

### Dynamic Pizza ROI

Instead of using a static dough zone:

- The system dynamically computes a pizza ROI based on detected pizza locations
- This allows robustness against camera shifts and layout changes

---

### Violation Trigger Logic

A violation is triggered only if:

- A hand ID is marked as contaminated
- AND the hand comes within a defined distance threshold of pizza dough

This prevents false positives caused by unrelated movements.

---

### Smart Cooldown Mechanism

To avoid duplicate alerts for the same action:

- I implemented a 15-second cooldown per hand ID
- Once a violation is logged:
  - The same hand ID cannot trigger another violation until cooldown expires

```python
if (current_time - last_recorded_time) > COOLDOWN_SECONDS:
    violation = True
    violation_tracker[hand_id] = current_time
```

This dramatically reduces alert spam while preserving correctness.

### Logic Flow (Conceptual)

- Capture frame  
- Publish frame to RabbitMQ  
- Run YOLO12 detection  
- Track hands using ByteTrack  
- Update contamination state per hand ID  
- Compute dynamic pizza ROI  
- Check contaminated hand proximity to pizza  
- Apply cooldown logic  
- Log violation and update dashboard  


### System Boundaries & Assumptions

Fixed overhead camera angle

Single pizza preparation surface per camera

One scooper shared per protein station

No identity recognition (privacy-preserving by design)

### Performance Notes

Processes ~15-20 FPS with frame skipping enabled

Sub-second end-to-end latency

Designed to scale horizontally by adding detection workers

### Tech Stack

- Computer Vision: YOLO12 (custom-trained), OpenCV
- Tracking: ByteTrack
- Messaging: RabbitMQ
- Backend: Flask
- Database: SQLite
- Deployment: Docker, Docker Compose
- Language: Python 3.10+


---

## Installation & Deployment

### Docker (Recommended)

```bash
docker-compose up --build
```

This starts:

RabbitMQ (with management UI)

Detection engine

Dashboard service

Frame reader service

### Local Development Setup

```bash
git clone <repository-url>
cd pizza-scooper-violation

python -m venv venv
source venv/bin/activate  # Linux / macOS
venv\Scripts\activate     # Windows

pip install -r requirements.txt
```

Start services manually:

```bash
# Start RabbitMQ
docker run -d -p 5672:5672 -p 15672:15672 rabbitmq:3-management

# Detection Service
python detection_service/main.py

# Dashboard
python streaming_service/app.py

# Frame Reader
python frame_reader_service/reader.py
```

Access the dashboard at:

http://localhost:5000

### Visual Samples

Bounding boxes, tracking IDs, ROIs, and violation overlays are rendered for debugging and validation.

### Key Features

Real-time video processing

Per-ID contamination tracking

Smart cooldown to reduce false positives

Dynamic ROIs for robustness

Scalable microservices architecture

Production-ready deployment with Docker

### Final Notes

This project was engineered with real-world constraints in mind:

Crowded environments

High FPS streams

Occlusions and fast hand movement

Maintainability and scalability

The architecture and logic can be extended to other hygiene, safety, or compliance monitoring use cases with minimal changes.
