import unittest
from unittest.mock import patch, MagicMock
from polybot_script import ObjectDetectionBot
from yolo5_script import download_from_s3, upload_to_s3, store_in_dynamodb, send_results_to_polybot

class TestIntegrationPolybotYolo5(unittest.TestCase):
    @patch('polybot_script.boto3.client')
    @patch('yolo5_script.boto3.client')
    def test_integration_polybot_yolo5(self, mock_polybot_boto_client, mock_yolo5_boto_client):
        # Set up mock S3 clients for both Polybot and Yolo5
        mock_polybot_s3_client = MagicMock()
        mock_polybot_boto_client.return_value = mock_polybot_s3_client

        mock_yolo5_s3_client = MagicMock()
        mock_yolo5_boto_client.return_value = mock_yolo5_s3_client

        # Mock S3 download_file to simulate downloading from S3 for Yolo5
        with patch.object(mock_yolo5_s3_client, 'download_file') as mock_yolo5_download_file:
            mock_yolo5_download_file.return_value = None

            # Mock S3 upload_file to simulate uploading to S3 for Polybot
            with patch.object(mock_polybot_s3_client, 'upload_file') as mock_polybot_upload_file:
                mock_polybot_upload_file.return_value = None

                # Mock DynamoDB put_item to simulate storing an item for Yolo5
                with patch('yolo5_script.boto3.resource') as mock_yolo5_boto_resource:
                    mock_yolo5_dynamodb_resource = MagicMock()
                    mock_yolo5_boto_resource.return_value = mock_yolo5_dynamodb_resource

                    with patch.object(mock_yolo5_dynamodb_resource.Table('ezdehar-table'), 'put_item') as mock_yolo5_put_item:
                        mock_yolo5_put_item.return_value = None

                        # Mock SQS send_message to simulate sending a message to SQS for Polybot
                        with patch('polybot_script.boto3.client') as mock_polybot_sqs_client:
                            mock_polybot_sqs_client.return_value = MagicMock()

                            # Create instances of Polybot and Yolo5
                            polybot = ObjectDetectionBot()
                            # Yolo5-related code (consuming SQS, etc.) would usually be in a separate module

                            # Run the Polybot function
                            polybot.handle_message({'chat': {'id': '123'}, 'text': 'test'})

                            # Assert that download_file is called for Yolo5
                            mock_yolo5_download_file.assert_called_once()

                            # Assert that upload_file is called for Polybot
                            mock_polybot_upload_file.assert_called_once()

                            # Assert that put_item is called for Yolo5
                            mock_yolo5_put_item.assert_called_once()

                            # Assert that send_message is called for Polybot
                            mock_polybot_sqs_client.return_value.send_message.assert_called_once()

if __name__ == '__main__':
    unittest.main()
