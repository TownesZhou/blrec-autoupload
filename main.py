"""
    Listen to the BLREC Webhook and upload the recoding video files to TMPLINK.
"""
from cmath import log
import os
import subprocess
from threading import Thread
import toml
import tempfile
import logging
from flask import Flask, request, Response

app = Flask(__name__)


# File uploading to be initiated in another thread after returning 200 in the respond() method.
def upload_video(video_path, danmu_path, token, mrid, post_url):
    # Use subprocess to call the CLI command.
    # The command with mrid is: curl -k -F "file=@{file path}" -F "token={token}" -F "model=2" -F "mrid={mrid}" -X POST "{post_url}"
    # The command without mrid is: curl -k -F "file=@{file path}" -F "token={token}" -F "model=2" -X POST "{post_url}"
    # Use a temporary file to redirect curl's output so the progress bar can be seen in the terminal.
    with tempfile.NamedTemporaryFile() as f:
        if mrid != "":
            cmd = f"curl -k -F \"file=@{video_path}\" -F \"token={token}\" -F \"model=2\" -F \"mrid={mrid}\" \-X POST \"{post_url}\" > {f.name}"
        else:
            cmd = f"curl -k -F \"file=@{video_path}\" -F \"token={token}\" -F \"model=2\" -X POST \"{post_url}\" > {f.name}"
        logging.info(f"Uploading the video file: {os.path.basename(video_path)}")
        logging.debug(f"Executing command: {cmd}")
        
        complete_status = subprocess.call(cmd, shell=True)
        if complete_status == 0:
            logging.info("Successfully uploaded the video file.")
            logging.info(f"Response from the TMP server: \n{f.read().decode('utf-8')}")
        else:
            logging.error(f"Upload process failed with return code: {complete_status}")
            logging.error(f"Piped Output: \n{f.read().decode('utf-8')}")

        
    # If there is a Danmu file, upload it as well.
    with tempfile.NamedTemporaryFile() as f:
        if os.path.isfile(danmu_path):
            if mrid != "":
                cmd = f"curl -k -F \"file=@{danmu_path}\" -F \"token={token}\" -F \"model=2\" -F \"mrid={mrid}\" -X POST \"{post_url}\" > {f.name}"
            else:
                cmd = f"curl -k -F \"file=@{danmu_path}\" -F \"token={token}\" -F \"model=2\" -X POST \"{post_url}\" > {f.name}"
            logging.info(f"Danmu file found. Uploading the Danmu file: {os.path.basename(danmu_path)}.")
            logging.debug(f"Executing command: {cmd}")
            
            complete_status = subprocess.call(cmd, shell=True)
            if complete_status == 0:
                logging.info("Successfully uploaded the Danmu file.")
                logging.info(f"Response from the TMP server: \n{f.read().decode('utf-8')}")
            else:
                logging.error(f"Upload process failed with return code: {complete_status}")
                logging.error(f"Piped Output: \n{f.read().decode('utf-8')}")
            

# The method that listens to POST webhook requests. 
@app.route('/blrec-autoupload', methods=['POST'])
def respond():
    """
        Respond to the BLREC Webhook.
    """
    if request.method != 'POST':
        return

    # Sanity check: the request should be a JSON object.
    logging.info("Received a new request.")
    if not request.is_json:
        logging.error("The request is not a JSON object.")
        return Response(status=400)
    # Check that the request has all the required fields.
    if not all(key in request.json for key in ['id', 'date', 'type', 'data']):
        logging.error(f"The request is missing these required fields: \
            {[key for key in ['id', 'date', 'type', 'data'] if key not in request.json]}")
        return Response(status=400)
    
    # Get metadata
    id = request.json['id']
    date = request.json['date']
    type = request.json['type']
    data = request.json['data']
    logging.info(f"Request type is: {type}")
    logging.debug(f"\tID: {id}")
    logging.debug(f"\tDATE: {date}")
    logging.debug(f"\tTYPE: {type}")
    # Only proceed if the event type is VideoPostprocessingCompletedEvent.
    if type != 'VideoPostprocessingCompletedEvent':
        logging.info(f"The event type is not VideoPostprocessingCompletedEvent. Skipping.")
        return Response(status=400)
    
    # Get room_id and path of the video file.
    room_id = data['room_id']
    path = data['path']
    logging.debug(f"\tROOM_ID: {room_id}")
    logging.debug(f"\tPATH: {path}")

    # Get the file name and its dir
    filename = os.path.basename(path)
    dir = os.path.dirname(path)
    # Sanity check: the file should be a mp4 file.
    if not filename.endswith('.mp4'):
        logging.error(f"The file is not a mp4 file. Skipping.")
        return Response(status=400)
    # Sanity check: the file should indeed exist.
    if not os.path.isfile(path):
        logging.error(f"The file does not exist. Skipping.")
        return Response(status=400)

    # Check if there is a Danmu file with the same name and ends with .xml.
    danmu_path = os.path.join(dir, filename[:-4] + '.xml')
    # If there is no Danmu file, print an info and upload only the video file.
    if not os.path.isfile(danmu_path):
        logging.info(f"No Danmu file found. Uploading only the video file.")
    
    # Upload files to TMPLINK using CLI command.
    # Get room config
    room_config = app.config['ROOM_CONFIG']
    logging.debug(f"The config for room {room_id} is: {room_config}")

    # Check that the room_id is one of the rooms in the config. 
    if room_id not in room_config:
        logging.error(f"The room_id {room_id} is not in the config. Skipping.")
        return Response(status=400)
    
    # Get token, mrid, API post url from the room config
    token = room_config[room_id]['token']
    mrid = room_config[room_id]['mrid']
    post_url = room_config[room_id]['post_url']

    # Everything is OK. Respond with 200 OK and start uploading.
    logging.info(f"Everything is OK. Starting uploading.")

    # Upload the video file with another thread.
    thread = Thread(target=upload_video, args=(path, danmu_path, token, mrid, post_url))
    thread.start()
    
    return Response(status=200)


if __name__ == '__main__':
    # Read config file.
    config_path = os.path.join(os.path.dirname(__file__), 'config.toml')
    config = toml.load(config_path)
    # Parse config for each room. Room-specific config overwrites the global config.
    room_config = {}
    for key, table in config.items():
        if "room_" in key:
            room_id = int(key.split("_")[1])
            room_config[room_id] = {**config['global'], **table}  # Room-specific config overwrites the global ones.
    # Save the room config in the Flask app's config dict so we can access it in the respond() method.
    app.config['ROOM_CONFIG'] = room_config

    # Config logging.
    log_level_numeric = getattr(logging, config['app']['log_level'], "INFO")  # Defalt to INFO is not found. 
    logging.basicConfig(
        level=log_level_numeric,  # Set logging level.
        format='[%(asctime)s] [%(levelname)s] %(message)s'  # Display time and level.
    )
    # Start server.
    app.run()
