import os.path
import tempfile
from datetime import datetime

from botocore.exceptions import ClientError
from celery import Celery
from fastapi import FastAPI, UploadFile, HTTPException
import boto3
import uuid
from moviepy.editor import VideoFileClip
from fastapi.responses import FileResponse
from app.utils import (
    table_name,
    key_schema,
    attribute_definitions,
    VideoInfo,
    convert_dynamodb_item_to_video_info,
)

app = FastAPI(
    title="Video Service",
)

# Celery configuration
celery = Celery("app.tasks", broker="redis://redis:6379")

# Configure S3 client
s3 = boto3.client(
    "s3",
    endpoint_url="http://localstack:4566",  # LocalStack S3 endpoint URL
    aws_access_key_id="test",  # Use any access key
    aws_secret_access_key="test",  # Use any secret key
)

# Configure DynamoDB client
dynamodb = boto3.client(
    "dynamodb",
    endpoint_url="http://localstack:4566",  # Use the hostname of the LocalStack service
    aws_access_key_id="test",  # Use the default access key ID
    aws_secret_access_key="test",  # Use the default secret access key
    region_name="us-west-2",
)


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


# Create the DynamoDB table
try:
    dynamodb.create_table(
        TableName=table_name,
        KeySchema=key_schema,
        AttributeDefinitions=attribute_definitions,
        ProvisionedThroughput={"ReadCapacityUnits": 1, "WriteCapacityUnits": 1},
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
                "video_id": {"S": video_id},
                "name": {"S": file.filename},
                "size": {"N": str(file.size)},
                "length": {"N": str(0)},
                "creation_date": {"S": str(creation_date)},
                "processing_status": {"S": "processing"},
            },
        )

        return True

    except Exception as e:
        # Handle exceptions here
        raise e


def update_video_status(video_id: str, status: str, new_length: int):
    # Check if the video ID exists in the database
    response = dynamodb.update_item(
        TableName=table_name,
        Key={"video_id": {"S": video_id}},
        UpdateExpression="SET processing_status = :status, #l = :new_length",
        ExpressionAttributeValues={
            ":status": {"S": status},
            ":new_length": {"N": str(new_length)},
        },
        ExpressionAttributeNames={"#l": "length"},
        ReturnValues="ALL_NEW",  # If you want to get the updated item after the update
    )

    updated_item = response.get("Attributes")

    if updated_item is None:
        raise HTTPException(
            status_code=404, detail=f"Video with ID {video_id} not found"
        )

    print(updated_item)


# Define your Celery task to compress the video
@celery.task
def compress_video(video_id, original_name, file_contents):
    input_path = os.path.join(os.getcwd(), f"{video_id}_temp_video.mp4")
    output_path = os.path.join(os.getcwd(), f"{video_id}_compressed_video.mp4")
    target_resolution = (480, 360)  # Adjust as needed

    # Save the uploaded video to a temporary location
    with open(input_path, "wb") as temp_file:
        temp_file.write(file_contents)

    # Compress the video using MoviePy
    video = VideoFileClip(input_path)
    compressed_video = video.resize(target_resolution)
    compressed_video.write_videofile(output_path)

    # Upload the original video to S3
    upload_to_s3(video_id, input_path, is_compressed=False)

    # Upload the compressed video to S3
    upload_to_s3(video_id, output_path, is_compressed=True)

    # Update the status in DynamoDB
    # Converted the video duration to an integer, since it is in seconds, eliminated milliseconds
    update_video_status(video_id, "done", int(compressed_video.duration))

    # Clean up the temporary files
    video.close()
    compressed_video.close()


def upload_to_s3(video_id, file_path, is_compressed=False):
    try:
        bucket_name = "videos"
        object_key = f'{video_id}/{"compressed_" if is_compressed else ""}video.mp4'
        # Check if the bucket already exists, create it if not
        response = s3.list_buckets()
        buckets = [bucket["Name"] for bucket in response["Buckets"]]
        if bucket_name not in buckets:
            s3.create_bucket(Bucket=bucket_name)
            print(f"Bucket '{bucket_name}' created successfully.")

        # Upload the file to S3
        s3.upload_file(
            file_path, bucket_name, object_key, ExtraArgs={"ACL": "public-read"}
        )

        print(f"Object '{object_key}' uploaded successfully to bucket '{bucket_name}'.")
    except Exception as e:
        print(f"An error occurred: {e}")


