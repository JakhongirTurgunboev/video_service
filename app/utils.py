from moviepy.editor import VideoFileClip
from pydantic import BaseModel


# Define the model for video metadata
class VideoInfo(BaseModel):
    video_id: str
    name: str
    size: int
    length: int
    creation_date: str
    processing_status: str


# Function to convert DynamoDB response to VideoInfo
def convert_dynamodb_item_to_video_info(item: dict) -> VideoInfo:
    return VideoInfo(
        video_id=item.get("video_id", {}).get("S", ""),
        name=item.get("name", {}).get("S", ""),
        size=int(item.get("size", {}).get("N", 0)),
        length=int(item.get("length", {}).get("N", 0)),
        creation_date=item.get("creation_date", {}).get("S", ""),
        processing_status=item.get("processing_status", {}).get("S", ""),
    )


# Define the table name
table_name = "videos_table"

# Define the KeySchema and AttributeDefinitions
key_schema = [
    {"AttributeName": "video_id", "KeyType": "HASH"}  # HASH indicates the partition key
]

attribute_definitions = [
    {
        "AttributeName": "video_id",
        "AttributeType": "S",  # 'S' represents a string attribute
    }
]
