import requests
from requests.exceptions import RequestException, Timeout
from tkinter import scrolledtext, messagebox, font, simpledialog
import customtkinter
import customtkinter as ctk
from customtkinter import CTkImage 
import tkinter as tk
from tkinter import PhotoImage
from PIL import Image, ImageTk
import json
import time
import openai
import threading
import sys
import subprocess
import traceback
import webbrowser
import os
import re
import configparser
import sys
import random
import subprocess
import webbrowser
import atexit
import socketserver
import signal
import glob
# Additional imports specific to Google Sheets API and OAuth
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from google.cloud import texttospeech

from search import search_web, scrape_content, save_content_to_file

from http.server import HTTPServer, BaseHTTPRequestHandler, SimpleHTTPRequestHandler
import socketserver
import urllib.parse
import urllib.request
from urllib.parse import urlparse, parse_qs
from pathlib import Path
import uuid
import logging
logging.basicConfig(stream=sys.stdout, level=logging.INFO,  # set to logging.DEBUG for verbose output
        format="[%(asctime)s] %(message)s", datefmt="%m/%d/%Y %I:%M:%S %p %Z")
logger = logging.getLogger(__name__)

def generate_state_parameter():
    return str(uuid.uuid4())

def open_basic_html():
    # Path to your basic.html file
    html_file_path = os.path.abspath("cognitive-services-speech-sdk/samples/js/browser/avatar/basic.html")
    # Use the file:// scheme to open a local file
    url = 'file://' + html_file_path
    webbrowser.open(url)

# Global variable to keep track of the subprocess
cachecheck_process = None

def terminate_cachecheck_process():
    global cachecheck_process
    if cachecheck_process is not None:
        logging.info("Terminating cachecheck.py script.")
        # Send SIGTERM signal to ensure graceful shutdown
        os.killpg(os.getpgid(cachecheck_process.pid), signal.SIGTERM)
        cachecheck_process.wait()  # Wait for the process to terminate
        logging.info("cachecheck.py script terminated.")


def start_cachecheck_script():
    global cachecheck_process
    try:
        # Introduce a 10-second delay
        logging.info("Waiting 10 seconds before starting cachecheck.py script...")
        time.sleep(10)

        script_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'cachecheck.py')
        cachecheck_process = subprocess.Popen(["python3", script_path], start_new_session=True)
        logging.info("cachecheck.py script started successfully.")
        
        # Register the cleanup function with atexit
        atexit.register(terminate_cachecheck_process)
    except Exception as e:
        logging.error(f"Failed to start cachecheck.py script: {e}")

# Call the function to start the cachecheck.py script
start_cachecheck_script()

def cleanup_thread_files():
    """
    Deletes thread-specific text files generated during the application's runtime.
    """
    logging.info("Cleaning up thread files...")
    try:
        # Assuming thread files follow the pattern "thread_id_session.txt"
        for filename in glob.glob("*_session.txt"):
            os.remove(filename)
            logging.info(f"Deleted file: {filename}")
    except Exception as e:
        logging.error(f"Error during cleanup: {e}")

# Register the cleanup function to be called upon program exit
atexit.register(cleanup_thread_files)


#Start of Assistants API Functions
def get_openai_api_key():
    config = configparser.ConfigParser()
    directory = os.path.dirname(os.path.realpath(__file__))
    config_file = os.path.join(directory, 'config.ini')
    if not os.path.exists(config_file):
        os.makedirs(os.path.dirname(config_file), exist_ok=True)
        # Use Tkinter dialog to prompt for the OpenAI API key
        root = tk.Tk()
        root.withdraw()  # Hide the main window
        openai_api_key = simpledialog.askstring("OpenAI API Key", "Enter your OpenAI API key:", parent=root)
        if openai_api_key:
            config['DEFAULT'] = {'OpenAI_API_Key': openai_api_key}
            with open(config_file, 'w') as configfile:
                config.write(configfile)
        root.destroy()
    else:
        config.read(config_file)
        openai_api_key = config['DEFAULT']['OpenAI_API_Key']
    return openai_api_key


OPENAI_API_KEY = get_openai_api_key()
ASSISTANT_ID = "asst_E8fpEjXc0zKkyjWjGq3UR9PV"
thread_id = None
# Initialize the global variable to track the last displayed message ID

# Add a global flag
is_filtering_saving_messages = False
# Global flag to control polling
last_displayed_message_id = None
displayed_message_ids = set()  # Keep track of displayed message IDs
# Simple cache for run statuses to avoid losing context
run_status_cache = {}
global_assistant_file_id = None
# Hardcoded Spreadsheet IDs
SPREADSHEET_ID = "1y2nOP0JCHlPqZNS9B2WD8tBPC_WuRFA277nAA_CJa3s"  # ID for the synopsis ai in healthcare sheet
SPREADSHEET_ID1 = "1ii2iXJ752nl9RcTmBHv7tlXZ6LrC3qhcjrkk_5dB_Ik"  # ID for the append values to sheet function for the test results

# Update for Google Sheets and Google Docs API
SCOPES = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/documents"]
API_SERVICE_NAME_SHEETS = 'sheets'
API_SERVICE_NAME_DOCS = 'docs'
API_VERSION_SHEETS = 'v4'
API_VERSION_DOCS = 'v1'
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

directory = os.path.dirname(os.path.realpath(__file__))
CLIENT_SECRETS_FILE = os.path.join(directory, 'client_secret.json')
# Global variable to keep track of the server instance
httpd_server = None

def cleanup_server():
    global httpd_server
    if httpd_server:
        print("Shutting down the server...")
        httpd_server.shutdown()
        httpd_server.server_close()
        httpd_server = None
        print("Server shut down successfully.")

# Define OAuthHandler outside to ensure it's accessible
class OAuthHandler(SimpleHTTPRequestHandler):
    def do_GET(self):
        global flow  # Ensure flow is accessible here
        # Parse the authorization response URL
        self.send_response(200)
        self.end_headers()
        query = urlparse(self.path).query
        auth_response = dict(parse_qs(query))
        flow.fetch_token(authorization_response=self.path)

        # Store the credentials
        creds = flow.credentials
        save_credentials(creds)

        self.wfile.write(b'Authorization successful. You may close this window.')

def attempt_start_server(port):
    global httpd_server
    try:
        httpd_server = socketserver.TCPServer(("", port), OAuthHandler)
        print(f"Server started on port {port}")
        httpd_server.serve_forever()
        return True
    except OSError as e:
        print(f"Failed to start server on port {port}: {e}")
        return False

