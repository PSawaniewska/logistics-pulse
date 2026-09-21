"""
Tests for the distance logic in cleaning/clean_geography.py.
"""

import pandas as pd
import pytest

from cleaning.clean_geography import aggregate_geolocation, haversine


def test_haversine_is_zero_for_two_identical_points():
    # Arrange / Act
    result = haversine(-23.5505, -46.6333, -23.5505, -46.6333)

    # Assert
    assert result == pytest.approx(0.0)


def test_haversine_matches_a_known_distance_between_two_cities():
    # Sao Paulo -> Rio de Janeiro, roughly 360 km in a straight line
    result = haversine(-23.5505, -46.6333, -22.9068, -43.1729)

    assert result == pytest.approx(360, rel=0.01)


def test_aggregate_geolocation_returns_one_row_per_zip_prefix():
    geo = pd.DataFrame({
        "geolocation_zip_code_prefix": [1001, 1001, 1001, 2002],
        "geolocation_lat": [-23.55, -23.56, -23.57, -22.90],
        "geolocation_lng": [-46.63, -46.64, -46.65, -43.17],
    })

    result = aggregate_geolocation(geo)

    assert len(result) == 2


def test_aggregate_geolocation_ignores_a_point_outside_brazil():
    geo = pd.DataFrame({
        "geolocation_zip_code_prefix": [1001, 1001, 1001],
        "geolocation_lat": [-23.55, -23.57, 45.0],
        "geolocation_lng": [-46.63, -46.65, 121.0],
    })

    result = aggregate_geolocation(geo)

    assert result["geolocation_lat"].iloc[0] == pytest.approx(-23.56)