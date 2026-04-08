import os
import json
import requests
from datetime import datetime
from dotenv import load_dotenv
from azure.storage.blob import BlobServiceClient
from azure.core.exceptions import ResourceExistsError, ResourceNotFoundError

# Load environment variables
load_dotenv()


class WeatherDashboard:
    def __init__(self):
        self.api_key = os.getenv('OPENWEATHER_API_KEY')
        self.container_name = os.getenv('AZURE_CONTAINER_NAME')       # equivalent to AWS_BUCKET_NAME

        # Azure equivalent of boto3.client('s3')
        # Connect via connection string (from Azure Portal → Storage Account → Access Keys)
        connection_string = os.getenv('AZURE_STORAGE_CONNECTION_STRING')
        self.blob_service_client = BlobServiceClient.from_connection_string(connection_string)

    def create_container_if_not_exists(self):
        """Create Azure Blob container if it doesn't exist"""
        try:
            self.blob_service_client.create_container(self.container_name)
            print(f"Successfully created container '{self.container_name}'")
        except ResourceExistsError:
            print(f"Container '{self.container_name}' already exists")
        except Exception as e:
            print(f"Error creating container: {e}")

    def fetch_weather(self, city):
        """Fetch weather data from OpenWeather API (unchanged from AWS version)"""
        base_url = "http://api.openweathermap.org/data/2.5/weather"
        params = {
            "q": city,
            "appid": self.api_key,
            "units": "imperial"
        }
        try:
            response = requests.get(base_url, params=params)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error fetching weather data: {e}")
            return None

    def save_to_blob(self, weather_data, city):
        """
        Save weather data to Azure Blob Storage.
        """
        if not weather_data:
            return False

        timestamp = datetime.now().strftime('%Y%m%d-%H%M%S')
        blob_name = f"weather-data/{city}-{timestamp}.json"   # same path convention as S3 key

        try:
            weather_data['timestamp'] = timestamp

            # Get a client for this specific blob (file), then upload
            blob_client = self.blob_service_client.get_blob_client(
                container=self.container_name,
                blob=blob_name
            )
            blob_client.upload_blob(
                json.dumps(weather_data),
                overwrite=True,
                content_settings=None   # optionally set ContentType via ContentSettings
            )
            print(f"Successfully saved data for {city} to Azure Blob Storage")
            return True
        except Exception as e:
            print(f"Error saving to Blob Storage: {e}")
            return False


def main():
    dashboard = WeatherDashboard()

    # Create container if needed (equivalent to create_bucket_if_not_exists)
    dashboard.create_container_if_not_exists()

    cities = ["Abia,ng", "Minna", "Abuja"]

    for city in cities:
        print(f"\nFetching weather for {city}...")
        weather_data = dashboard.fetch_weather(city)
        if weather_data:
            temp        = weather_data['main']['temp']
            feels_like  = weather_data['main']['feels_like']
            humidity    = weather_data['main']['humidity']
            description = weather_data['weather'][0]['description']

            print(f"Temperature: {temp}°F")
            print(f"Feels like: {feels_like}°F")
            print(f"Humidity: {humidity}%")
            print(f"Conditions: {description}")

            success = dashboard.save_to_blob(weather_data, city)
            if success:
                print(f"Weather data for {city} saved to Azure Blob Storage!")
        else:
            print(f"Failed to fetch weather data for {city}")


if __name__ == "__main__":
    main()