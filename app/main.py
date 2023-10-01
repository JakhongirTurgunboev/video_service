from datetime import datetime

from celery import Celery
from fastapi import FastAPI, UploadFile, HTTPException
from pydantic import BaseModel
import boto3
import uuid
from moviepy.editor import VideoFileClip

app = FastAPI(
    title="Video Service",
)

# Configure AWS S3 client
s3 = boto3.client('s3',
                    endpoint_url='http://localstack:4572',
                    aws_access_key_id='test',  # Use the default access key ID
                    aws_secret_access_key='test',  # Use the default secret access key
                    region_name='us-east-1'
                  )

# Celery configuration
celery = Celery('app.tasks', broker='redis://redis:6379')

# Configure DynamoDB client
dynamodb = boto3.client(
    'dynamodb',
    endpoint_url='http://localstack:4566',  # Use the hostname of the LocalStack service
    aws_access_key_id='test',               # Use the default access key ID
    aws_secret_access_key='test',            # Use the default secret access key
    region_name='us-west-2'
)


# Define a model for video metadata
class VideoInfo(BaseModel):
    video_id: str
    name: str
    size: int
    length: int
    creation_date: str
    processing_status: str


@app.post("/upload/")
async def upload_video(file: UploadFile):
    # Generate a unique video ID
    video_id = str(uuid.uuid4())

    # Store video metadata in DynamoDB (you'll need to set up DynamoDB)
    store_video_metadata(video_id, file)

    # Queue the compression task with Celery
    compress_video.apply_async(args=(video_id, file.filename, file.file.read()))

    # Return the video ID as a response
    return {"video_id": video_id}


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
        'AttributeType': 'S'  # 'S' represents a string attribute
    }
]
# Create the DynamoDB table
try:
    dynamodb.create_table(
        TableName=table_name,
        KeySchema=key_schema,
        AttributeDefinitions=attribute_definitions,
        ProvisionedThroughput={
            'ReadCapacityUnits': 1,
            'WriteCapacityUnits': 1
        }
    )
    print(f"Table '{table_name}' created successfully.")
except dynamodb.exceptions.ResourceInUseException:
    print(f"Table '{table_name}' already exists.")


def store_video_metadata(video_id, file):
    try:
        creation_date = datetime.now().isoformat()
        dynamodb.put_item(
            TableName=table_name,
            Item={
                'video_id': {'S': video_id},
                'name': {'S': file.filename},
                'size': {'N': str(file.size)},
                'length': {'N': str(0)},
                'creation_date': {'S': str(creation_date)},
                'processing_status': {'S': "processing"},
            }
        )

        return True

    except Exception as e:
        # Handle exceptions here
        raise e


def update_video_status(video_id: str, status: str, length: str):
    # Check if the video ID exists in the database
    video_database = dynamodb.get_item(
        TableName=table_name,
    )
    if video_id not in video_database:
        raise HTTPException(status_code=404, detail=f"Video with ID {video_id} not found")

    # Update the processing status
    video_database[video_id].processing_status = status
    video_database[video_id].length = length


# Define your Celery task to compress the video
@celery.task
def compress_video(video_id, original_name, file_contents):
    input_path = f"{video_id}_temp_video.mp4"
    output_path = f"{video_id}_compressed_video.mp4"
    target_resolution = (480, 360)  # Adjust as needed

    # Save the uploaded video to a temporary location
    with open(input_path, "wb") as temp_file:
        temp_file.write(file_contents)

    # Compress the video using MoviePy
    video = VideoFileClip(input_path)
    compressed_video = video.resize(target_resolution)
    compressed_video.write_videofile(output_path)

    # Upload the compressed video to S3
    upload_to_s3(video_id, output_path)

    # Update the status in DynamoDB
    update_video_status(video_id, "done", str(compressed_video.duration))

    # Clean up the temporary files
    video.close()
    compressed_video.close()

    # Optionally, you can remove the temporary files here


def upload_to_s3(video_id, file_path):
    # Use the boto3 library to upload the file to S3
    s3 = boto3.client('s3',
                      endpoint_url='http://localstack:4572',  # LocalStack S3 endpoint URL
                      aws_access_key_id='test',  # Use any access key
                      aws_secret_access_key='test',  # Use any secret key
                      )

    bucket_name = 'videos'
    object_key = f'{video_id}/compressed_video.mp4'

    try:
        # Check if the bucket already exists, create it if not
        response = s3.list_buckets()
        buckets = [bucket['Name'] for bucket in response['Buckets']]
        if bucket_name not in buckets:
            s3.create_bucket(Bucket=bucket_name)
            print(f"Bucket '{bucket_name}' created successfully.")

        s3.upload_file(file_path, bucket_name, object_key, ExtraArgs={'ACL': 'public-read'})  # Add ExtraArgs if needed

        print(f"Object '{object_key}' uploaded successfully.")
    except Exception as e:
        print(f"An error occurred: {e}")


# Function to convert DynamoDB response to VideoInfo
def convert_dynamodb_item_to_video_info(item: dict) -> VideoInfo:
    return VideoInfo(
        video_id=item.get('video_id', {}).get('S', ''),
        name=item.get('name', {}).get('S', ''),
        size=int(item.get('size', {}).get('N', 0)),
        length=int(item.get('length', {}).get('N', 0)),
        creation_date=item.get('creation_date', {}).get('S', ''),
        processing_status=item.get('processing_status', {}).get('S', '')
    )


# Get information about the source video file using video_id
@app.get("/video/{video_id}/info/", response_model=VideoInfo)
async def get_video_info(video_id: str):
    # Retrieve video metadata from DynamoDB based on video_id
    # Return the metadata as a VideoInfo object
    try:
        # Retrieve item from DynamoDB based on video_id
        response = dynamodb.get_item(
            TableName=table_name,
            Key={'video_id': {'S': video_id}}
        )
        # Extract the item from the DynamoDB response
        item = response.get('Item')

        # If item is found, convert it to VideoInfo and return
        if item:
            video_info = convert_dynamodb_item_to_video_info(item)
            return video_info

        # If item is not found, return a 404 response
        else:
            raise HTTPException(status_code=404, detail="Video not found / Enter video id without quotes")

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Download the original video using video_id
@app.get("/video/{video_id}/original/")
async def download_original_video(video_id: str):
    # Use S3 to generate a pre-signed URL for the original video
    # Return a redirect to the pre-signed URL
    return {"video_id": video_id, "message": "Redirect to original video URL"}


# Download the compressed video using video_id
@app.get("/video/{video_id}/compressed/")
async def download_compressed_video(video_id: str):
    # Use S3 to generate a pre-signed URL for the compressed video
    # Return a redirect to the pre-signed URL
    return {"video_id": video_id, "message": "Redirect to compressed video URL"}


# Delete a video using video_id
@app.delete("/video/{video_id}/")
async def delete_video(video_id: str):
    # Delete the video file from S3
    # Remove the video's metadata from DynamoDB
    # Return a success message or status code
    return {"message": "Video deleted successfully"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
