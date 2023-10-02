import os
import tempfile
import pytest
import requests
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app import main

client = TestClient(main.app)


@pytest.fixture
def video_id():
    return "test-video"


# Test uploading a video
def test_upload_video():
    # Create a temporary file for testing
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as temp_file:
        temp_file.write(b"Test video content")
        temp_file.seek(0)

        # Send a POST request to the /upload/ endpoint
        response = client.post("/upload/", files={"file": temp_file})

        # Assert that the response has a status code of 200
        assert response.status_code == 200

        # Assert that the response JSON contains a video_id field
        assert "video_id" in response.json()

        # Remember the video_id for later tests
        video_id = response.json()["video_id"]

    # Clean up the temporary file
    os.remove(temp_file.name)


# Test getting video information
def test_get_video_info(video_id):
    response = client.get(f"/video/{video_id}/info/")

    # Assert that the response has a status code of 200
    assert response.status_code == 200

    # Assert that the response JSON matches the expected structure
    expected_keys = [
        "video_id",
        "name",
        "size",
        "length",
        "creation_date",
        "processing_status",
    ]
    assert all(key in response.json() for key in expected_keys)


# Test downloading the original video
def test_download_original_video(video_id):
    response = client.get(f"/video/{video_id}/original/")

    # Assert that the response has a status code of 200
    assert response.status_code == 200

    # Assert that the response contains the expected content type
    assert "video/mp4" in response.headers["content-type"]

    # Optionally, you can write the response content to a file for further inspection


# Test downloading the compressed video
def test_download_compressed_video(video_id):
    response = client.get(f"/video/{video_id}/compressed/")

    # Assert that the response has a status code of 200
    assert response.status_code == 200

    # Assert that the response contains the expected content type
    assert "video/mp4" in response.headers["content-type"]

    # Optionally, you can write the response content to a file for further inspection


# Test deleting a video
def test_delete_video(video_id):
    response = client.delete(f"/video/{video_id}/")

    # Assert that the response has a status code of 200
    assert response.status_code == 200

    # Assert that the response JSON contains a success message
    assert "message" in response.json()
    assert response.json()["message"] == "Video deleted successfully"