def start_oauth_and_server():
    global flow  # Declare flow as global to ensure it's accessible in OAuthHandler
    # Initialize OAuth flow with client secrets and scopes
    flow = Flow.from_client_secrets_file(CLIENT_SECRETS_FILE, SCOPES)
    flow.redirect_uri = 'http://localhost:8081/sheets-callback'

    # Open the authorization URL in the user's browser
    auth_url, _ = flow.authorization_url(prompt='consent')
    webbrowser.open(auth_url)
    atexit.register(cleanup_server)

    # Attempt to start the server on a range of ports if the default is unavailable
    port_range = range(8081, 8100)
    server_started = False
    for port in port_range:
        if attempt_start_server(port):
            server_started = True
            break

    if not server_started:
        original_port = 8081
        try:
            subprocess.check_call(['fuser', '-k', f'{original_port}/tcp'])
            print(f"Terminated server on port {original_port}. Attempting to restart.")
            if attempt_start_server(original_port):
                server_started = True
        except subprocess.CalledProcessError as e:
            print(f"Failed to terminate and restart server on port {original_port}: {e}")

    if not server_started:
        raise Exception("Failed to start the OAuth server on any port. Please check your system's port availability.")

def signal_handler(signum, frame):
    print("Signal received, cleaning up...")
    cleanup_server()
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

# Function to save Google Sheets API credentials to a file
def save_credentials(credentials):
    directory = os.path.dirname(os.path.realpath(__file__))
    credentials_file = os.path.join(directory, 'credentials.json')
    os.makedirs(os.path.dirname(credentials_file), exist_ok=True)
    with open(credentials_file, 'w') as file:
        file.write(credentials.to_json())
    os.chmod(credentials_file, 0o600)

# Update the google_authenticate function
def google_authenticate():
    directory = os.path.dirname(os.path.realpath(__file__))
    credentials_file = os.path.join(directory, 'credentials.json')
    with open(credentials_file, 'r') as file:
        credentials_json = file.read()
    credentials = Credentials.from_authorized_user_info(json.loads(credentials_json), SCOPES)

    # Build the service object for the Sheets API
    service_sheets = build(API_SERVICE_NAME_SHEETS, API_VERSION_SHEETS, credentials=credentials)
    # Build the service object for the Docs API
    service_docs = build(API_SERVICE_NAME_DOCS, API_VERSION_DOCS, credentials=credentials)

    return service_sheets, service_docs

def append_to_sheet(spreadsheet_id1, user_name, formal_response, summative_assessment):
    logging.info(f"Starting authentication process for Google Sheets API.")
    service_sheets, _ = google_authenticate()
    logging.info(f"Authentication successful. Preparing to append data to the sheet.")

    values = [
        [user_name, formal_response, summative_assessment]
    ]
    body = {
        'values': values
    }
    range_ = "A2:C"  # Appends starting from the second row

    logging.info(f"Appending data to spreadsheet ID: {spreadsheet_id1}. Range: {range_}. Values: {values}")
    try:
        result = service_sheets.spreadsheets().values().append(
            spreadsheetId=spreadsheet_id1,
            range=range_,
            valueInputOption="RAW",
            insertDataOption="INSERT_ROWS",
            body=body
        ).execute()
        logging.info(f"Data append successful. Result: {result}")
    except Exception as e:
        logging.error(f"Failed to append data to the sheet. Error: {str(e)}")
        raise e

    return result

def retrieve_rows_data(spreadsheet_id, rows):
    logging.info(f"Starting retrieval of rows data from spreadsheet ID: {spreadsheet_id}")
    try:
        service_sheets, _ = google_authenticate()  # Assuming this returns the Sheets service
        logging.info("Google Sheets service authenticated successfully.")
        values = []
        for row in rows:
            range_ = f"A{row}:A{row}"
            logging.debug(f"Fetching data for range: {range_}")
            result = service_sheets.spreadsheets().values().get(
                spreadsheetId=spreadsheet_id, range=range_).execute()
            row_values = result.get('values', [])
            if row_values:
                logging.debug(f"Data retrieved for row {row}: {row_values[0]}")
                values.append(row_values[0])  # Assume each range returns a single row's values
            else:
                logging.debug(f"No data found for row {row}.")
        
        if values:
            logging.info(f"Data retrieval successful. Rows fetched: {len(values)}")
            return True, values
        else:
            logging.warning("No data retrieved from Google Sheets.")
            return False, "No data retrieved from Google Sheets."
    except Exception as e:
        error_message = f"Failed to retrieve data: {str(e)}"
        logging.error(error_message)
        return False, error_message

def retrieve_doc_contents(document_id):
    """
    Retrieves the contents of a Google Doc.

    Parameters:
    - document_id: ID of the Google Doc.

    Returns:
    - A tuple with a boolean indicating success or failure, and the text contents of the Google Doc or an error message if the operation fails.
    """
    logging.info(f"Initiating retrieval of document contents for document ID: {document_id}")
    try:
        _, service_docs = google_authenticate()  # Corrected to get the Docs service correctly
        logging.debug("Google Docs service authenticated successfully.")
        document = service_docs.documents().get(documentId=document_id).execute()
        logging.debug(f"Document retrieved successfully. Document ID: {document_id[:10]}...")  # Truncate document ID for logging
        doc_content = document.get('body').get('content')
        text_content = ""
        for element in doc_content:
            if 'paragraph' in element:
                for paragraphElement in element.get('paragraph').get('elements'):
                    if 'textRun' in paragraphElement:
                        text_content += paragraphElement.get('textRun').get('content')
        
        if text_content:
            logging.info(f"Document contents retrieved successfully for document ID: {document_id[:10]}...")  # Truncate document ID for logging
            return True, text_content.strip()  # Strip to remove any leading/trailing whitespace
        else:
            logging.warning(f"No text found in the document with ID: {document_id}")
            return False, "No text found in the document."

    except Exception as e:
        error_message = f"Failed to retrieve document contents for document ID: {document_id}. Error: {str(e)[:100]}"  # Truncate error message
        logging.error(error_message)
        return False, error_message


def filter_and_save_messages(thread_id):
    logging.info(f"Starting to filter and save messages for thread_id: {thread_id}")
    messages = load_messages_from_cache(thread_id)
    if messages:
        logging.info("Messages loaded from cache successfully.")
        filtered_content = ""
        for message in messages.get("data", []):
            role = "User" if message["role"] == "user" else "Assistant"
            # Concatenate all text parts of the message content
            content = "".join(part["text"]["value"] for part in message["content"] if part["type"] == "text")
            line = f"{role}: {content}\n\n"
            if not line_in_file(f"{thread_id}_session.txt", line):
                filtered_content += line
        
        # Append the filtered content to a text file if there's new content
        if filtered_content:
            filename = f"{thread_id}_session.txt"
            with open(filename, "a") as file:
                file.write(filtered_content)
            logging.info(f"Filtered content appended successfully to {filename}.")
            return True, filename
    else:
        logging.warning("No messages found in cache.")
        return False, "No messages found."

