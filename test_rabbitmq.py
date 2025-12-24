import pika

# Setup RabbitMQ connection
connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
channel = connection.channel()

# Declare test queue
channel.queue_declare(queue='test_queue')

# Send test message
channel.basic_publish(exchange='', routing_key='test_queue', body='Hello, RabbitMQ!')

print("Sent 'Hello, RabbitMQ!'")

# Receive and acknowledge message
method_frame, header_frame, body = channel.basic_get(queue='test_queue')
if method_frame:
    print(f"Received {body.decode()}")
    channel.basic_ack(method_frame.delivery_tag)
else:
    print('No message received')

# Cleanup connection
connection.close()
