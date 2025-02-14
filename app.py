from flask import Flask, render_template, request, jsonify
from datetime import datetime
import requests
import os
import json
import time
from math import radians, sin, cos, sqrt, atan2

app = Flask(__name__)

class WeatherApp:
    def __init__(self, api_key):
        self.api_key = api_key
        self.base_url = "http://api.openweathermap.org/data/2.5/forecast"
        self.geo_url = "http://api.openweathermap.org/geo/1.0/direct"
        self.cache_duration = 1800  # 30 minutes cache
        self.create_cache_directory()

    def create_cache_directory(self):
        if not os.path.exists('weather_cache'):
            os.makedirs('weather_cache')

    def get_wind_direction(self, degrees):
        directions = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW']
        index = round(degrees / (360 / len(directions))) % len(directions)
        return directions[index]

    def get_weather_symbol(self, description):
        weather_symbols = {
            'clear': '☀️',
            'clouds': '☁️',
            'rain': '🌧️',
            'snow': '❄️',
            'thunderstorm': '⛈️',
            'mist': '🌫️'
        }
        for key in weather_symbols:
            if key in description.lower():
                return weather_symbols[key]
        return '🌡️'

    def calculate_distance(self, lat1, lon1, lat2, lon2):
        R = 6371  # Earth's radius in kilometers

        lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
        dlat = lat2 - lat1
        dlon = lon2 - lon1

        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        c = 2 * atan2(sqrt(a), sqrt(1-a))
        distance = R * c

        return distance

    def get_city_coordinates(self, city):
        params = {
            'q': city,
            'limit': 1,
            'appid': self.api_key
        }
        
        response = requests.get(self.geo_url, params=params)
        response.raise_for_status()
        data = response.json()
        
        if data:
            return {
                'lat': data[0]['lat'],
                'lon': data[0]['lon']
            }
        return None

    def get_nearest_cities(self, lat, lon):
        nearby_cities_url = f"http://api.openweathermap.org/data/2.5/find"
        params = {
            'lat': lat,
            'lon': lon,
            'cnt': 10,
            'appid': self.api_key,
            'units': 'metric'
        }
        
        response = requests.get(nearby_cities_url, params=params)
        response.raise_for_status()
        data = response.json()
        
        cities = []
        for city in data['list']:
            if self.calculate_distance(lat, lon, city['coord']['lat'], city['coord']['lon']) < 1:
                continue
                
            cities.append({
                'name': city['name'],
                'country': city['sys']['country'],
                'temp': round(city['main']['temp']),
                'temp_min': round(city['main']['temp_min']),
                'temp_max': round(city['main']['temp_max']),
                'description': city['weather'][0]['description'].capitalize(),
                'symbol': self.get_weather_symbol(city['weather'][0]['description']),
                'distance': round(self.calculate_distance(lat, lon, city['coord']['lat'], city['coord']['lon']))
            })
        
        return sorted(cities, key=lambda x: x['distance'])[:3]

    def get_weather(self, city):
        if not city.replace(' ', '').isalpha():
            return {"error": "Invalid city name. Please use only letters and spaces."}

        try:
            coords = self.get_city_coordinates(city)
            if not coords:
                return {"error": "City not found"}

            nearest_cities = self.get_nearest_cities(coords['lat'], coords['lon'])

            params = {
                'q': city,
                'appid': self.api_key,
                'units': 'metric',
                'cnt': 7
            }
            
            response = requests.get(self.base_url, params=params)
            response.raise_for_status()
            
            data = response.json()
            
            daily_forecasts = []
            for day in data['list']:
                forecast = {
                    'date': datetime.fromtimestamp(day['dt']).strftime('%Y-%m-%d'),
                    'temperature': round(day['main']['temp'], 1),
                    'temp_min': round(day['main']['temp_min'], 1),
                    'temp_max': round(day['main']['temp_max'], 1),
                    'feels_like': round(day['main']['feels_like'], 1),
                    'humidity': day['main']['humidity'],
                    'wind_speed': day['wind']['speed'],
                    'wind_direction': self.get_wind_direction(day['wind']['deg']),
                    'pressure': day['main']['pressure'],
                    'description': day['weather'][0]['description'].capitalize(),
                    'symbol': self.get_weather_symbol(day['weather'][0]['description']),
                    'precipitation_chance': round(day.get('pop', 0) * 100)
                }
                daily_forecasts.append(forecast)
            
            return {
                'city': data['city']['name'],
                'country': data['city']['country'],
                'sunrise': datetime.fromtimestamp(data['city']['sunrise']).strftime('%H:%M'),
                'sunset': datetime.fromtimestamp(data['city']['sunset']).strftime('%H:%M'),
                'forecasts': daily_forecasts,
                'nearest_cities': nearest_cities
            }
            
        except requests.exceptions.RequestException as e:
            return {"error": f"Error fetching weather data: {str(e)}"}
        except Exception as e:
            return {"error": f"An unexpected error occurred: {str(e)}"}

# Initialize WeatherApp
weather_app = WeatherApp("e8acb1e23bea72fbf433c3e2b553d6c2")

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/landing')
def landing():
    return render_template('landing.html')  # This will be your search page

@app.route('/results')
def results():
    return render_template('single.html')

@app.route('/get_weather', methods=['POST'])
def get_weather():
    city = request.json.get('city', '')
    if not city:
        return jsonify({"error": "Please provide a city name"})
    
    weather_data = weather_app.get_weather(city)
    return jsonify(weather_data)

if __name__ == '__main__':
    app.run(debug=True)