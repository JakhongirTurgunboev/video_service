# Use an official Python runtime as a parent image
FROM python:3.8

# Set the working directory to /app
WORKDIR /app

# Install dependencies first (leveraging Docker cache)
COPY requirements.txt /app/
RUN pip install --upgrade pip && pip install -r requirements.txt

# Copy the current directory contents into the container at /app
COPY . /app

# Make port 8000 available to the world outside this container
EXPOSE 8000

# Define environment variables
ENV DYNAMODB_ENDPOINT=http://localstack:4566
ENV S3_ENDPOINT=http://localstack:4572

# Run main.py when the container launches
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
