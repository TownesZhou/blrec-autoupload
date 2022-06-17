"""
    Testing the main script by sending a mock Webhook request.
"""
import requests
import json


# URL of the target webhook
webhook_url = 'http://localhost:5000/blrec-autoupload'

# Mock to be send
data = {
  "id": "a8a19d06-8cdd-11ec-9d5b-d8bbc192d668",
  "date": "2022-02-13 23:00:18.646777+08:00",
  "type": "VideoPostprocessingCompletedEvent",
  "data": {
    "room_id": 962983,
    "path": "/home/jincheng/projects/blrec-autoupload/test/test_data/blive_962983_2022-06-17-045810.mp4"
  }
}


if __name__ == '__main__':
    # Send the mock request
    requests.post(webhook_url, data=json.dumps(data), headers={'Content-Type': 'application/json'})
    print("Mock request sent.")

