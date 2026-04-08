 // ─────────────────────────────────────────────
  //  MOCK DATA  (swap fetchWeather() with your
  //  Azure Function call when ready)
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

  // ─────────────────────────────────────────────
  //  REPLACE THIS with your real Azure Function
  //  e.g. const res = await fetch(`https://<fn>.azurewebsites.net/api/weather?city=${city}`);
  //       return await res.json();
  // ─────────────────────────────────────────────
  async function fetchWeather(city) {
    // Simulated network delay
    await new Promise(r => setTimeout(r, 600));
    // Return mock — replace with real fetch ↑
    return { ...MOCK, city: city || MOCK.city };
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
    const days = ['Sun','Mon','Tue','Wed','Thu','Fri','Sat'];
    const todayName = days[new Date().getDay()];
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
      err.textContent = 'Could not load weather data.';
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