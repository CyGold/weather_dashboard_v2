import json
import os
from datetime import datetime

import azure.functions as func
import requests

try:
    from azure.communication.email import EmailClient
except Exception:  # pragma: no cover
    EmailClient = None

app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)

OPENWEATHER_BASE_URL = "https://api.openweathermap.org/data/2.5"
ICON_MAP = {
    "01d": "☀️", "01n": "🌙",
    "02d": "⛅", "02n": "☁️",
    "03d": "☁️", "03n": "☁️",
    "04d": "☁️", "04n": "☁️",
    "09d": "🌧", "09n": "🌧",
    "10d": "🌦", "10n": "🌧",
    "11d": "⛈", "11n": "⛈",
    "13d": "❄️", "13n": "❄️",
    "50d": "🌫", "50n": "🌫",
}


def _title_case(value: str) -> str:
    return " ".join(part[:1].upper() + part[1:] for part in value.split())


def _deg_to_compass(deg):
    if not isinstance(deg, (int, float)):
        return "N/A"
    points = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
    return points[round(deg / 45) % 8]


def _build_daily_forecast(entries):
    if not entries:
        return []

    chosen = {}
    for entry in entries:
        dt = datetime.utcfromtimestamp(entry.get("dt", 0))
        day_key = dt.strftime("%Y-%m-%d")
        score = abs(dt.hour - 12)

        existing = chosen.get(day_key)
        if not existing or score < existing["score"]:
            chosen[day_key] = {"score": score, "entry": entry, "dt": dt}

    out = []
    for item in sorted(chosen.values(), key=lambda x: x["dt"])[:5]:
        weather = item["entry"].get("weather", [{}])[0]
        main = item["entry"].get("main", {})
        icon_code = weather.get("icon", "")
        out.append(
            {
                "day": item["dt"].strftime("%a"),
                "icon": ICON_MAP.get(icon_code, "⛅"),
                "hi_c": round(main.get("temp_max", main.get("temp", 0))),
                "lo_c": round(main.get("temp_min", main.get("temp", 0))),
            }
        )
    return out


def _fetch_openweather_json(path, params):
    response = requests.get(f"{OPENWEATHER_BASE_URL}/{path}", params=params, timeout=20)
    response.raise_for_status()
    return response.json()


def _weather_payload_for_city(city: str):
    api_key = os.getenv("OPENWEATHER_API_KEY", "").strip()
    if not api_key:
        raise ValueError("OPENWEATHER_API_KEY is not configured in Function App settings")

    current = _fetch_openweather_json(
        "weather",
        {"q": city, "appid": api_key, "units": "metric"},
    )

    forecast_list = []
    coord = current.get("coord", {})
    if coord.get("lat") is not None and coord.get("lon") is not None:
        forecast = _fetch_openweather_json(
            "forecast",
            {
                "lat": coord["lat"],
                "lon": coord["lon"],
                "appid": api_key,
                "units": "metric",
            },
        )
        forecast_list = forecast.get("list", [])

    weather_main = current.get("weather", [{}])[0]
    main = current.get("main", {})
    wind = current.get("wind", {})

    return {
        "city": current.get("name", city),
        "country": f"Country · {current.get('sys', {}).get('country', 'N/A')}",
        "temp_c": float(main.get("temp", 0)),
        "feels_c": float(main.get("feels_like", main.get("temp", 0))),
        "humidity": int(main.get("humidity", 0)),
        "wind_kph": round(float(wind.get("speed", 0)) * 3.6),
        "wind_dir": _deg_to_compass(wind.get("deg")),
        "condition": _title_case(weather_main.get("description", "Unknown")),
        "icon": ICON_MAP.get(weather_main.get("icon", ""), "⛅"),
        "forecast": _build_daily_forecast(forecast_list),
        "updated_at": datetime.utcnow().isoformat() + "Z",
    }


def _send_weather_email(payload, recipient_override=None):
    if EmailClient is None:
        raise RuntimeError("azure-communication-email package is not available")

    acs_conn = os.getenv("ACS_CONNECTION_STRING", "").strip()
    sender = os.getenv("ACS_EMAIL_FROM", "").strip()
    default_to = os.getenv("ACS_EMAIL_TO", "").strip()
    recipient = (recipient_override or default_to).strip()

    if not acs_conn or not sender or not recipient:
        raise ValueError("ACS_CONNECTION_STRING, ACS_EMAIL_FROM and ACS_EMAIL_TO/emailTo are required")

    body_text = (
        f"City: {payload['city']}\n"
        f"Country: {payload['country']}\n"
        f"Temperature: {payload['temp_c']} C\n"
        f"Feels Like: {payload['feels_c']} C\n"
        f"Humidity: {payload['humidity']}%\n"
        f"Wind: {payload['wind_kph']} km/h ({payload['wind_dir']})\n"
        f"Condition: {payload['condition']}\n"
        f"Updated At: {payload['updated_at']}\n"
    )

    message = {
        "senderAddress": sender,
        "recipients": {"to": [{"address": recipient}]},
        "content": {
            "subject": f"Weather Update: {payload['city']}",
            "plainText": body_text,
        },
    }

    client = EmailClient.from_connection_string(acs_conn)
    poller = client.begin_send(message)
    result = poller.result()

    status = None
    if isinstance(result, dict):
        status = result.get("status")
    else:
        status = getattr(result, "status", None)

    return {
        "sent": True,
        "to": recipient,
        "status": status or "Queued",
    }


@app.route(route="weather", methods=["GET", "POST"])
def weather(req: func.HttpRequest) -> func.HttpResponse:
    try:
        city = (req.params.get("city") or "").strip()
        send_email = (req.params.get("sendEmail") or "false").lower() == "true"
        email_to = (req.params.get("emailTo") or "").strip() or None

        if req.method == "POST":
            body = req.get_json()
            city = (body.get("city") or city or "").strip()
            send_email = bool(body.get("sendEmail", send_email))
            email_to = (body.get("emailTo") or email_to or "").strip() or None

        if not city:
            return func.HttpResponse(
                json.dumps({"error": "Missing required query/body parameter: city"}),
                mimetype="application/json",
                status_code=400,
            )

        payload = _weather_payload_for_city(city)

        if send_email:
            payload["email"] = _send_weather_email(payload, email_to)

        return func.HttpResponse(json.dumps(payload), mimetype="application/json", status_code=200)
    except requests.HTTPError as exc:
        status = exc.response.status_code if exc.response is not None else 502
        details = None
        try:
            details = exc.response.json()
        except Exception:
            details = str(exc)

        return func.HttpResponse(
            json.dumps({"error": "Weather provider request failed", "details": details}),
            mimetype="application/json",
            status_code=status,
        )
    except ValueError as exc:
        return func.HttpResponse(
            json.dumps({"error": str(exc)}),
            mimetype="application/json",
            status_code=400,
        )
    except Exception as exc:
        return func.HttpResponse(
            json.dumps({"error": "Unexpected server error", "details": str(exc)}),
            mimetype="application/json",
            status_code=500,
        )
