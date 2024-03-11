import os
from azure.communication.networktraversal import CommunicationRelayClient
from azure.identity import DefaultAzureCredential
from azure.communication.identity import CommunicationIdentityClient
import json
import logging
import os
import sys
import time
from pathlib import Path

import requests

logging.basicConfig(stream=sys.stdout, level=logging.INFO,  # set to logging.DEBUG for verbose output
        format="[%(asctime)s] %(message)s", datefmt="%m/%d/%Y %I:%M:%S %p %Z")
logger = logging.getLogger(__name__)

# Your Speech resource key and region
# This example requires environment variables named "SPEECH_KEY" and "SPEECH_REGION"

SUBSCRIPTION_KEY = os.getenv("SUBSCRIPTION_KEY", 'subkey')
SERVICE_REGION = os.getenv("SERVICE_REGION", "westus2")

NAME = "Simple avatar synthesis"
DESCRIPTION = "Simple avatar synthesis description"

# The service host suffix.
SERVICE_HOST = "customvoice.api.speech.microsoft.com"

try:
    print("Azure Communication Services - Access Relay Configuration Quickstart")

    # Authentication setup
    # Replace <RESOURCE_NAME> and KEY with your actual resource name and key
    connection_string = 'endpoint='
    endpoint = "https://<server>.unitedstates.communication.azure.com"

    # Using Azure Active Directory Authentication (DefaultAzureCredential)
    # Ensure AZURE_TENANT_ID, AZURE_CLIENT_ID, and AZURE_CLIENT_SECRET are set as environment variables
    identity_client = CommunicationIdentityClient(endpoint, DefaultAzureCredential())
    relay_client = CommunicationRelayClient(endpoint, DefaultAzureCredential())

    # Alternatively, authenticate using your connection string
    # Uncomment the lines below if you prefer to use a connection string for authentication
    identity_client = CommunicationIdentityClient.from_connection_string(connection_string)
    relay_client = CommunicationRelayClient.from_connection_string(connection_string)

    # Create a user from identity
    user = identity_client.create_user()
    print(f"Created user with id: {user.properties['id']}")

    # Getting the relay configuration
    relay_configuration = relay_client.get_relay_configuration(user=user)
    print("Relay Configuration:")
    for iceServer in relay_configuration.ice_servers:
        assert iceServer.username is not None
        print('Username: ' + iceServer.username)

        assert iceServer.credential is not None
        print('Credential: ' + iceServer.credential)
        
        assert iceServer.urls is not None
        for url in iceServer.urls:
            print('Url: ' + url)

except Exception as ex:
    print("Exception:")
    print(ex)
