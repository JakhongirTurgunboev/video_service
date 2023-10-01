# Define the table name
table_name = 'videos_table'

# Define the KeySchema and AttributeDefinitions
key_schema = [
    {
        'AttributeName': 'video_id',
        'KeyType': 'HASH'  # HASH indicates the partition key
    }
]

attribute_definitions = [
    {
        'AttributeName': 'video_id',
        'AttributeType': 'S'
    },
    {
        'AttributeName': 'name',
        'AttributeType': 'S'
    },
    {
        'AttributeName': 'size',
        'AttributeType': 'N'
    },
    {
        'AttributeName': 'length',
        'AttributeType': 'N'
    },
    {
        'AttributeName': 'creation_date',
        'AttributeType': 'S'
    },
    {
        'AttributeName': 'processing_status',
        'AttributeType': 'S'
    }
]
