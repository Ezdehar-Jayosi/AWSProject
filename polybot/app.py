import flask
from flask import request
import os
from bot import ObjectDetectionBot
import boto3

app = flask.Flask(__name__)

# Load TELEGRAM_TOKEN value from Secret Manager
SECRET_MANAGER_SECRET_NAME = 'your_secret_manager_secret_name'
SECRET_MANAGER_REGION = 'your_secret_manager_region'

secrets_manager = boto3.client('secretsmanager', region_name=SECRET_MANAGER_REGION)
secret_response = secrets_manager.get_secret_value(SecretId=SECRET_MANAGER_SECRET_NAME)
TELEGRAM_TOKEN = secret_response['SecretString'].strip()

TELEGRAM_APP_URL = os.environ['TELEGRAM_APP_URL']

# TODO: Fill in your DynamoDB configuration
DYNAMODB_REGION = 'your_dynamodb_region'
DYNAMODB_TABLE_NAME = 'your_dynamodb_table_name'
dynamodb = boto3.resource('dynamodb', region_name=DYNAMODB_REGION)
dynamodb_table = dynamodb.Table(DYNAMODB_TABLE_NAME)


@app.route('/', methods=['GET'])
def index():
    return 'Ok'


@app.route(f'/{TELEGRAM_TOKEN}/', methods=['POST'])
def webhook():
    req = request.get_json()
    bot.handle_message(req['message'])
    return 'Ok'


@app.route(f'/results/', methods=['GET'])
def results():
    prediction_id = request.args.get('predictionId')

    # Retrieve results from DynamoDB
    response = dynamodb_table.get_item(Key={'prediction_id': prediction_id})
    result_item = response.get('Item', {})

    # Extract chat_id and text_results from the DynamoDB result_item
    chat_id = result_item.get('chat_id', 'default_chat_id')
    text_results = result_item.get('text_results', 'default_text_results')

    bot.send_text(chat_id, text_results)
    return 'Ok'


@app.route(f'/loadTest/', methods=['POST'])
def load_test():
    req = request.get_json()
    bot.handle_message(req['message'])
    return 'Ok'


if __name__ == "__main__":
    bot = ObjectDetectionBot(TELEGRAM_TOKEN, TELEGRAM_APP_URL)
    app.run(host='0.0.0.0', port=8443)
