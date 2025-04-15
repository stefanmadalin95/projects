#!/usr/bin/env python3
from flask import Flask, render_template, jsonify
from flask_socketio import SocketIO
import json
import threading
import time
from confluent_kafka import Consumer, KafkaError
from collections import defaultdict, deque
from datetime import datetime, timedelta

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

# Kafka consumer configuration
conf = {
    'bootstrap.servers': 'localhost:9092',
    'group.id': 'web-dashboard-group',
    'auto.offset.reset': 'latest',
    'enable.auto.commit': True
}

# Analytics data structures
WINDOW_SIZE = 5 * 60  # 5 minutes in seconds
active_users = deque()
page_views = defaultdict(int)
event_counts = defaultdict(int)
sales_data = {
    'total_revenue': 0.0,
    'order_count': 0,
    'avg_order_value': 0.0
}
product_popularity = defaultdict(int)

# Time series data for charts
time_series_data = {
    'timestamps': [],
    'active_users': [],
    'page_views': [],
    'revenue': []
}

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

def update_time_series():
    """Update time series data for charts"""
    current_time = datetime.now().strftime('%H:%M:%S')
    active_user_count = len(set(item['user_id'] for item in active_users))
    
    time_series_data['timestamps'].append(current_time)
    time_series_data['active_users'].append(active_user_count)
    time_series_data['page_views'].append(sum(page_views.values()))
    time_series_data['revenue'].append(sales_data['total_revenue'])
    
    # Keep only last 20 data points
    if len(time_series_data['timestamps']) > 20:
        for key in time_series_data:
            time_series_data[key] = time_series_data[key][-20:]

def get_analytics_data():
    """Prepare analytics data for the dashboard"""
    active_user_count = len(set(item['user_id'] for item in active_users))
    
    top_pages = sorted(page_views.items(), key=lambda x: x[1], reverse=True)[:5]
    
    event_distribution = []
    total_events = sum(event_counts.values())
    for event_type, count in event_counts.items():
        percentage = (count / total_events * 100) if total_events > 0 else 0
        event_distribution.append({
            'event_type': event_type,
            'count': count,
            'percentage': round(percentage, 1)
        })
    
    top_products = sorted(product_popularity.items(), key=lambda x: x[1], reverse=True)[:3]
    
    return {
        'active_users': active_user_count,
        'top_pages': dict(top_pages),
        'event_distribution': event_distribution,
        'sales_data': sales_data,
        'top_products': dict(top_products),
        'time_series': time_series_data
    }

def kafka_consumer_thread():
    """Background thread for consuming Kafka messages"""
    consumer = Consumer(conf)
    consumer.subscribe(['web-events'])
    
    try:
        while True:
            msg = consumer.poll(1.0)
            
            if msg is None:
                continue
            
            if msg.error():
                if msg.error().code() != KafkaError._PARTITION_EOF:
                    print(f"Error: {msg.error()}")
            else:
                try:
                    event = json.loads(msg.value())
                    process_event(event)
                    
                    # Emit updated data to connected clients
                    socketio.emit('analytics_update', get_analytics_data())
                except json.JSONDecodeError:
                    print(f"Failed to parse message: {msg.value()}")
            
            # Update time series data every second
            update_time_series()
            time.sleep(1)
    
    except Exception as e:
        print(f"Consumer thread error: {e}")
    finally:
        consumer.close()

@app.route('/')
def index():
    """Render dashboard template"""
    return render_template('index.html')

@app.route('/api/analytics')
def get_analytics():
    """API endpoint for getting current analytics data"""
    return jsonify(get_analytics_data())

@socketio.on('connect')
def handle_connect():
    """Handle client connection"""
    print('Client connected')
    socketio.emit('analytics_update', get_analytics_data())

