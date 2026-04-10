import os
import json
import requests
import re
import smtplib
from datetime import datetime, timedelta
from email.message import EmailMessage
from dotenv import load_dotenv
from azure.storage.blob import BlobServiceClient
from azure.core.exceptions import ResourceExistsError

# Load environment variables
load_dotenv()


class WeatherDashboard:
    def __init__(self):
        self.api_key = os.getenv('OPENWEATHER_API_KEY')
        self.container_name = os.getenv('AZURE_CONTAINER_NAME')       # equivalent to AWS_BUCKET_NAME
        self.output_modes = {
            mode.strip().lower()
            for mode in os.getenv('OUTPUT_MODES', 'blob').split(',')
            if mode.strip()
        }

        self.smtp_host = os.getenv('SMTP_HOST')
        self.smtp_port = int(os.getenv('SMTP_PORT', '587'))
        self.smtp_username = os.getenv('SMTP_USERNAME')
        self.smtp_password = os.getenv('SMTP_PASSWORD')
        self.mail_from = os.getenv('MAIL_FROM')
        self.mail_to = os.getenv('MAIL_TO')

        frontend_dir = os.getenv('FRONTEND_DIR', 'frontend')
        self.frontend_dir = os.path.abspath(frontend_dir)

        # Azure equivalent of boto3.client('s3')
        # Connect via connection string (from Azure Portal → Storage Account → Access Keys)
        connection_string = os.getenv('AZURE_STORAGE_CONNECTION_STRING')
        self.blob_service_client = None
        if connection_string:
            self.blob_service_client = BlobServiceClient.from_connection_string(connection_string)

    @staticmethod
    def city_slug(city):
        return re.sub(r'[^a-z0-9]+', '-', city.strip().lower()).strip('-') or 'unknown-city'

    @staticmethod
    def deg_to_compass(deg):
        if not isinstance(deg, (int, float)):
            return 'N/A'
        points = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW']
        return points[round(deg / 45) % 8]

    @staticmethod
    def build_frontend_payload(weather_data, city):
        temp_c = (weather_data['main']['temp'] - 32) * 5 / 9
        feels_c = (weather_data['main']['feels_like'] - 32) * 5 / 9
        wind_kph = weather_data.get('wind', {}).get('speed', 0) * 1.60934

        fallback_forecast = []
        now = datetime.now()
        for i in range(5):
            day_temp = round(temp_c + (i % 3 - 1))
            fallback_forecast.append({
                'day': (now + timedelta(days=i)).strftime('%a'),
                'icon': weather_data['weather'][0]['icon'],
                'hi_c': day_temp + 2,
                'lo_c': day_temp - 2
            })

        return {
            'city': city,
            'country': f"{weather_data.get('sys', {}).get('country', '')}".strip() or 'N/A',
            'temp_c': round(temp_c, 1),
            'feels_c': round(feels_c, 1),
            'humidity': weather_data['main']['humidity'],
            'wind_kph': round(wind_kph, 1),
            'wind_dir': self.deg_to_compass(weather_data.get('wind', {}).get('deg')),
            'condition': weather_data['weather'][0]['description'].title(),
            'icon': weather_data['weather'][0]['icon'],
            'forecast': fallback_forecast,
            'updated_at': weather_data.get('timestamp')
        }

    def create_container_if_not_exists(self):
        """Create Azure Blob container if it doesn't exist"""
        if not self.blob_service_client:
            print("Skipping container check: AZURE_STORAGE_CONNECTION_STRING not set")
            return
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
        if not self.blob_service_client:
            print("Skipping Blob upload: AZURE_STORAGE_CONNECTION_STRING not set")
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

    def save_for_frontend(self, weather_data, city):
        """Write weather JSON files for frontend consumption."""
        if not weather_data:
            return False

        try:
            os.makedirs(self.frontend_dir, exist_ok=True)
            payload = self.build_frontend_payload(weather_data, city)
            latest_path = os.path.join(self.frontend_dir, 'latest-weather.json')
            city_path = os.path.join(self.frontend_dir, f"latest-weather-{self.city_slug(city)}.json")

            with open(latest_path, 'w', encoding='utf-8') as f:
                json.dump(payload, f, indent=2)

            with open(city_path, 'w', encoding='utf-8') as f:
                json.dump(payload, f, indent=2)

            print(f"Saved frontend weather file: {latest_path}")
            print(f"Saved city weather file: {city_path}")
            return True
        except Exception as e:
            print(f"Error writing frontend JSON: {e}")
            return False

    def send_email(self, weather_data, city):
        """Send weather summary via SMTP email."""
        required = [
            self.smtp_host,
            self.smtp_username,
            self.smtp_password,
            self.mail_from,
            self.mail_to,
        ]
        if not all(required):
            print("Skipping email: SMTP/MAIL env vars are missing")
            return False

        try:
            summary = self.build_frontend_payload(weather_data, city)
            subject = f"Weather Update: {summary['city']} ({summary['country']})"
            body = (
                f"City: {summary['city']}\n"
                f"Country: {summary['country']}\n"
                f"Temperature: {summary['temp_c']} C\n"
                f"Feels Like: {summary['feels_c']} C\n"
                f"Humidity: {summary['humidity']}%\n"
                f"Wind: {summary['wind_kph']} km/h (dir: {summary['wind_dir']})\n"
                f"Condition: {summary['condition']}\n"
                f"Updated: {summary['updated_at']}\n"
            )

            msg = EmailMessage()
            msg['Subject'] = subject
            msg['From'] = self.mail_from
            msg['To'] = self.mail_to
            msg.set_content(body)

            with smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=30) as server:
                server.starttls()
                server.login(self.smtp_username, self.smtp_password)
                server.send_message(msg)

            print(f"Weather email sent to {self.mail_to}")
            return True
        except Exception as e:
            print(f"Error sending weather email: {e}")
            return False


def main():
    dashboard = WeatherDashboard()

    # Create container if needed (equivalent to create_bucket_if_not_exists)
    if 'blob' in dashboard.output_modes:
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

            if 'blob' in dashboard.output_modes:
                success = dashboard.save_to_blob(weather_data, city)
                if success:
                    print(f"Weather data for {city} saved to Azure Blob Storage!")

            if 'email' in dashboard.output_modes:
                mail_ok = dashboard.send_email(weather_data, city)
                if mail_ok:
                    print(f"Weather data for {city} sent via email!")

            if 'frontend' in dashboard.output_modes:
                frontend_ok = dashboard.save_for_frontend(weather_data, city)
                if frontend_ok:
                    print(f"Weather data for {city} exported for frontend display!")
        else:
            print(f"Failed to fetch weather data for {city}")


if __name__ == "__main__":
    main()