def line_in_file(filename, line):
    """Check if a specific line is already in a file."""
    try:
        with open(filename, "r") as file:
            if line in file.read():
                return True
    except FileNotFoundError:
        pass
    return False

def update_spreadsheet_with_text(spreadsheet_id1, text_file_path):
    logging.info(f"Starting to update spreadsheet: {spreadsheet_id1} with text file: {text_file_path}")
    service_sheets, _ = google_authenticate()
    # Read the text file content
    with open(text_file_path, 'r') as file:
        text_content = file.read()
    
    # Find the last edited row in column D
    last_row = find_last_edited_row(service_sheets, 'Sheet1')  # Make sure 'Sheet1' matches your actual sheet name
    logging.info(f"Last edited row found in column D: {last_row}")
    
    # Check if the last_row is 1, which means column D is empty, start from row 2
    if last_row == 1:
        start_row = 2
    else:
        # If there's content in column D starting from row 2, append to the next available row
        start_row = last_row
    
    # Define the range to update based on the last edited row in column D
    range_ = f"Sheet1!D{start_row}"  # Adjust 'Sheet1' if your sheet name is different
    
    body = {
        'values': [[text_content]]
    }
    
    # Update the spreadsheet
    try:
        result = service_sheets.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id1,
            range=range_,
            valueInputOption="RAW",
            body=body
        ).execute()
        logging.info(f"Spreadsheet updated successfully in column D, row {start_row}. Result: {result}")
    except Exception as e:
        logging.error(f"Failed to update the spreadsheet. Error: {e}")
        raise e
    
    return result

def submit_session():
    logging.info("Starting to submit session.")
    global thread_id  # Ensure thread_id is declared as global if it's not already
    if thread_id:
        success, text_file_path = filter_and_save_messages(thread_id)
        if success:
            logging.info(f"Messages filtered and saved successfully. File path: {text_file_path}")
            update_spreadsheet_with_text(SPREADSHEET_ID1, text_file_path)  # Using the correct global variable
            print("Session submitted successfully.")
        else:
            logging.warning("Failed to filter and save messages.")
            print("Failed to submit session.")
    else:
        logging.error("Thread ID is not set. Please start a session first.")
        print("Thread ID is not set. Please start a session first.")

def find_last_edited_row(service_sheets, sheet_name='Sheet1'):
    logging.info(f"Finding last edited row in spreadsheet: {SPREADSHEET_ID1}, sheet: {sheet_name}")
    range_name = f"{sheet_name}!D:D"  # Adjusted to check column D
    result = service_sheets.spreadsheets().values().get(
        spreadsheetId=SPREADSHEET_ID1,
        range=range_name
    ).execute()
    values = result.get('values', [])
    
    if not values:
        logging.info("No data found in the specified range. Starting from the first row.")
        return 1  # Return 1 to start from the first row if the column is empty
    else:
        logging.info(f"Last row with data found: {len(values)}")
        return len(values) + 1  # Return the next available row



def upload_file(filepath, purpose="assistants"):
    url = "https://api.openai.com/v1/files"
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}"
    }
    with open(filepath, "rb") as file:
        files = {
            "file": file
        }
        data = {
            "purpose": purpose
        }
        response = requests.post(url, headers=headers, files=files, data=data)
    if response.status_code == 200:
        return response.json()["id"]  # Return the file ID
    else:
        raise Exception(f"File upload failed: {response.text}")

def create_assistant_file(filepath, assistant_id):
    # Upload the file to get a file ID
    file_id = upload_file(filepath)
    url = f"https://api.openai.com/v1/assistants/{assistant_id}/files"
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json",
        "OpenAI-Beta": "assistants=v1"
    }
    data = {"file_id": file_id}
    response = requests.post(url, headers=headers, json=data)
    if response.status_code == 200:
        print("Assistant file created successfully.")
        return file_id  # Return the original file ID, as it's used to reference the file
    else:
        raise Exception(f"Failed to create assistant file: {response.text}")
import logging

def delete_assistant_file(assistant_id, file_id):
    logging.info(f"Attempting to delete assistant file with ID: {file_id}")
    url = f"https://api.openai.com/v1/assistants/{assistant_id}/files/{file_id}"
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "OpenAI-Beta": "assistants=v1"
    }
    response = requests.delete(url, headers=headers)
    if response.status_code == 200:
        logging.info("Assistant file deleted successfully.")
        print("Assistant file deleted successfully.")
    else:
        logging.error(f"Failed to delete assistant file: {response.text}")
        print(f"Failed to delete assistant file: {response.text}")


def delete_file(file_id):
    logging.info(f"Attempting to delete file with ID: {file_id}")
    url = f"https://api.openai.com/v1/files/{file_id}"
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
    }
    response = requests.delete(url, headers=headers)
    if response.status_code == 200:
        logging.info("File deleted successfully.")
        print("File deleted successfully.")
    else:
        logging.error(f"Failed to delete file: {response.text}")
        print(f"Failed to delete file: {response.text}")

def initiate_search_and_upload():
    global global_assistant_file_id 
    # Step 1: Perform the search and save content to a file
    query = "latest developments in healthcare and ai"
    urls = search_web(query)
    content = scrape_content(urls)
    filename = "the_latest_in_ai_healthcare.txt"
    save_content_to_file(content, filename)
    
    # Step 2: Upload the file and get the file ID
    try:
        assistant_file_id = create_assistant_file(filename, ASSISTANT_ID)
        global_assistant_file_id = assistant_file_id  # Store the file ID globally after attaching it to an assistant
        update_status_message("Assistant file created successfully. File ID: " + assistant_file_id)
        
        # Step 3: Optionally, you can now pass this file_id to create_thread or any other function that needs it
        # For example, if create_thread is modified to accept file_ids:
        create_thread(file_ids=[assistant_file_id])
    except Exception as e:
        update_status_message(f"Failed to upload file: {str(e)}")

def delete_thread(thread_id):
    logging.info(f"Attempting to delete thread with ID: {thread_id}")
    url = f"https://api.openai.com/v1/threads/{thread_id}"
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "OpenAI-Beta": "assistants=v1",
        "Content-Type": "application/json"
    }
    response = requests.delete(url, headers=headers)
    if response.status_code == 200:
        logging.info("Thread deleted successfully.")
        print("Thread deleted successfully.")
    else:
        logging.error(f"Failed to delete thread: {response.text}")
        print(f"Failed to delete thread: {response.text}")

def cleanup():
    global global_assistant_file_id, thread_id  # Ensure thread_id is declared as global if it's not already
    if global_assistant_file_id is not None:
        try:
            delete_assistant_file(ASSISTANT_ID, global_assistant_file_id)
            delete_file(global_assistant_file_id)  # Delete the file from OpenAI
        except Exception as e:
            print(f"Failed to delete assistant file on exit: {str(e)}")
    if thread_id is not None:
        try:
            delete_thread(thread_id)  # Delete the thread
        except Exception as e:
            print(f"Failed to delete thread on exit: {str(e)}")

