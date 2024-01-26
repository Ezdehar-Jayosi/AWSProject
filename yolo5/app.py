import time
from pathlib import Path
from detect import run
import yaml
from loguru import logger
import os
import boto3
import requests
import json

# Retrieve sensitive information from AWS Secrets Manager
secrets_manager = boto3.client('secretsmanager', region_name='eu-west-3')

def get_secret(secret_name):
    try:
        secret_response = secrets_manager.get_secret_value(SecretId=secret_name)
        return json.loads(secret_response['SecretString'])
    except Exception as e:
        logger.error(f"Error retrieving secret '{secret_name}': {e}")
        raise

secrets = get_secret('ezdehar-secret')

images_bucket = secrets['BUCKET_NAME']
queue_name = secrets['SQS_QUEUE_NAME']
polybot_url = 'http://polybot-alb-url/results'  # Replace with the actual ALB URL of Polybot

sqs_client = boto3.client('sqs', region_name='eu-west-3')

with open("data/coco128.yaml", "r") as stream:
    names = yaml.safe_load(stream)['names']



def consume():
    while True:
        response = sqs_client.receive_message(QueueUrl=queue_name, MaxNumberOfMessages=1, WaitTimeSeconds=5)

        if 'Messages' in response:
            message = response['Messages'][0]['Body']
            receipt_handle = response['Messages'][0]['ReceiptHandle']

            # Use the ReceiptHandle as a prediction UUID
            prediction_id = response['Messages'][0]['MessageId']

            logger.info(f'prediction: {prediction_id}. start processing')

            # Receives parameters from the message
            message_body = json.loads(message)
            img_name = message_body.get('photo_key')
            chat_id = message_body.get('chat_id')
           # original_img_path = f'{img_name}'
            logger.info(f'S3 Bucket: {images_bucket}, Image Name: {img_name}')

            original_img_path = download_from_s3(img_name, prediction_id)

            logger.info(f'prediction: {prediction_id}/{original_img_path}. Download img completed')

            # Predicts the objects in the image
            run(
                weights='yolov5s.pt',
                data='data/coco128.yaml',
                source=original_img_path,
                project='static/data',
                name=prediction_id,
                save_txt=True
            )

            logger.info(f'prediction: {prediction_id}/{original_img_path}. done')

            # This is the path for the predicted image with labels
            predicted_img_path = Path(f'static/data/{prediction_id}/{original_img_path}')

            # Upload the predicted image to S3 (do not override the original image)
            upload_to_s3(predicted_img_path, f'predicted_images/{prediction_id}/{original_img_path}')

            # Parse prediction labels and create a summary
            pred_summary_path = Path(f'static/data/{prediction_id}/labels/{original_img_path.split(".")[0]}.txt')
            if pred_summary_path.exists():
                labels = parse_labels(pred_summary_path)
                logger.info(f'prediction: {prediction_id}/{original_img_path}. prediction summary:\n\n{labels}')

                prediction_summary = {
                    'prediction_id': prediction_id,
                    'original_img_path': original_img_path,
                    'predicted_img_path': predicted_img_path,
                    'labels': labels,
                    'time': time.time()
                }

                # Store the prediction_summary in a DynamoDB table
                store_in_dynamodb(prediction_summary)

                # Perform a GET request to Polybot's /results endpoint
                send_results_to_polybot(prediction_summary)

            # Delete the message from the queue as the job is considered as DONE
            sqs_client.delete_message(QueueUrl=queue_name, ReceiptHandle=receipt_handle)


def download_from_s3(img_name, prediction_id):
    # Remove 'photos/' prefix if it exists in img_name
    img_name_without_prefix = img_name[len('photos/'):] if img_name.startswith('photos/') else img_name
    local_file_path = Path(f'photos/{prediction_id}.jpg')

    try:
        # Ensure 'photos' directory exists locally
        photos_directory = Path("photos")
        photos_directory.mkdir(parents=True, exist_ok=True)

        boto3.client('s3').download_file(images_bucket, img_name_without_prefix, str(local_file_path))
    except Exception as e:
        logger.error(f'Error downloading image from S3: {e}')
        raise

    return str(local_file_path)



def upload_to_s3(local_path, s3_key):
    try:
        # Extract directory path from s3_key
        directory_path = '/'.join(s3_key.split('/')[:-1])

        # Ensure the directory exists locally
        local_directory = Path(directory_path)
        local_directory.mkdir(parents=True, exist_ok=True)

        # Upload the file to S3
        boto3.client('s3').upload_file(local_path, images_bucket, s3_key)
    except Exception as e:
        logger.error(f'Error uploading to S3: {e}')
        raise




def parse_labels(pred_summary_path):
    with open(pred_summary_path) as f:
        labels = f.read().splitlines()
        labels = [line.split(' ') for line in labels]
        labels = [{
            'class': names[int(l[0])],
            'cx': float(l[1]),
            'cy': float(l[2]),
            'width': float(l[3]),
            'height': float(l[4]),
        } for l in labels]

    return labels


def store_in_dynamodb(prediction_summary):
    try:
        boto3.resource('dynamodb').Table('ezdehar-table').put_item(Item=prediction_summary)
    except Exception as e:
        logger.error(f'Error storing in DynamoDB: {e}')
        raise


def send_results_to_polybot(prediction_summary):
    try:
        response = requests.get(polybot_url, params={'predictionId': prediction_summary['prediction_id']})
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        logger.error(f'Error sending results to Polybot: {e}')
        raise


if __name__ == "__main__":
    consume()