if __name__ == '__main__':
    # Create templates directory and index.html file
    import os
    if not os.path.exists('templates'):
        os.makedirs('templates')
    
    with open('templates/index.html', 'w') as f:
        f.write('''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Real-time Web Analytics</title>
    <script src="https://cdn.socket.io/4.5.4/socket.io.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        body { font-family: Arial, sans-serif; margin: 0; padding: 20px; background-color: #f5f5f5; }
        .dashboard { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; }
        .card { background-color: white; border-radius: 8px; padding: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .card h2 { margin-top: 0; color: #333; border-bottom: 1px solid #eee; padding-bottom: 10px; }
        .metric { font-size: 24px; font-weight: bold; color: #2c3e50; margin: 10px 0; }
        .chart-container { height: 250px; }
        table { width: 100%; border-collapse: collapse; }
        table th, table td { text-align: left; padding: 8px; border-bottom: 1px solid #eee; }
        table th { background-color: #f9f9f9; }
    </style>
</head>
<body>
    <h1>Real-time Web Analytics Dashboard</h1>
    <div class="dashboard">
        <div class="card">
            <h2>Active Users</h2>
            <div class="metric" id="active-users">0</div>
            <div class="chart-container">
                <canvas id="active-users-chart"></canvas>
            </div>
        </div>
        <div class="card">
            <h2>Page Views</h2>
            <div class="chart-container">
                <canvas id="page-views-chart"></canvas>
            </div>
        </div>
        <div class="card">
            <h2>Event Distribution</h2>
            <div class="chart-container">
                <canvas id="event-distribution-chart"></canvas>
            </div>
        </div>
        <div class="card">
            <h2>Sales Overview</h2>
            <div class="metric">Revenue: $<span id="total-revenue">0.00</span></div>
            <div class="metric">Orders: <span id="order-count">0</span></div>
            <div class="metric">Avg Order: $<span id="avg-order-value">0.00</span></div>
            <div class="chart-container">
                <canvas id="revenue-chart"></canvas>
            </div>
        </div>
        <div class="card">
            <h2>Top Pages</h2>
            <table id="top-pages-table">
                <thead>
                    <tr>
                        <th>Page</th>
                        <th>Views</th>
                    </tr>
                </thead>
                <tbody></tbody>
            </table>
        </div>
        <div class="card">
            <h2>Top Products</h2>
            <table id="top-products-table">
                <thead>
                    <tr>
                        <th>Product</th>
                        <th>Added to Cart</th>
                    </tr>
                </thead>
                <tbody></tbody>
            </table>
        </div>
    </div>

    <script>
        // Initialize Socket.IO connection
        const socket = io();
        
        // Charts configuration
        const activeUsersChart = new Chart(
            document.getElementById('active-users-chart').getContext('2d'),
            {
                type: 'line',
                data: {
                    labels: [],
                    datasets: [{
                        label: 'Active Users',
                        data: [],
                        borderColor: 'rgb(75, 192, 192)',
                        tension: 0.1,
                        fill: false
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        y: {
                            beginAtZero: true
                        }
                    }
                }
            }
        );
        
        const pageViewsChart = new Chart(
            document.getElementById('page-views-chart').getContext('2d'),
            {
                type: 'line',
                data: {
                    labels: [],
                    datasets: [{
                        label: 'Page Views',
                        data: [],
                        borderColor: 'rgb(54, 162, 235)',
                        tension: 0.1,
                        fill: false
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        y: {
                            beginAtZero: true
                        }
                    }
                }
            }
        );
        
        const eventDistributionChart = new Chart(
            document.getElementById('event-distribution-chart').getContext('2d'),
            {
                type: 'pie',
                data: {
                    labels: [],
                    datasets: [{
                        data: [],
                        backgroundColor: [
                            'rgba(255, 99, 132, 0.6)',
                            'rgba(54, 162, 235, 0.6)',
                            'rgba(255, 206, 86, 0.6)',
                            'rgba(75, 192, 192, 0.6)',
                            'rgba(153, 102, 255, 0.6)'
                        ]
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false
                }
            }
        );
        
        const revenueChart = new Chart(
            document.getElementById('revenue-chart').getContext('2d'),
            {
                type: 'line',
                data: {
                    labels: [],
                    datasets: [{
                        label: 'Revenue ($)',
                        data: [],
                        borderColor: 'rgb(153, 102, 255)',
                        tension: 0.1,
                        fill: false
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        y: {
                            beginAtZero: true
                        }
                    }
                }
            }
        );
        
        // Update dashboard with analytics data
        function updateDashboard(data) {
            // Update active users
            document.getElementById('active-users').textContent = data.active_users;
            
            // Update sales metrics
            document.getElementById('total-revenue').textContent = data.sales_data.total_revenue.toFixed(2);
            document.getElementById('order-count').textContent = data.sales_data.order_count;
            document.getElementById('avg-order-value').textContent = data.sales_data.avg_order_value.toFixed(2);
            
            // Update top pages table
            const topPagesTable = document.getElementById('top-pages-table').getElementsByTagName('tbody')[0];
            topPagesTable.innerHTML = '';
            for (const [page, views] of Object.entries(data.top_pages)) {
                const row = topPagesTable.insertRow();
                row.insertCell(0).textContent = page;
                row.insertCell(1).textContent = views;
            }
            
            // Update top products table
            const topProductsTable = document.getElementById('top-products-table').getElementsByTagName('tbody')[0];
            topProductsTable.innerHTML = '';
            for (const [product, count] of Object.entries(data.top_products)) {
                const row = topProductsTable.insertRow();
                row.insertCell(0).textContent = product;
                row.insertCell(1).textContent = count;
            }
            
            // Update event distribution chart
            eventDistributionChart.data.labels = data.event_distribution.map(e => e.event_type);
            eventDistributionChart.data.datasets[0].data = data.event_distribution.map(e => e.count);
            eventDistributionChart.update();
            
            // Update time series charts
            activeUsersChart.data.labels = data.time_series.timestamps;
            activeUsersChart.data.datasets[0].data = data.time_series.active_users;
            activeUsersChart.update();
            
            pageViewsChart.data.labels = data.time_series.timestamps;
            pageViewsChart.data.datasets[0].data = data.time_series.page_views;
            pageViewsChart.update();
            
            revenueChart.data.labels = data.time_series.timestamps;
            revenueChart.data.datasets[0].data = data.time_series.revenue;
            revenueChart.update();
        }
        
        // Listen for updates from the server
        socket.on('analytics_update', updateDashboard);
    </script>
</body>
</html>
        ''')
    
    # Start Kafka consumer thread
    threading.Thread(target=kafka_consumer_thread, daemon=True).start()
    
    # Start Flask-SocketIO server
    socketio.run(app, debug=True, host='0.0.0.0', port=5000)