atexit.register(cleanup)

def create_thread(messages=None, metadata=None, file_ids=None):
    logging.info("Creating a new thread.")
    global thread_id
    url = "https://api.openai.com/v1/threads"
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json",
        "OpenAI-Beta": "assistants=v1"
    }
    
    # Pre-existing hardcoded file ID in the assistant's system settings
    hardcoded_file_id = "file-wSkAIsTLbSUrcNM9CP4AK51n"
    
    # Modify the initial message to include file_ids if provided
    initial_message = {
        "role": "user",
        "content": "Initial message",
    }
    
    # Ensure file_ids is a list and add the hardcoded_file_id to it
    if file_ids is None:
        file_ids = []
    file_ids.append(hardcoded_file_id)  # Add the pre-existing hardcoded file ID
    initial_message["file_ids"] = file_ids

    # Ensure messages is a list and add the initial_message to it
    messages = messages or []
    messages.insert(0, initial_message)

    data = {
        "messages": messages,
        "metadata": metadata or {}
    }
    
    response = requests.post(url, headers=headers, json=data)
    if response.status_code == 200:
        thread_id = response.json()['id']
        logging.info(f"Thread created successfully with ID: {thread_id}")
        welcome_message = """
        Welcome to the "Digital Healthcare and AI" course, brought to you by the Royal College of Surgeons.

        This interactive tool is designed to enhance your learning experience by providing access to essential course materials and features:

        - **Course Modules**: Dive into four comprehensive modules covering the fundamentals and applications of AI and ML in healthcare, ethical considerations, and future trends.
            1. *Introduction to AI, ML, and Data Science*: Explore the historical evolution and impact on modern life.
            2. *AI and ML in Healthcare*: Discover how AI and ML are revolutionizing healthcare delivery, diagnostics, and treatment options.
            3. *Generative AI in Medicine*: Learn about the implications for personalized medicine and drug discovery.
            4. *Ethical Implications of AI in Healthcare*: Understand the ethical and legal considerations in deploying AI technologies.

        - **Interactive Engagement**: Engage with reflective questions and hypothetical scenarios to apply your knowledge and encourage critical thinking.

        - **Knowledge Checks**: Assess your understanding through formative and summative assessments, with immediate feedback to guide your learning journey.

        **Getting Started**:
        - Click "Start OAuth for Google API" to enable access to course materials.
        - "Submit Session" allows you to save your progress and submit assessments.

        Are you ready to embark on this innovative journey to explore how AI is transforming healthcare? Type 'I'm ready' and press enter, or the "Send" button to begin.

        Status updates and instructions will be displayed below. Feel free to ask questions and seek support throughout your learning experience.
        """

        # Display the welcome message in the conversation_text widget
        conversation_text.config(state='normal')
        conversation_text.tag_configure('assistant_author', foreground='pink')
        conversation_text.insert(tk.END, "HealthNex AI: ", 'assistant_author')
        conversation_text.insert(tk.END, welcome_message)
        conversation_text.config(state='disabled')
        logging.info("Welcome message displayed successfully.")
    else:
        logging.error(f"Failed to create thread: {response.text}")
        print(f"Failed to create thread: {response.text}")

def add_message_to_thread(thread_id, role, content, file_ids=None, metadata=None):
    url = f"https://api.openai.com/v1/threads/{thread_id}/messages"
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json",
        "OpenAI-Beta": "assistants=v1"
    }

    payload = {
        "role": role,
        "content": content,
        "file_ids": file_ids if file_ids else [],
        "metadata": metadata if metadata else {}
    }

    try:
        response = requests.post(url, headers=headers, data=json.dumps(payload), timeout=25)
        response.raise_for_status()  # Raises an HTTPError for bad responses
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"An error occurred: {e}")
        return {"status": "error", "message": str(e)}

def run_thread(thread_id, assistant_id, model=None, instructions=None, additional_instructions=None, tools=None, metadata=None):
    # Start a new run
    url = f"https://api.openai.com/v1/threads/{thread_id}/runs"
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json",
        "OpenAI-Beta": "assistants=v1"
    }

    # Define default tools if not provided, including the "retrieval" tool.
    if tools is None:
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "retrieve_doc_contents",
                    "description": "Retrieve the contents of a specified Google Doc",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "document_id": {
                                "type": "string",
                                "description": "The ID of the Google Doc to retrieve contents from"
                            }
                        },
                        "required": ["document_id"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "append_to_sheet",
                    "description": "Appends data to a Google Spreadsheet, organizing the data across three columns: User name, Formal Assistant Response, and Summative Assessment Response.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "user_name": {
                                "type": "string",
                                "description": "The users name."
                            },
                            "formal_response": {
                                "type": "string",
                                "description": "The formal assessment response."
                            },
                            "summative_assessment": {
                                "type": "string",
                                "description": "The summative assessment response."
                            }
                        },
                        "required": ["user_name", "formal_response", "summative_assessment"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "retrieve_sheet_data",
                    "description": "Retrieve data from specified rows in a Google Sheet, considering the stage of the lesson the bot is on",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "rows": {
                                "type": "array",
                                "items": {
                                    "type": "integer"
                                },
                                "description": "The rows from which to fetch data, specified as an array of integers"
                            }
                        },
                        "required": ["rows"]
                    }
                }
            },
            {
                "type": "retrieval",
            }
        ]

    logging.debug(f"Preparing to send payload with assistant_id: {assistant_id[:8]}...")  # Truncate for privacy
    payload = {
        "assistant_id": assistant_id,
        "model": model,
        "instructions": instructions,
        "additional_instructions": additional_instructions,
        "tools": tools,
        "metadata": metadata or {}
    }
    logging.info("Sending request to API...")
    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()  # Raises an HTTPError for bad responses
        logging.info("Request successfully processed by the API.")
        return response.json()
    except requests.exceptions.HTTPError as errh:
        logging.error(f"HTTP Error: {errh}")
    except requests.exceptions.ConnectionError as errc:
        logging.error(f"Error Connecting: {errc}")
    except requests.exceptions.Timeout as errt:
        logging.error(f"Timeout Error: {errt}")
    except requests.exceptions.RequestException as err:
        logging.error(f"Unexpected Error: {err}")
    except Exception as e:
        logging.error(f"An unexpected error occurred: {str(e)}")

    # Return an error message if the request failed
    return {"error": "Failed to start a new run due to an error."}

