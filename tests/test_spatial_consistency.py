from __future__ import annotations

import numpy as np
import pandas as pd

from aoe2stat.spatial import (
    build_perspective_spatial_frames,
    normalize_coordinates,
    overlay_player_layers,
    spatial_frames_to_tensor,
)


def _base_events(rows):
    return pd.DataFrame(rows, columns=["match_id", "time_sec", "player_id", "x", "y", "event_type_semantic", "action_family"])


def test_normalize_coordinates_bounds():
    df = _base_events(
        [
            ("m1", 1.0, 1, -10.0, -5.0, "unit_train", "production"),
            ("m1", 2.0, 1, 60.0, 30.0, "unit_train", "production"),
            ("m1", 3.0, 2, 130.0, 200.0, "unit_train", "production"),
        ]
    )
    out = normalize_coordinates(df, map_dimension=120.0)
    assert (out["x_norm"] >= 0.0).all() and (out["x_norm"] <= 1.0).all()
    assert (out["y_norm"] >= 0.0).all() and (out["y_norm"] <= 1.0).all()


def test_spatial_scaling_invariance_cells():
    # Same relative positions on different map dimensions should map to same cells.
    a = _base_events([("m1", 1.0, 1, 30.0, 90.0, "unit_train", "production")])
    b = _base_events([("m1", 1.0, 1, 60.0, 180.0, "unit_train", "production")])
    fa = build_perspective_spatial_frames(a, map_dimension=120.0, grid_size=16, window_sec=10)
    fb = build_perspective_spatial_frames(b, map_dimension=240.0, grid_size=16, window_sec=10)
    sa = fa[fa["channel"] == "own_units"][["cell_x", "cell_y"]].iloc[0].to_dict()
    sb = fb[fb["channel"] == "own_units"][["cell_x", "cell_y"]].iloc[0].to_dict()
    assert sa == sb


def test_spatial_border_cells_and_overlay_layers():
    df = _base_events(
        [
            ("m1", 1.0, 1, 0.0, 0.0, "unit_train", "production"),
            ("m1", 1.0, 2, 119.9, 119.9, "unit_train", "production"),
        ]
    )
    frames = build_perspective_spatial_frames(df, map_dimension=120.0, grid_size=16, window_sec=10)
    own1 = frames[(frames["player_id"] == 1) & (frames["channel"] == "own_units")].iloc[0]
    own2 = frames[(frames["player_id"] == 2) & (frames["channel"] == "own_units")].iloc[0]
    assert int(own1["cell_x"]) == 0 and int(own1["cell_y"]) == 0
    assert int(own2["cell_x"]) == 15 and int(own2["cell_y"]) == 15

    overlay = overlay_player_layers(frames, player_a=1, player_b=2, channel="own_units")
    assert set(overlay["layer"].unique().tolist()) == {"A", "B"}
    assert set(overlay["player_id"].unique().tolist()) == {1, 2}


def test_tensor_has_expected_shape_and_channels():
    df = _base_events(
        [
            ("m1", 1.0, 1, 10.0, 10.0, "unit_train", "production"),
            ("m1", 11.0, 2, 20.0, 20.0, "unit_train", "production"),
            ("m1", 11.0, 1, 40.0, 40.0, "building_build", "build"),
            ("m1", 11.0, 2, 50.0, 50.0, "other", "military"),
        ]
    )
    frames = build_perspective_spatial_frames(df, map_dimension=120.0, grid_size=8, window_sec=10)
    tensor, meta = spatial_frames_to_tensor(frames, player_id=1)
    assert tensor.ndim == 4
    assert tensor.shape[1] == 5
    assert tensor.shape[2] == 8 and tensor.shape[3] == 8
    assert meta["channels"] == ["own_units", "enemy_units", "buildings", "combat", "risk_proxy"]


def test_spatial_symmetry_mirror_x():
    # Mirror over X axis: x and (D-x) should map to mirrored cell_x.
    D = 120.0
    n = 16
    x = 15.0
    xm = D - x
    df = _base_events(
        [
            ("m1", 1.0, 1, x, 30.0, "unit_train", "production"),
            ("m1", 1.0, 1, xm, 30.0, "unit_train", "production"),
        ]
    )
    frames = build_perspective_spatial_frames(df, map_dimension=D, grid_size=n, window_sec=10)
    own = frames[(frames["player_id"] == 1) & (frames["channel"] == "own_units")]
    xs = sorted(own["cell_x"].unique().tolist())
    assert len(xs) == 2
    # Approx mirror around grid center with integer discretization tolerance.
    assert abs((xs[0] + xs[1]) - (n - 1)) <= 1

