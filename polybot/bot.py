import telebot
from loguru import logger
import os
import time
from telebot.types import InputFile
import boto3
import json

class Bot:

    def __init__(self, token, telegram_chat_url):
        # create a new instance of the TeleBot class.
        # all communication with Telegram servers are done using self.telegram_bot_client
        self.telegram_bot_client = telebot.TeleBot(token)

        # remove any existing webhooks configured in Telegram servers
        self.telegram_bot_client.remove_webhook()
        time.sleep(0.5)

        # set the webhook URL
        self.telegram_bot_client.set_webhook(url=f'{telegram_chat_url}/{token}/', timeout=60)

        logger.info(f'Telegram Bot information\n\n{self.telegram_bot_client.get_me()}')

    def send_text(self, chat_id, text):
        self.telegram_bot_client.send_message(chat_id, text)

    def send_text_with_quote(self, chat_id, text, quoted_msg_id):
        self.telegram_bot_client.send_message(chat_id, text, reply_to_message_id=quoted_msg_id)

    def is_current_msg_photo(self, msg):
        return 'photo' in msg

    def download_user_photo(self, msg):
        """
        Downloads the photos that sent to the Bot to `photos` directory (should be existed)
        :return:
        """
        if not self.is_current_msg_photo(msg):
            raise RuntimeError(f'Message content of type \'photo\' expected')

        file_info = self.telegram_bot_client.get_file(msg['photo'][-1]['file_id'])
        data = self.telegram_bot_client.download_file(file_info.file_path)
        folder_name = file_info.file_path.split('/')[0]

        if not os.path.exists(folder_name):
            os.makedirs(folder_name)

        with open(file_info.file_path, 'wb') as photo:
            photo.write(data)

        return file_info.file_path

    def send_photo(self, chat_id, img_path):
        if not os.path.exists(img_path):
            raise RuntimeError("Image path doesn't exist")

        self.telegram_bot_client.send_photo(
            chat_id,
            InputFile(img_path)
        )

    def handle_message(self, msg):
        """Bot Main message handler"""
        logger.info(f'Incoming message: {msg}')
        self.send_text(msg['chat']['id'], f'Your original message: {msg["text"]}')


class ObjectDetectionBot(Bot):
    def __init__(self, telegram_token_secret_name, telegram_chat_url, s3_bucket_secret_name, sqs_queue_secret_name):
        # Retrieve sensitive information from AWS Secrets Manager
        secrets_manager = boto3.client('ezdehar-secret', region_name='eu-west-3')

        telegram_token = self.get_secret('TELEGRAM_TOKEN', secrets_manager)
        self.s3_bucket_name= self.get_secret('S3_BUCKET_URL', secrets_manager)
        self.sqs_queue_url = self.get_secret('SQS_QUEUE_NAME', secrets_manager)

        super().__init__(telegram_token, telegram_chat_url)
        self.s3 = boto3.client('s3')
        self.sqs = boto3.client('sqs')


    def handle_message(self, msg):
        logger.info(f'Incoming message: {msg}')

        if self.is_current_msg_photo(msg):
            photo_path = self.download_user_photo(msg)

            # Upload the photo to S3
            s3_key = f'photos/{os.path.basename(photo_path)}'
            self.upload_to_s3(photo_path, s3_key)

            # Send a job to the SQS queue
            job_message = {
                'photo_key': s3_key,
                'chat_id': msg['chat']['id']
            }
            self.send_to_sqs(json.dumps(job_message))

            # Send a message to the Telegram end-user
            self.send_text(msg['chat']['id'], 'Your image is being processed. Please wait...')

    def upload_to_s3(self, local_path, s3_key):
        self.s3.upload_file(local_path, self.s3_bucket_name, s3_key)

    def send_to_sqs(self, message_body):
        self.sqs.send_message(QueueUrl=self.sqs_queue_url, MessageBody=message_body)

    @staticmethod
    def get_secret(secret_name, secrets_manager):
        try:
            get_secret_value_response = secrets_manager.get_secret_value(SecretId=secret_name)
            return json.loads(get_secret_value_response['SecretString'])['value']
        except Exception as e:
            logger.error(f"Error retrieving secret '{secret_name}': {e}")
            raise

# Example usage:
telegram_token_secret = 'YOUR_TELEGRAM_TOKEN_SECRET_NAME'
telegram_chat_url = 'YOUR_TELEGRAM_WEBHOOK_URL'
s3_bucket_secret = 'YOUR_S3_BUCKET_SECRET_NAME'
sqs_queue_secret = 'YOUR_SQS_QUEUE_SECRET_NAME'

bot = ObjectDetectionBot(telegram_token_secret, telegram_chat_url, s3_bucket_secret, sqs_queue_secret)