def submit_function_outputs(thread_id, run_id, tool_call_id, tool_outputs):
    """
    Submits the outputs from the called functions back to the run, allowing it to continue.
    Includes error handling and retry logic for rate limiting, with graceful handling of submission failures.
    Enhanced to handle a wider variety of input types by converting them to strings in a more robust manner.
    """
    print(f"Initiating submission of function outputs for thread_id: {thread_id[:8]}..., run_id: {run_id[:8]}..., tool_call_id: {tool_call_id[:8]}...")
    url = f"https://api.openai.com/v1/threads/{thread_id}/runs/{run_id}/submit_tool_outputs"
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json",
        "OpenAI-Beta": "assistants=v1"
    }

    def convert_to_string(value):
        """
        Converts a given value to a string in a more robust manner, handling various data types.
        """
        if isinstance(value, (dict, list, tuple)):
            return json.dumps(value, ensure_ascii=False)
        elif isinstance(value, (int, float, bool)):
            return str(value)
        elif value is None:
            return 'null'
        elif isinstance(value, str):
            return value
        else:
            # Attempt to use the object's __str__ method
            return str(value)

    # Ensure each output is converted to a string in a more robust manner
    formatted_tool_outputs = [{"tool_call_id": tool_call_id, "output": convert_to_string(output)} for output in tool_outputs]
    data = {"tool_outputs": formatted_tool_outputs}

    print(f"Submitting the following data: {data}")  # Added detailed logging

    max_retries = 3
    retry_delay = 1  # Initial delay in seconds
    submission_successful = False  # Flag to track submission status

    # Attempt to submit the tool outputs with retry logic
    for attempt in range(max_retries):
        try:
            response = requests.post(url, json=data, headers=headers, timeout=10)  # Set a timeout of 10 seconds
            response.raise_for_status()  # Check for HTTP errors
            print("Submission successful.")
            submission_successful = True  # Update flag on successful submission
            break  # Exit loop on success
        except requests.exceptions.Timeout:
            print("The request timed out. Retrying...")
        except requests.exceptions.RequestException as e:
            if e.response.status_code == 429:  # Rate limit exceeded
                print("Rate limit exceeded. Retrying with exponential backoff...")
                time.sleep(retry_delay)
                retry_delay *= 2  # Double the delay for exponential backoff
            else:
                print(f"An error occurred while submitting tool outputs: {e}")
                break  # Exit the loop for non-rate-limit errors
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
            break  # Exit the loop for unexpected errors

    if not submission_successful:
        print("Failed to submit tool outputs after retries. Skipping this submission to continue with others.")
        return {"status": "error", "message": "Failed to submit after retries, skipped to continue with other submissions."}
    else:
        return response.json()

def retry_with_exponential_backoff(func):
    def wrapper(*args, **kwargs):
        max_retries = 5
        retry_delay = 1.0  # Start with a 1-second delay
        for attempt in range(max_retries):
            result = func(*args, **kwargs)
            # Determine if result is a response object or a dictionary
            if isinstance(result, dict):  # Error case, result is a dictionary
                status_code = result.get('status_code', 500)  # Default to 500 if status_code is not in dictionary
            else:  # Success case, result is a response object
                status_code = result.status_code
            
            if status_code == 429:  # Rate limit exceeded
                sleep_time = retry_delay * (2 ** attempt) + random.uniform(0, 1)
                print(f"Rate limit exceeded. Retrying in {sleep_time:.2f} seconds...")
                time.sleep(sleep_time)
            else:
                return result
        return func(*args, **kwargs)  # Final attempt outside of loop
    return wrapper

@retry_with_exponential_backoff
def get_run_steps(thread_id, run_id, limit=20, order="desc", after=None, before=None):
    url = f"https://api.openai.com/v1/threads/{thread_id}/runs/{run_id}/steps"
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json",
        "OpenAI-Beta": "assistants=v1"
    }
    params = {
        "limit": limit,
        "order": order,
        "after": after,
        "before": before
    }

    response = requests.get(url, headers=headers, params=params)
    return response.json()

@retry_with_exponential_backoff
def get_run_status(thread_id, run_id):
    global should_continue_polling
    url = f"https://api.openai.com/v1/threads/{thread_id}/runs/{run_id}"
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json",
        "OpenAI-Beta": "assistants=v1"
    }

    try:
        response = requests.get(url, headers=headers, timeout=25)
        if response.status_code == 200:
            run_status = response.json().get('status')
            update_status_message(run_status)
            if run_status in ['queued', 'in_progress']:
                return {"status": run_status, "message": "Run is either queued or in progress."}
            elif run_status == 'completed':
                # When the run is completed, stop polling
                should_continue_polling = False
                return {"status": run_status, "message": "Run has successfully completed!"}
            elif run_status == 'requires_action':
                tool_call_id = response.json().get('required_action', {}).get('submit_tool_outputs', {}).get('tool_calls', [{}])[0].get('id', None)
                return {"status": run_status, "message": "Run requires action. Please submit the required tool outputs.", "tool_call_id": tool_call_id}
            elif run_status == 'expired':
                return {"status": run_status, "message": "Run has expired. Outputs were not submitted in time."}
            elif run_status == 'cancelling':
                return {"status": run_status, "message": "Run is currently cancelling."}
            elif run_status == 'cancelled':
                return {"status": run_status, "message": "Run was successfully cancelled."}
            elif run_status == 'failed':
                last_error = response.json().get('last_error', 'No error information available.')
                return {"status": run_status, "message": f"Run failed. Error: {last_error}"}
            else:
                return {"status": "unknown", "message": "Unknown run status."}
        else:
            return {"status": "error", "message": f"Error: {response.status_code} - {response.text}"}
    except requests.exceptions.Timeout:
        return {"status": "error", "message": "Request timed out."}
    except requests.exceptions.RequestException as e:
        return {"status": "error", "message": f"Request failed: {e}"}

def post_load_decorator(func):
    def wrapper(*args, **kwargs):
        global is_filtering_saving_messages
        # Only proceed if not already filtering and saving messages
        if not is_filtering_saving_messages:
            result = func(*args, **kwargs)  # Call the original function
            if result is not None:
                # Assuming the first argument is always thread_id
                thread_id = args[0]
                is_filtering_saving_messages = True
                try:
                    filter_and_save_messages(thread_id)  # Call filter_and_save_messages after loading messages
                finally:
                    is_filtering_saving_messages = False
            return result
        else:
            return func(*args, **kwargs)
    return wrapper

@post_load_decorator
def load_messages_from_cache(thread_id):
    cache_file = f"cache_{thread_id}.json"
    if os.path.exists(cache_file):
        with open(cache_file, 'r') as file:
            return json.load(file)
    return None

def save_messages_to_cache(thread_id, messages):
    cache_file = f"cache_{thread_id}.json"
    with open(cache_file, 'w') as file:
        json.dump(messages, file)

