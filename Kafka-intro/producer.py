#!/usr/bin/env python3
import json
import random
import time
from datetime import datetime
from confluent_kafka import Producer

# Kafka producer configuration
conf = {
    'bootstrap.servers': 'localhost:9092',
    'client.id': 'web-event-producer'
}

# Create Producer instance
producer = Producer(conf)

# Sample user IDs and pages for simulation
user_ids = [f"user_{i}" for i in range(1, 101)]
pages = [
    '/home', '/products', '/category/electronics', '/category/clothing',
    '/product/1', '/product/2', '/product/3', '/cart', '/checkout', '/thank-you'
]

# Event types
event_types = ['page_view', 'click', 'add_to_cart', 'remove_from_cart', 'purchase']

def delivery_report(err, msg):
    """Callback invoked on delivery success or failure"""
    if err is not None:
        print(f'Message delivery failed: {err}')
    else:
        print(f'Message delivered to {msg.topic()} [{msg.partition()}] at offset {msg.offset()}')

def generate_event():
    """Generate a random web event"""
    user_id = random.choice(user_ids)
    timestamp = datetime.now().isoformat()
    event_type = random.choice(event_types)
    page = random.choice(pages)
    
    # Add event-specific properties
    properties = {
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'ip_address': f'192.168.1.{random.randint(1, 255)}',
        'session_id': f'session_{random.randint(1000, 9999)}'
    }
    
    if event_type == 'click':
        properties['element_id'] = f'button_{random.randint(1, 20)}'
    elif event_type in ['add_to_cart', 'remove_from_cart']:
        properties['product_id'] = f'product_{random.randint(1, 100)}'
        properties['quantity'] = random.randint(1, 5)
    elif event_type == 'purchase':
        properties['order_id'] = f'order_{random.randint(10000, 99999)}'
        properties['total_amount'] = round(random.uniform(10.0, 500.0), 2)
    
    return {
        'user_id': user_id,
        'timestamp': timestamp,
        'event_type': event_type,
        'page': page,
        'properties': properties
    }

def main():
    """Main loop to generate and send events"""
    try:
        while True:
            # Generate a random event
            event = generate_event()
            
            # Convert to JSON string
            event_json = json.dumps(event)
            
            # Produce message
            producer.produce(
                'web-events',
                key=event['user_id'],
                value=event_json,
                callback=delivery_report
            )
            
            # Serve delivery callbacks from previous produce calls
            producer.poll(0)
            
            # Simulate random timing between events
            time.sleep(random.uniform(0.1, 1.0))
            
    except KeyboardInterrupt:
        print('Producer interrupted')
    finally:
        # Wait for any outstanding messages to be delivered
        producer.flush()
        print('Producer closed')

if __name__ == '__main__':
    main()