# Get information about the source video file using video_id
@app.get("/video/{video_id}/info/", response_model=VideoInfo)
async def get_video_info(video_id: str):
    # Retrieve video metadata from DynamoDB based on video_id
    # Return the metadata as a VideoInfo object
    try:
        # Retrieve item from DynamoDB based on video_id
        response = dynamodb.get_item(
            TableName=table_name, Key={"video_id": {"S": video_id}}
        )
        # Extract the item from the DynamoDB response
        item = response.get("Item")

        # If item is found, convert it to VideoInfo and return
        if item:
            video_info = convert_dynamodb_item_to_video_info(item)
            return video_info

        # If item is not found, return a 404 response
        else:
            raise HTTPException(
                status_code=404,
                detail="Video not found / Enter video id without quotes",
            )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Download the original video using video_id
@app.get("/video/{video_id}/original/")
async def download_original_video(video_id: str):
    # Generate a pre-signed URL for the original video
    bucket_name = "videos"  # Replace with your S3 bucket name
    object_key = f"{video_id}/video.mp4"  # Modify the object key as needed

    try:
        # Retrieve the original video file from S3
        response = s3.get_object(Bucket=bucket_name, Key=object_key)

        # Create a temporary file to save the video content
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            temp_file.write(response["Body"].read())
            temp_file.seek(0)

            # Determine the content type and file name
            content_type = response["ContentType"]
            file_name = os.path.basename(object_key)

            # Return the video file as a response with appropriate headers
            return FileResponse(
                temp_file.name,
                headers={"Content-Disposition": f"attachment; filename={file_name}"},
                media_type=content_type,
            )
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error downloading video: {str(e)}"
        )


# Download the compressed video using video_id
@app.get("/video/{video_id}/compressed/")
async def download_compressed_video(video_id: str):
    # Generate a pre-signed URL for the compressed video
    bucket_name = "videos"  # Replace with your S3 bucket name
    object_key = f"{video_id}/compressed_video.mp4"  # Modify the object key as needed

    try:
        # Retrieve the compressed video file from S3
        response = s3.get_object(Bucket=bucket_name, Key=object_key)

        # Create a temporary file to save the video content
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            temp_file.write(response["Body"].read())
            temp_file.seek(0)

            # Determine the content type and file name
            content_type = response["ContentType"]
            file_name = os.path.basename(object_key)

            # Return the compressed video file as a response with appropriate headers
            return FileResponse(
                temp_file.name,
                headers={"Content-Disposition": f"attachment; filename={file_name}"},
                media_type=content_type,
            )
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error downloading video: {str(e)}"
        )


def delete_video_metadata(video_id: str):
    try:
        # Delete the item from DynamoDB based on video_id
        dynamodb.delete_item(TableName=table_name, Key={"video_id": {"S": video_id}})

        print(f"Video metadata for video_id {video_id} deleted successfully.")
    except ClientError as e:
        # Handle specific errors, if needed
        print(f"Error deleting video metadata: {str(e)}")


# Modify the delete_video function to call delete_video_metadata
@app.delete("/video/{video_id}/")
async def delete_video(video_id: str):
    # Define your S3 bucket name and object keys for both original and compressed videos
    bucket_name = "videos"  # Replace with your S3 bucket name
    original_video_key = f"{video_id}/video.mp4"
    compressed_video_key = f"{video_id}/compressed_video.mp4"

    try:
        # Delete the original video from S3
        s3.delete_object(Bucket=bucket_name, Key=original_video_key)

        # Delete the compressed video from S3
        s3.delete_object(Bucket=bucket_name, Key=compressed_video_key)

        # Remove the video's metadata from DynamoDB
        delete_video_metadata(video_id)

        # Return a success message or status code
        return {"message": "Video deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting video: {str(e)}")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