@retry_with_exponential_backoff
def get_messages(thread_id, limit=100, order="asc", after=None, before=None):
    print(f"Fetching messages for thread_id: {thread_id[:10]}... Limit: {limit}, Order: {order}, After: {str(after)[:10]}, Before: {str(before)[:10]}")
    url = f"https://api.openai.com/v1/threads/{thread_id}/messages"
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json",
        "OpenAI-Beta": "assistants=v1"
    }
    params = {
        "limit": limit,
        "order": order,
        "after": after,
        "before": before
    }

    response = requests.get(url, headers=headers, params=params)
    if response.status_code == 200:
        new_messages = response.json()
        print(f"Successfully fetched messages. Response size: {len(str(new_messages))} characters")
        
        cached_messages = load_messages_from_cache(thread_id) or {"data": []}
        all_messages = cached_messages.get("data", []) + new_messages.get("data", [])
        unique_messages = {msg['id']: msg for msg in all_messages}.values()
        
        save_messages_to_cache(thread_id, {"data": list(unique_messages)})

        # After saving messages to cache, filter and save them to a session .txt file
        filter_and_save_messages(thread_id)
        
        return {"data": list(unique_messages)}
    else:
        error_message = {"error": f"Error fetching messages: {response.status_code} - {response.text[:100]}", "status_code": response.status_code}
        print(error_message['error'])
        return error_message

def save_last_message_id_to_cache(thread_id, last_message_id):
    cache_file = f"last_message_id_cache_{thread_id}.json"
    with open(cache_file, 'w') as file:
        json.dump({"last_message_id": last_message_id}, file)

def load_last_message_id_from_cache(thread_id):
    cache_file = f"last_message_id_cache_{thread_id}.json"
    if os.path.exists(cache_file):
        with open(cache_file, 'r') as file:
            data = json.load(file)
            return data.get("last_message_id")
    return None

def get_last_message_id(thread_id):
    logging.debug("Fetching the last message ID for thread_id: %s", thread_id)

    # Attempt to load the last message ID from cache first
    cached_last_message_id = load_last_message_id_from_cache(thread_id)
    if cached_last_message_id:
        logging.debug("Last message ID loaded from cache: %s", cached_last_message_id)
        return cached_last_message_id

    # If not found in cache, fetch the latest messages in descending order (most recent first)
    messages_response = get_messages(thread_id, limit=1, order="desc")

    if isinstance(messages_response, dict) and messages_response.get("object") == "list":
        messages = messages_response.get("data", [])
        if messages:
            # Get the ID of the very last message, regardless of the sender
            last_message_id = messages[0].get("id")
            logging.debug("Last message ID found: %s", last_message_id)
            # Save the last message ID to cache
            save_last_message_id_to_cache(thread_id, last_message_id)
            return last_message_id

    logging.warning("No messages found in the thread")
    return None

def save_runs_to_cache(thread_id, runs):
    cache_file = f"runs_cache_{thread_id}.json"
    with open(cache_file, 'w') as file:
        json.dump(runs, file)

def load_runs_from_cache(thread_id):
    cache_file = f"runs_cache_{thread_id}.json"
    if os.path.exists(cache_file):
        with open(cache_file, 'r') as file:
            return json.load(file)
    return None

def get_runs(thread_id, limit=100, order="desc", after=None, before=None):
    cached_runs = load_runs_from_cache(thread_id)
    if cached_runs:
        print("Loaded runs from cache.")
        return cached_runs

    url = f"https://api.openai.com/v1/threads/{thread_id}/runs"
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json",
        "OpenAI-Beta": "assistants=v1"
    }
    params = {
        "limit": limit,
        "order": order,
        "after": after,
        "before": before
    }

    response = requests.get(url, headers=headers, params=params)
    if response.status_code == 200:
        runs = response.json()
        # Save the fetched runs to cache
        save_runs_to_cache(thread_id, runs)
        return runs
    else:
        error_message = f"Error: {response.status_code} - {response.text}"
        print(error_message)
        return {"error": error_message}

def send_message():
    global thread_id

    if not thread_id:
        print("[ERROR] Thread not initialized. Unable to send message.")
        return

    user_message = message_entry.get("1.0", "end-1c")

    # Clear the entry widget
    message_entry.delete("1.0", "end")

    # Send the user's message to the thread
    add_message_to_thread(thread_id, "user", user_message)
    print(f"[INFO] Message sent to thread. Message (truncated to 100 chars): {user_message[:100]}")

    # Display the message directly without the typing effect
    conversation_text.config(state='normal')
    conversation_text.insert(tk.END, f"User: {user_message}\n", 'user_message')
    conversation_text.config(state='disabled')
    print("[INFO] Message displayed in GUI.")

    try:
        # Call run_thread to process the user message
        run_status_response = run_thread(thread_id, ASSISTANT_ID)
        run_id = run_status_response.get("id")  # Extract the run ID from the response
        print(f"[INFO] Run thread initiated. Run ID: {run_id}")

        # Handle the run status in a separate function
        handle_run_status(thread_id, run_id)

    except Exception as e:
        print(f"[ERROR] An error occurred while sending message or initiating run thread. Error: {str(e)[:100]}")  # Truncate error message

def handle_run_status(thread_id, run_id):
    logging.info("Starting to check the status of the run in a loop with a delay.")
    run_status = None
    attempt_count = 0
    while run_status not in ['completed', 'requires_action', 'failed']:
        attempt_count += 1
        logging.info(f"Attempt {attempt_count}: Checking run status for thread_id: {thread_id}, run_id: {run_id}")
        status_response = get_run_status(thread_id, run_id)
        if status_response.get("status") == "error":
            logging.error(f"Error fetching run status: {status_response.get('message')}")
            update_status_message(f"Error fetching run status: {status_response.get('message')}")
            break

        run_status = status_response.get('status')
        logging.info(f"Current run status: {run_status}, Message: {status_response.get('message', 'No message available')}")

        if run_status == 'requires_action':
            logging.info("Run status requires action. Handling 'requires_action' status.")
            tool_call_id = status_response.get('tool_call_id')
            if tool_call_id:
                logging.info(f"Found tool_call_id: {tool_call_id}. Fetching run steps.")
                steps_response = get_run_steps(thread_id, run_id)
                for step in steps_response.get('data', []):
                    for tool_call in step.get('step_details', {}).get('tool_calls', []):
                        tool_name = tool_call.get('function', {}).get('name')
                        logging.info(f"Processing function call: {tool_name}")
                        if tool_name in ['retrieve_sheet_data', 'retrieve_doc_contents', 'append_to_sheet']:
                            arguments_str = tool_call.get('function', {}).get('arguments', '{}')
                            arguments_dict = json.loads(arguments_str)
                            if tool_name == 'retrieve_sheet_data':
                                rows = arguments_dict.get('rows')
                                if rows:
                                    sheet_data = retrieve_rows_data(SPREADSHEET_ID, rows=rows)
                                    formatted_sheet_data = "\n".join([str(row) for row in sheet_data])
                                    tool_output = {"tool_call_id": tool_call_id, "output": formatted_sheet_data}
                                    submit_function_outputs(thread_id, run_id, tool_call_id, [tool_output])
                            elif tool_name == 'retrieve_doc_contents':
                                document_id = arguments_dict.get('document_id')
                                if document_id:
                                    doc_contents = retrieve_doc_contents(document_id)
                                    tool_output = {"tool_call_id": tool_call_id, "output": doc_contents}
                                    submit_function_outputs(thread_id, run_id, tool_call_id, [tool_output])
                            elif tool_name == 'append_to_sheet':
                                user_name = arguments_dict.get('user_name')
                                formal_response = arguments_dict.get('formal_response')
                                summative_assessment = arguments_dict.get('summative_assessment')
                                if user_name and formal_response and summative_assessment:
                                    append_result = append_to_sheet(SPREADSHEET_ID1, user_name, formal_response, summative_assessment)
                                    print(f"Append to sheet result: {append_result}")  # Log the result of the append operation
                                    tool_output = {"tool_call_id": tool_call_id, "output": "Data appended successfully."}
                                    submit_function_outputs(thread_id, run_id, tool_call_id, [tool_output])
                        else:
                            logging.warning(f"No handler for function call: {tool_name}")
        elif run_status in ['queued', 'in_progress']:
            print("Run status not completed. Waiting for 3 seconds before checking the status again.")
            time.sleep(3)  # Wait for 3 seconds before checking the status again
        else:
            print(f"Run completed or reached a final state: {run_status}. Exiting loop.")
            break  # Exit the loop
        check_and_display_new_messages(run_id)
        print(f"Run ended with status: {run_status}")


