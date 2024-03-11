# HealthNexAI

## Introduction
HealthNexAI.py is a comprehensive Python application designed to enhance healthcare and AI research by aggregating the latest developments from the web, providing an interactive chat interface, and integrating with cognitive services for speech-to-text and text-to-speech functionalities.

## Features
- Web scraping for the latest healthcare and AI news.
- An interactive chat interface with a talking avatar.
- Integration with Google Sheets API for data management.
- OAuth authentication for secure access to Google services.
- Local server setup for handling speech synthesis requests.
- Cache management for efficient data processing.
- Integration with Microsoft Azure API for enhanced cognitive services.

## Setup Instructions
1. Clone the repository to your local machine.
2. Install the required dependencies listed in `requirements.txt` using the command `pip install -r requirements.txt`.
3. Obtain necessary API keys and credentials:
   - Google Sheets API credentials.
   - OpenAI API key for chat functionalities.
   - SerpAPI key for web scraping.
   - Microsoft Azure API credentials for cognitive services.
4. Update the `config.ini` file with your API keys and credentials.
5. Replace placeholders in `basic.html` with your Microsoft Azure API credentials:
   - Update `subscriptionKey`, `username`, and `credential` placeholders in `basic.html` with your actual credentials.
6. Replace the placeholder in `token.php` with your actual API key.
7. Run `issue-relay-tokens.py` to generate and configure relay tokens for your application.
8. Upon running `healthnexai.py`, you will be prompted to enter your OpenAI API key.
9. Run `healthnexai.py` to start the application.

## Usage
- Start the application and follow the on-screen instructions to authenticate with Google.
- Use the chat interface to interact with the HealthNexAI assistant.
- Access the latest healthcare and AI news fetched by the application.
- Manage your data using the integrated Google Sheets functionality.

## Related Files
- `search.py`: Handles web scraping and content aggregation.
- `basic.html`: Provides the frontend for the talking avatar using cognitive services.
- `cachecheck.py`: Manages a local server for processing speech synthesis requests and caching.
- `issue-relay-tokens.py`: Script to generate and configure relay tokens for Azure Communication Services.

## Acknowledgments
This application integrates various technologies and APIs, including Google Sheets API, OpenAI's GPT-3, SerpAPI for web scraping, Microsoft Cognitive Services Speech SDK, and Microsoft Azure API for the talking avatar feature.

For more information on configuring and extending the application, refer to the comments and documentation within each script file.
