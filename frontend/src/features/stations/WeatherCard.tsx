import type { Weather } from '@/api/schemas'
import { Card } from '@/components/ui/Card'

const oneDecimal = new Intl.NumberFormat('en-IN', { maximumFractionDigits: 1, minimumFractionDigits: 1 })

function Reading({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-13 text-ink-muted">{label}</p>
      <p className="font-mono text-22">{value}</p>
    </div>
  )
}

/** Weather at the station, or a plain explanation for stations without sensors. */
export function WeatherCard({ weather }: { weather: Weather | null }) {
  return (
    <Card as="section" aria-labelledby="weather-title" className="flex min-w-0 flex-[1_1_300px] flex-col gap-3.5 px-5 py-6 md:px-7">
      <h2 id="weather-title" className="text-17 font-semibold">
        Weather at the station
      </h2>
      {weather ? (
        <div className="grid grid-cols-2 gap-4">
          <Reading label="Temperature" value={weather.temperatureC === null ? '—' : `${oneDecimal.format(weather.temperatureC)} °C`} />
          <Reading label="Wind" value={weather.windMs === null ? '—' : `${oneDecimal.format(weather.windMs)} m/s`} />
          <Reading label="Humidity" value={weather.humidityPct === null ? '—' : `${Math.round(weather.humidityPct)}%`} />
          <Reading label="Solar radiation" value={weather.solarWm2 === null ? '—' : `${Math.round(weather.solarWm2)} W/m²`} />
        </div>
      ) : (
        <p className="text-ink-2">
          No weather readings for this station right now. Some stations (ITO) have no weather sensors, and the forecast models do not use filled-in weather.
        </p>
      )}
      <p className="mt-auto border-t border-line-soft pt-3 text-13 text-ink-muted">
        Calm wind and cold nights trap particles near the ground.
      </p>
    </Card>
  )
}
