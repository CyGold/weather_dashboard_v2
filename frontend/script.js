 // ─────────────────────────────────────────────
  //  FRONTEND WEATHER MODE (Azure Function API)
  // ─────────────────────────────────────────────
  const MOCK = {
    city: "Lagos", country: "Nigeria · NG",
    temp_c: 28, feels_c: 31, humidity: 74,
    wind_kph: 18, wind_dir: "SW",
    condition: "Partly Cloudy", icon: "⛅",
    forecast: [
      { day: "Mon", icon: "☀️", hi_c: 31, lo_c: 24 },
      { day: "Tue", icon: "🌦", hi_c: 29, lo_c: 23 },
      { day: "Wed", icon: "🌧", hi_c: 26, lo_c: 22 },
      { day: "Thu", icon: "⛅", hi_c: 30, lo_c: 24 },
      { day: "Fri", icon: "☀️", hi_c: 32, lo_c: 25 },
    ]
  };

  const WEATHER_API_BASE = (window.WEATHER_API_BASE || '').trim() || '/api';

  const iconMap = {
    '01d': '☀️', '01n': '🌙',
    '02d': '⛅', '02n': '☁️',
    '03d': '☁️', '03n': '☁️',
    '04d': '☁️', '04n': '☁️',
    '09d': '🌧', '09n': '🌧',
    '10d': '🌦', '10n': '🌧',
    '11d': '⛈', '11n': '⛈',
    '13d': '❄️', '13n': '❄️',
    '50d': '🌫', '50n': '🌫'
  };

  async function fetchJsonOrThrow(url, errorPrefix) {
    const res = await fetch(url);
    const payload = await res.json().catch(() => ({}));
    if (!res.ok) {
      const reason = payload.message || `HTTP ${res.status}`;
      throw new Error(`${errorPrefix}: ${reason}`);
    }
    return payload;
  }

  async function fetchWeather(city) {
    const query = (city || MOCK.city).trim();
    const apiUrl = `${WEATHER_API_BASE}/weather?city=${encodeURIComponent(query)}`;
    const payload = await fetchJsonOrThrow(apiUrl, 'Weather API request failed');

    return {
      ...MOCK,
      ...payload,
      icon: iconMap[payload.icon] || payload.icon || MOCK.icon,
      forecast: Array.isArray(payload.forecast) && payload.forecast.length
        ? payload.forecast.map((f, i) => ({
            day: f.day || ['Mon', 'Tue', 'Wed', 'Thu', 'Fri'][i % 5],
            icon: iconMap[f.icon] || f.icon || '⛅',
            hi_c: Number.isFinite(f.hi_c) ? f.hi_c : MOCK.forecast[i % 5].hi_c,
            lo_c: Number.isFinite(f.lo_c) ? f.lo_c : MOCK.forecast[i % 5].lo_c
          }))
        : MOCK.forecast
    };
  }

  // ─────────────────────────────────────────────
  //  STATE
  // ─────────────────────────────────────────────
  let isCelsius = true;
  let data = null;

  const toF = c => Math.round(c * 9 / 5 + 32);
  const fmt = c => isCelsius ? Math.round(c) : toF(c);
  const unit = () => isCelsius ? '°C' : '°F';

  // ─────────────────────────────────────────────
  //  RENDER
  // ─────────────────────────────────────────────
  function render(d) {
    data = d;

    document.getElementById('cityName').textContent = d.city;
    document.getElementById('countryName').textContent = d.country;
    document.getElementById('tempVal').textContent = fmt(d.temp_c);
    document.getElementById('unitToggle').textContent = unit();
    document.getElementById('condIcon').textContent = d.icon;
    document.getElementById('condText').textContent = d.condition;
    document.getElementById('feelsVal').textContent = fmt(d.feels_c) + '°';
    document.getElementById('humidVal').textContent = d.humidity + '%';
    document.getElementById('windVal').textContent = d.wind_kph;
    document.getElementById('windSub').textContent = `km/h · ${d.wind_dir}`;

    // Forecast
    const row = document.getElementById('forecastRow');
    row.innerHTML = d.forecast.map((f, i) => `
      <div class="fc-day ${i === 0 ? 'today' : ''}">
        <span class="fc-name">${i === 0 ? 'Now' : f.day}</span>
        <span class="fc-icon">${f.icon}</span>
        <span class="fc-hi">${fmt(f.hi_c)}°</span>
        <span class="fc-lo">${fmt(f.lo_c)}°</span>
      </div>`).join('');
  }

  // ─────────────────────────────────────────────
  //  LOAD
  // ─────────────────────────────────────────────
  async function load(city) {
    const bar = document.getElementById('statusBar');
    const err = document.getElementById('errorMsg');
    bar.style.width = '55%';
    err.textContent = '';
    try {
      const d = await fetchWeather(city);
      render(d);
      bar.style.width = '100%';
      setTimeout(() => bar.style.width = '0', 400);
    } catch (e) {
      err.textContent = e?.message || 'Could not load weather data.';
      bar.style.width = '0';
    }
  }

  // ─────────────────────────────────────────────
  //  CLOCK
  // ─────────────────────────────────────────────
  function tick() {
    const now = new Date();
    document.getElementById('clock').textContent =
      now.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: false });
    document.getElementById('dateLine').textContent =
      now.toLocaleDateString('en-US', { weekday: 'short', day: 'numeric', month: 'short', year: 'numeric' }).toUpperCase();
  }
  tick(); setInterval(tick, 30000);

  // ─────────────────────────────────────────────
  //  EVENTS
  // ─────────────────────────────────────────────
  document.getElementById('unitToggle').addEventListener('click', () => {
    isCelsius = !isCelsius;
    if (data) render(data);
  });

  document.getElementById('searchBtn').addEventListener('click', () => {
    const q = document.getElementById('searchInput').value.trim();
    if (q) load(q);
  });

  document.getElementById('searchInput').addEventListener('keydown', e => {
    if (e.key === 'Enter') {
      const q = e.target.value.trim();
      if (q) load(q);
    }
  });

  // Init
  load();