from kombu import Exchange, Queue

# Celery Configuration
broker_url = 'redis://redis:6379/0'
result_backend = 'redis://redis:6379/0'
accept_content = ['json']
result_serializer = 'json'
task_serializer = 'json'

# Define queues for tasks
task_queues = (
    Queue('default', Exchange('default'), routing_key='default'),
)

# Define task routes
task_routes = {
    'app.main.*': {'queue': 'default'},
}
