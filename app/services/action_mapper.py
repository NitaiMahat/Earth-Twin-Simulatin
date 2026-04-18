from __future__ import annotations

from app.models.domain.action import ActionType


ACTION_TYPE_MAPPING: dict[str, ActionType] = {
    ActionType.DEFORESTATION.value: ActionType.DEFORESTATION,
    ActionType.TRAFFIC_INCREASE.value: ActionType.TRAFFIC_INCREASE,
    ActionType.POLLUTION_SPIKE.value: ActionType.POLLUTION_SPIKE,
    ActionType.RESTORATION.value: ActionType.RESTORATION,
    "reduce_green_space": ActionType.DEFORESTATION,
    "expand_roadway": ActionType.TRAFFIC_INCREASE,
    "industrial_expansion": ActionType.POLLUTION_SPIKE,
    "add_urban_park": ActionType.RESTORATION,
    # For the hackathon build we route transit improvements through the
    # beneficial restoration rule until a dedicated transit rule is added.
    "improve_public_transit": ActionType.RESTORATION,
    "restoration_corridor": ActionType.RESTORATION,
    "cut_trees": ActionType.DEFORESTATION,
    "increase_traffic": ActionType.TRAFFIC_INCREASE,
    "increase_pollution": ActionType.POLLUTION_SPIKE,
    "restore_ecosystem": ActionType.RESTORATION,
}


class ActionMapper:
    def normalize_action_type(self, action_type: str) -> ActionType:
        normalized_key = action_type.strip().lower()
        normalized_action = ACTION_TYPE_MAPPING.get(normalized_key)
        if normalized_action is None:
            supported_actions = ", ".join(sorted(ACTION_TYPE_MAPPING))
            raise ValueError(f"Unsupported action_type '{action_type}'. Supported values: {supported_actions}.")
        return normalized_action

    def list_supported_action_types(self) -> list[str]:
        return sorted(ACTION_TYPE_MAPPING)


action_mapper = ActionMapper()
