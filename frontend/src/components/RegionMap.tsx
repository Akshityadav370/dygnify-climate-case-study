import { useEffect, useState } from 'react'
import { CircleMarker, MapContainer, Rectangle, TileLayer, useMap, useMapEvents } from 'react-leaflet'
import type { LatLng } from 'leaflet'
import type { Bounds, Region } from '../api/types'
import { boundsFrom, wrapLon } from '../lib/region'

type Props = {
  region: Region | null
  mode: 'city' | 'state' | 'box'
  onPoint: (lat: number, lon: number) => void
  onBox: (bounds: Bounds) => void
}

function FitToRegion({ region }: { region: Region | null }) {
  const map = useMap()
  useEffect(() => {
    if (!region) return
    if (region.type === 'point') map.setView([region.lat, region.lon], Math.max(map.getZoom(), 6))
    else map.fitBounds([[region.south, region.west], [region.north, region.east]], { padding: [20, 20] })
  }, [region, map])
  return null
}

function ClickToPoint({ onPoint }: { onPoint: Props['onPoint'] }) {
  useMapEvents({
    click(e) {
      onPoint(Math.round(e.latlng.lat * 100) / 100, Math.round(wrapLon(e.latlng.lng) * 100) / 100)
    },
  })
  return null
}

function BoxDrawer({ onBox }: { onBox: Props['onBox'] }) {
  const map = useMap()
  const [start, setStart] = useState<LatLng | null>(null)
  const [current, setCurrent] = useState<LatLng | null>(null)

  useEffect(() => {
    map.dragging.disable()
    map.getContainer().style.cursor = 'crosshair'
    return () => {
      map.dragging.enable()
      map.getContainer().style.cursor = ''
    }
  }, [map])

  useMapEvents({
    mousedown(e) { setStart(e.latlng); setCurrent(e.latlng) },
    mousemove(e) { if (start) setCurrent(e.latlng) },
    mouseup(e) {
      if (!start) return
      const bounds = boundsFrom(start, e.latlng)
      setStart(null)
      setCurrent(null)
      if (bounds.north - bounds.south > 0.01 && bounds.east - bounds.west > 0.01) onBox(bounds)
    },
  })

  if (!start || !current) return null
  return <Rectangle bounds={[[start.lat, start.lng], [current.lat, current.lng]]} pathOptions={{ dashArray: '4' }} />
}

export function RegionMap({ region, mode, onPoint, onBox }: Props) {
  return (
    <MapContainer center={[20, 0]} zoom={2} minZoom={2} className="map" worldCopyJump>
      <TileLayer
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
      />
      {region?.type === 'point' && <CircleMarker center={[region.lat, region.lon]} radius={8} />}
      {region?.type === 'box' && <Rectangle bounds={[[region.south, region.west], [region.north, region.east]]} />}
      <FitToRegion region={region} />
      {mode === 'box' ? <BoxDrawer onBox={onBox} /> : <ClickToPoint onPoint={onPoint} />}
    </MapContainer>
  )
}