def check_and_display_new_messages(run_id):
    global thread_id
    global last_displayed_message_id  # Ensure this global variable is accessible within this function
    polling_interval = 3  # Initial polling interval in seconds
    logging.debug(f"Polling for new messages with interval: {polling_interval} seconds")
    should_continue_polling = True  # Flag to indicate whether polling should continue

    def poll_messages(run_id):
        nonlocal polling_interval, should_continue_polling  # Ensure these are accessible
        print(f"Polling messages for run_id: {run_id[:10]}...")  # Limiting run_id printout for brevity
        
        run_status_response = get_run_status(thread_id, run_id)
        print(f"Run status response (limited): {str(run_status_response)[:50]}")  # Limiting content for brevity
        
        if run_status_response['status'] in ['completed', 'requires_action']:
            should_continue_polling = False  # Stop polling if run is completed or requires action
            print(f"Polling stopped. Run status: {run_status_response['status']}")
            if run_status_response['status'] == 'completed':
                fetch_and_display_messages(run_id)
        else:
            print(f"Scheduling next poll in {polling_interval} seconds.")
            if polling_interval < 15:
                polling_interval += 3  # Increment the polling interval by 3 seconds, up to a maximum of 15 seconds
            threading.Timer(polling_interval, lambda: poll_messages(run_id)).start()

    def fetch_and_display_messages(run_id):
        global thread_id
        global last_displayed_message_id
        global displayed_message_ids

        print(f"[INFO] Initiating fetch for messages. Thread ID: {thread_id[:10]}, Run ID: {run_id[:10]}")
        messages_response = get_messages(thread_id, order="asc")
        print(f"[DEBUG] Messages response (truncated): {str(messages_response)[:100]}")

        if messages_response.get("data"):
            messages = messages_response["data"]
            print(f"[INFO] Total messages fetched: {len(messages)}")

            # Filter out messages that have already been displayed
            new_messages = [msg for msg in messages if msg["id"] not in displayed_message_ids]
            print(f"[INFO] New messages identified for display: {len(new_messages)}")

            for message in new_messages:
                role = message["role"]
                content_parts = [part["text"]["value"] for part in message["content"] if part["type"] == "text"]
                content = "".join(content_parts)
                print(f"[DISPLAY] Message ID: {message['id']}, Role: {role}, Content (truncated): {content[:100]}")

                # Display the message and then mark it as displayed
                display_message(message["id"], role, content)
                # Note: The addition to displayed_message_ids should now happen inside display_message

            if new_messages:
                # Update last_displayed_message_id based on the last message in the new_messages list
                last_displayed_message_id = new_messages[-1]["id"]
                print(f"[UPDATE] Last displayed message ID updated to: {last_displayed_message_id}")
            else:
                print("[INFO] No new messages to display. Last displayed message ID remains unchanged.")

    poll_messages(run_id)


def display_message(message_id, role, content):
    global displayed_message_ids
    global thread_id
    global root  # Ensure root is globally accessible

    def update_gui():
        if message_id in displayed_message_ids:
            return

        conversation_text.config(state='normal')

        if conversation_text.get("end-2l", tk.END).strip() == "Assistant is typing...":
            end_line_index = conversation_text.index("end-1c linestart")
            conversation_text.delete(end_line_index, tk.END)

        tag = 'user_author' if role == "user" else 'assistant_author'
        author = "You" if role == "user" else "Assistant"

        conversation_text.tag_configure('assistant_author', foreground='pink')
        conversation_text.tag_configure('user_author', foreground='lightblue')

        # Insert the author tag
        conversation_text.insert(tk.END, f"\n{author}: ", tag)

        # Process and insert the content
        process_and_insert_content(content)

        conversation_text.config(state='disabled')
        displayed_message_ids.add(message_id)


    def process_and_insert_content(content):
        # Split the content into lines for processing
        lines = content.split('\n')
        for line in lines:
            # Existing formatting logic
            if line.startswith("### "):
                line = line[4:]
                title_tag = "title_text"
                conversation_text.tag_configure(title_tag, font=("Roboto", 18, "bold"))
                conversation_text.insert(tk.END, f"{line}\n", title_tag)
            elif re.match(r'^(\-|\*|\d+\.) \*\*.*\*\*$', line):
                line = re.sub(r'\*\*(.*)\*\*', r'\1', line)
                bold_tag = "list_bold_text"
                conversation_text.tag_configure(bold_tag, font=("Roboto", 17, "bold"))
                conversation_text.insert(tk.END, f"{line}\n", bold_tag)
            elif line.startswith("**") and line.endswith("**"):
                line = line[2:-2]
                bold_tag = "bold_text"
                conversation_text.tag_configure(bold_tag, font=("Roboto", 18, "bold"))
                conversation_text.insert(tk.END, f"{line}\n", bold_tag)
            else:
                insert_with_url_detection(line + '\n')  # Call the URL detection function for regular text

    def insert_with_url_detection(text):
        # Regular expression to match URLs
        url_pattern = r'https?://[^\s]+'
        start = 0
        for match in re.finditer(url_pattern, text):
            # Insert text up to the URL
            conversation_text.insert(tk.END, text[start:match.start()])
            # Insert leading space for padding (make clickable area larger)
            conversation_text.insert(tk.END, " ")
            # Insert the URL with a hyperlink tag
            url = match.group()
            hyperlink_tag = "hyperlink_" + str(uuid.uuid4())  # Unique tag for each hyperlink
            conversation_text.tag_configure(hyperlink_tag, foreground="blue", underline=1)
            # Apply the tag to the URL and surrounding spaces
            conversation_text.insert(tk.END, " " + url + " ", hyperlink_tag)
            # Bind the click event to open the URL in a web browser
            conversation_text.tag_bind(hyperlink_tag, "<Button-1>", lambda event, url=url: webbrowser.open(url))
            # Insert trailing space for padding (make clickable area larger)
            conversation_text.insert(tk.END, " ")
            start = match.end()
        # Insert any remaining text after the last URL
        conversation_text.insert(tk.END, text[start:])

    # Schedule GUI updates on the main thread
    root.after(0, update_gui)

