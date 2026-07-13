from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GeoPoint:
    latitude: float
    longitude: float


class Geocoder:
    def geocode(self, address: str) -> GeoPoint:
        raise NotImplementedError


class ManualGeocoder(Geocoder):
    def __init__(self, latitude: float, longitude: float) -> None:
        self.point = GeoPoint(latitude=latitude, longitude=longitude)

    def geocode(self, address: str) -> GeoPoint:
        del address
        return self.point

