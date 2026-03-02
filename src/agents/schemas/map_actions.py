from typing import Literal, TypedDict


class ZoomToAction(TypedDict):
    type: Literal["zoomTo"]
    geometry: dict


class AddBoundaryLayerAction(TypedDict):
    type: Literal["addBoundaryLayer"]
    geojson: dict
    label: str
    style: dict


class AddFeatureLayerAction(TypedDict):
    type: Literal["addFeatureLayer"]
    geojson: dict
    label: str
    colorByField: str | None
    colorPalette: list[str] | None
    style: dict | None


MapAction = ZoomToAction | AddBoundaryLayerAction | AddFeatureLayerAction