def create_scrolled_text(root):
    # Create a frame to hold the text widget and the scrollbar
    frame = tk.Frame(root)
    frame.grid(row=0, column=0, columnspan=2, padx=50, sticky="nsew")

    # Create a text widget with the desired appearance, including line spacing
    text_widget = tk.Text(frame, font=("Roboto", 16), wrap=tk.WORD, padx=50, pady=10, borderwidth=0, highlightthickness=0, bg=root.cget('bg'), spacing3=0.5)
    text_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    # Create a scrollbar that blends with the background
    scrollbar = ctk.CTkScrollbar(frame, command=text_widget.yview, fg_color=root.cget('bg'))
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    # Configure the text widget to use the scrollbar
    text_widget.config(yscrollcommand=scrollbar.set)

    return text_widget


def create_message_entry(root):
    # Create a frame to hold the text widget and the scrollbar
    entry_frame = tk.Frame(root)
    entry_frame.grid(row=1, column=0, sticky="ew", padx=60)
    root.grid_rowconfigure(1, weight=1)
    root.grid_columnconfigure(0, weight=1)

    # Fetch the background color of the root window
    bg_color = root.cget('bg')

    # Create a text widget for multiline input with a matching background color
    message_entry = tk.Text(entry_frame, height=4, wrap="word", font=("Roboto", 16), padx=10, pady=10, borderwidth=0, highlightthickness=0, bg=bg_color)
    message_entry.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    # Bind the Enter key while focusing on message_entry to send_message function
    # and prevent default newline insertion unless Shift is pressed
    def handle_enter_key(event):
        if event.state & 0x0001:  # Shift key is down
            return "break"  # Proceed with the default behavior (insert newline)
        else:
            send_message()  # Call the send_message function
            return "break"  # Prevent the default behavior

    message_entry.bind("<Return>", handle_enter_key)

    # Continue with the scrollbar setup and return statement...
    scrollbar = tk.Scrollbar(entry_frame, command=message_entry.yview)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    message_entry.config(yscrollcommand=scrollbar.set)
    scrollbar.config(bg=bg_color)

    return message_entry


# Function to add the logo to the bottom right corner of the GUI, with adaptive background
def add_logo(root, logo_path):
    # Open the image using PIL
    logo_image = Image.open(logo_path)
    
    # Resize the image (example: resizing to a width of 250 pixels while maintaining aspect ratio)
    basewidth = 250
    wpercent = (basewidth / float(logo_image.size[0]))
    hsize = int((float(logo_image.size[1]) * float(wpercent)))
    logo_image = logo_image.resize((basewidth, hsize), Image.Resampling.LANCZOS)
    
    # Convert to PhotoImage
    logo_photo = ImageTk.PhotoImage(logo_image)

    # Determine the background color based on the current appearance mode
    # For light theme, attempt to set a "transparent" background by using the root's background color
    # For dark theme, set the background to white
    if ctk.get_appearance_mode() == "light":
        bg_color = root.cget('bg')  # Attempt to match the root window's background for a "transparent" effect
    else:
        bg_color = 'white'  # Set background to white for dark theme

    # Create a label to hold the image, with a background color that adapts to the theme
    logo_label = tk.Label(root, image=logo_photo, bg=bg_color)
    logo_label.image = logo_photo  # Keep a reference to prevent garbage collection

    # Place the label in the bottom right corner
    logo_label.place(relx=1.0, rely=1.0, anchor='se')


# Your existing setup for the GUI
root = ctk.CTk()
root.title("Chat with HealthNex AI")
root.resizable(True, True)

# Set the appearance mode and color theme
ctk.set_appearance_mode("dark")  # or "dark"
ctk.set_default_color_theme("blue")  # or any other color

# Configure grid for dynamic resizing
root.grid_rowconfigure(1, weight=1)
root.grid_columnconfigure(0, weight=1)

conversation_text = scrolledtext.ScrolledText(root, state='disabled', height=30, width=100, font=("Roboto", 16), wrap=tk.WORD, padx=50, pady=10, bg=root.cget('bg'), borderwidth=0, highlightthickness=0, spacing3=0.5)
conversation_text.grid(row=0, column=0, columnspan=2, padx=50)

conversation_text = create_scrolled_text(root)
# Message Entry with 50 pixels of indent space on either side
# Replace the single-line entry with the multiline message entry
message_entry = create_message_entry(root)

auth_button = ctk.CTkButton(root, text="Start OAuth for Google API", command=lambda: threading.Thread(target=start_oauth_and_server).start())
auth_button.grid(row=4, column=0, padx=60, pady=10)

# Add this button in the GUI section where other buttons are defined
submit_button = ctk.CTkButton(root, text="Submit Session", command=lambda: threading.Thread(target=submit_session).start())
submit_button.grid(row=5, column=0, padx=60, pady=10)
# Step 1: Add a Status Display Field at the bottom of the GUI
status_label = ctk.CTkLabel(root, text="Status: Initializing...", anchor="w")
status_label.grid(row=6, column=0, columnspan=2, padx=60, pady=10, sticky="ew")

search_and_upload_button = ctk.CTkButton(root, text="Start & Fetch Latest AI News", command=initiate_search_and_upload)
search_and_upload_button.grid(row=7, column=0, padx=60, pady=10)  # Adjust row index as needed

# Call the function in your GUI setup section, pass the path to your image
add_logo(root,'RCS-logo.png')


def update_status_message(message):
    """
    Updates the status message display in a thread-safe manner.
    """
    def _update():
        if root:  # Check if root still exists; this is a simplistic check
            status_label.configure(text=f"Status: {message}")
    try:
        root.after(0, _update)
    except RuntimeError as e:
        print(f"Error updating status message: {e}")
open_basic_html()

root.mainloop()
