import http.server
import socketserver
import json
import time
import os
import glob
import subprocess
import sys
import logging
from logging import StreamHandler
import signal
import re
from threading import Thread
import signal

# New global variable to track request processing state
is_request_being_processed = False

PORT = 8004
session_directory = '.'
session_file_pattern = '*_session.txt'
last_known_modification = 0
last_processed_line = 0

class CustomLogHandler(StreamHandler):
    def __init__(self):
        super().__init__()
        self.last_log = None
        self.animation = "|/-\\"
        self.animation_index = 0
        self.last_msg_was_repeated = False

    def emit(self, record):
        try:
            msg = self.format(record)
            if self.last_log != msg:
                if self.last_msg_was_repeated:
                    self.stream.write("\n")  # Finish the animation line if the last message was repeated
                    self.last_msg_was_repeated = False
                self.stream.write(msg + "\n")
                self.flush()
            else:
                if not self.last_msg_was_repeated:
                    self.stream.write("\r" + self.animation[self.animation_index % len(self.animation)] + " " + msg)
                    self.last_msg_was_repeated = True
                else:
                    self.stream.write("\r" + self.animation[self.animation_index % len(self.animation)] + " " + msg)
                self.flush()
                self.animation_index += 1
            self.last_log = msg
        except Exception:
            self.handleError(record)

# Replace the default logging handler with the custom one
logging.basicConfig(level=logging.INFO, handlers=[CustomLogHandler()])

httpd = None

def find_latest_session_file():
    """
    Finds the most recently updated session file matching the session_file_pattern.
    Returns the path to the latest file or None if no file is found.
    """
    session_files = glob.glob(os.path.join(session_directory, session_file_pattern))
    if not session_files:
        return None
    latest_file = max(session_files, key=os.path.getmtime)
    return latest_file

class RequestHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        global last_processed_line, is_request_being_processed
        is_request_being_processed = True  # Indicate that a request is being processed
        try:
            new_messages = get_new_messages()
            self.send_response(200)
            self.send_header('Content-type', 'text/plain')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Access-Control-Allow-Methods', 'GET')
            self.send_header('Access-Control-Allow-Headers', 'X-Requested-With, Content-Type')
            self.end_headers()
            self.wfile.write(json.dumps(new_messages).encode('utf-8'))
        finally:
            is_request_being_processed = False  # Reset the state after handling the request

def remove_urls_and_markdown(text):
    """
    Removes URLs and Markdown characters from the given text.
    """
    # Remove URLs
    text = re.sub(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', '', text)
    # Remove Markdown bold and italic syntax
    text = re.sub(r'\*\*|\*|__|_', '', text)
    # Remove Markdown links [text](url)
    text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)
    return text

def get_new_messages():
    global last_known_modification, last_processed_line
    new_messages = []
    session_file_path = find_latest_session_file()
    if session_file_path is None:
        logging.info("No session file found. Please ensure the files are present.")
        return new_messages

    modification_time = os.path.getmtime(session_file_path)
    if modification_time != last_known_modification:
        logging.info(f"Session file {session_file_path} updated. Parsing for new messages...")
        last_known_modification = modification_time
        with open(session_file_path, 'r') as file:
            lines = file.readlines()
            message_content = ""
            for i, line in enumerate(lines[last_processed_line:], start=last_processed_line):
                if "Assistant:" in line:
                    # Start of a new message, add the previous one to the list
                    if message_content:
                        # Process the message to remove URLs and Markdown before adding
                        processed_message = remove_urls_and_markdown(message_content.strip())
                        new_messages.append(processed_message)
                        message_content = ""
                    # Remove "Assistant:" and leading/trailing whitespace, then add to the current message content
                    message_content += line.split("Assistant:", 1)[1].strip() + " "
                elif message_content:
                    # Continuation of the current message, append line content
                    message_content += line.strip() + " "
                last_processed_line = i + 1
            # Add the last message if there is one
            if message_content:
                # Process the last message to remove URLs and Markdown before adding
                processed_message = remove_urls_and_markdown(message_content.strip())
                new_messages.append(processed_message)
    return new_messages

def start_server():
    global httpd  # Make httpd modifiable
    try:
        httpd = socketserver.TCPServer(("", PORT), RequestHandler)
        print(f"Serving at port {PORT}")
        httpd.serve_forever()
    except OSError as e:
        if e.errno == 98:  # Port already in use
            logging.error(f"Port {PORT} is already in use. Please choose a different port.")
        else:
            raise  # Re-raise the exception if it's not a port in use error
    except Exception as general_error:
        logging.error(f"Failed to start the server on port {PORT}: {general_error}")
        sys.exit(1)

def signal_handler(signum, frame):
    """Gracefully shuts down the server."""
    print('Shutting down server...')
    if httpd:
        httpd.shutdown()
        httpd.server_close()
    sys.exit(0)

if __name__ == "__main__":
    # Modify the loading animation function to work with the new logging mechanism
    def loading_animation():
        global is_request_being_processed
        while True:
            if is_request_being_processed:
                time.sleep(0.1)  # Just keep the thread alive
            else:
                print("\r", end="")
    # Start the loading animation in a separate thread
    animation_thread = Thread(target=loading_animation)
    animation_thread.daemon = True
    animation_thread.start()

    update_thread = Thread(target=lambda: None)
    update_thread.daemon = True
    update_thread.start()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    start_server()