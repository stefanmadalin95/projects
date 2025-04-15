#!/usr/bin/env python3
import json
from collections import defaultdict, deque
from datetime import datetime, timedelta
import time
from confluent_kafka import Consumer, KafkaError

# Kafka consumer configuration
conf = {
    'bootstrap.servers': 'localhost:9092',
    'group.id': 'web-analytics-group',
    'auto.offset.reset': 'earliest',
    'enable.auto.commit': True,
    'auto.commit.interval.ms': 5000
}

# Create Consumer instance
consumer = Consumer(conf)

# Subscribe to topic
consumer.subscribe(['web-events'])

# Analytics data structures
# For simplicity, we'll keep everything in memory
# In a real application, you might use Redis or another database

# Sliding window of 5 minutes for active users
WINDOW_SIZE = 5 * 60  # 5 minutes in seconds
active_users = deque()

# Counters for various metrics
page_views = defaultdict(int)
event_counts = defaultdict(int)
sales_data = {
    'total_revenue': 0.0,
    'order_count': 0,
    'avg_order_value': 0.0
}
product_popularity = defaultdict(int)

def clean_expired_sessions(current_time):
    """Remove sessions older than WINDOW_SIZE from active_users queue"""
    cutoff_time = current_time - timedelta(seconds=WINDOW_SIZE)
    
    while active_users and active_users[0]['timestamp'] < cutoff_time:
        active_users.popleft()

def process_event(event):
    """Process a single web event and update analytics metrics"""
    event_type = event['event_type']
    page = event['page']
    user_id = event['user_id']
    timestamp = datetime.fromisoformat(event['timestamp'])
    properties = event['properties']
    
    # Update event counts
    event_counts[event_type] += 1
    
    # Update page views
    if event_type == 'page_view':
        page_views[page] += 1
    
    # Track active users
    active_users.append({
        'user_id': user_id,
        'timestamp': timestamp
    })
    clean_expired_sessions(timestamp)
    
    # Handle specific event types
    if event_type == 'add_to_cart':
        product_id = properties['product_id']
        product_popularity[product_id] += properties['quantity']
    
    elif event_type == 'purchase':
        amount = properties['total_amount']
        sales_data['total_revenue'] += amount
        sales_data['order_count'] += 1
        sales_data['avg_order_value'] = sales_data['total_revenue'] / sales_data['order_count']

def print_analytics():
    """Print current analytics metrics"""
    print("\n===== REAL-TIME WEB ANALYTICS =====")
    print(f"Active Users (last 5 min): {len(set(item['user_id'] for item in active_users))}")
    
    print("\nTop 5 Pages:")
    for page, count in sorted(page_views.items(), key=lambda x: x[1], reverse=True)[:5]:
        print(f"  {page}: {count} views")
    
    print("\nEvent Distribution:")
    total_events = sum(event_counts.values())
    for event_type, count in event_counts.items():
        percentage = (count / total_events * 100) if total_events > 0 else 0
        print(f"  {event_type}: {count} ({percentage:.1f}%)")
    
    print("\nSales Data:")
    print(f"  Total Revenue: ${sales_data['total_revenue']:.2f}")
    print(f"  Orders: {sales_data['order_count']}")
    print(f"  Avg. Order Value: ${sales_data['avg_order_value']:.2f}")
    
    print("\nTop 3 Popular Products:")
    for product, quantity in sorted(product_popularity.items(), key=lambda x: x[1], reverse=True)[:3]:
        print(f"  {product}: Added to cart {quantity} times")
    
    print("====================================\n")

def main():
    """Main consumer loop"""
    try:
        last_report_time = time.time()
        
        while True:
            # Poll for messages
            msg = consumer.poll(1.0)
            
            if msg is None:
                continue
            
            if msg.error():
                if msg.error().code() == KafkaError._PARTITION_EOF:
                    print(f"Reached end of partition {msg.partition()}")
                else:
                    print(f"Error: {msg.error()}")
            else:
                # Process message
                try:
                    event = json.loads(msg.value())
                    process_event(event)
                except json.JSONDecodeError:
                    print(f"Failed to parse message: {msg.value()}")
            
            # Print analytics every 5 seconds
            current_time = time.time()
            if current_time - last_report_time >= 5:
                print_analytics()
                last_report_time = current_time
    
    except KeyboardInterrupt:
        print("Consumer interrupted")
    finally:
        # Close consumer connection
        consumer.close()
        print("Consumer closed")

if __name__ == '__main__':
    main()