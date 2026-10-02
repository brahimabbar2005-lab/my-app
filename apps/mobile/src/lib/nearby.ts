/** Distance from the traveller to each destination (great-circle, km). */
export interface Point {
  lat: number;
  lng: number;
}

export function distanceKm(a: Point, b: Point): number {
  const rad = Math.PI / 180;
  const dLat = (b.lat - a.lat) * rad;
  const dLng = (b.lng - a.lng) * rad;
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(a.lat * rad) * Math.cos(b.lat * rad) * Math.sin(dLng / 2) ** 2;
  return 2 * 6371 * Math.asin(Math.sqrt(h));
}

/** Destinations nearest first, with their distance rounded to the km. */
export function byDistance<T extends Point>(from: Point, places: T[]): (T & { km: number })[] {
  return places
    .map((p) => ({ ...p, km: Math.round(distanceKm(from, p)) }))
    .sort((x, y) => x.km - y.km);
}

/** Farther than this from every destination: probably not in Morocco yet. */
export const OUTSIDE_KM = 400;
