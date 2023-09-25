import asyncio
import os
import sys
from urllib.parse import urlparse

from gql import Client, gql
from gql.transport.appsync_auth import AppSyncApiKeyAuthentication
from gql.transport.appsync_websockets import AppSyncWebsocketsTransport

# Uncomment the following lines to enable debug output
# import logging
# logging.basicConfig(level=logging.DEBUG)

SUBSCRIPTION = gql("""
subscription RequestedKaraoke {
  requestedKaraoke {
    name
    artists
    duration
    id
  }
}
""")

async def main():

    # Should look like:
    # https://XXXXXXXXXXXXXXXXXXXXXXXXXX.appsync-api.REGION.amazonaws.com/graphql
    url = "https://45uu7k6g6vdt3agqreaw4gytoa.appsync-api.us-east-1.amazonaws.com/graphql"
    api_key = "da2-eccjoab2rnfaxjdd2nbw35ar74"

    if url is None or api_key is None:
        print("Missing environment variables")
        sys.exit()

    # Extract host from url
    host = str(urlparse(url).netloc)

    print(f"Host: {host}")

    auth = AppSyncApiKeyAuthentication(host=host, api_key=api_key)

    transport = AppSyncWebsocketsTransport(url=url, auth=auth)

    async with Client(transport=transport) as session:

        print("Waiting for messages...")

        async for result in session.subscribe(SUBSCRIPTION):
            print(result)


asyncio.run(main())