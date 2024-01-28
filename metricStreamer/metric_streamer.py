import json

import boto3
import time

sqs_client = boto3.resource('sqs', region_name='eu-west-3')
asg_client = boto3.client('autoscaling', region_name='eu-west-3')
secrets_manager = boto3.client('secretsmanager', region_name='eu-west-3')

def get_secret(secret_name):
    try:
        secret_response = secrets_manager.get_secret_value(SecretId=secret_name)
        return json.loads(secret_response['SecretString'])
    except Exception as e:
        print(f"Error retrieving secret '{secret_name}': {e}")
        raise

secrets = get_secret('ezdehar-secret')
AUTOSCALING_GROUP_NAME = 'ezdehar-yolo5-asg'
QUEUE_NAME = secrets['SQS_QUEUE_NAME']
NAMESPACE = 'Ezdehar-Metrics'
METRIC_NAME = 'BacklogPerInstance'

while True:
    try:
        # Get the number of messages in the SQS queue
        queue = sqs_client.get_queue_by_name(QueueName=QUEUE_NAME)
        msgs_in_queue = int(queue.attributes.get('ApproximateNumberOfMessages'))

        # Get the Auto Scaling Group information
        asg_groups = asg_client.describe_auto_scaling_groups(AutoScalingGroupNames=[AUTOSCALING_GROUP_NAME])['AutoScalingGroups']

        if not asg_groups:
            raise RuntimeError('Autoscaling group not found')
        else:
            asg_size = asg_groups[0]['DesiredCapacity']

        if asg_size == 0:
            print('Auto Scaling Group has a desired capacity of zero. Skipping calculation.')
            time.sleep(30)
            continue

        # Calculate BacklogPerInstance
        backlog_per_instance = msgs_in_queue / asg_size

        # Print for testing (you can remove this in production)
        print(f'BacklogPerInstance: {backlog_per_instance}')

        # TODO: Send BacklogPerInstance to CloudWatch
        cloudwatch = boto3.client('cloudwatch', region_name='eu-west-3')
        cloudwatch.put_metric_data(
            Namespace=NAMESPACE,
            MetricData=[
                {
                    'MetricName': METRIC_NAME,
                    'Value': backlog_per_instance,
                    'Unit': 'Count',
                    'Dimensions': [
                        {
                            'Name': 'AutoScalingGroupName',
                            'Value': AUTOSCALING_GROUP_NAME
                        }
                    ]
                }
            ]
        )

    except Exception as e:
        print(f'Error: {e}')

    finally:
        # Sleep for 30 seconds before the next iteration
        time.sleep(30)
