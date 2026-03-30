"""Chat streaming helpers: pack, replay_chat, stream_chat."""

import json
import uuid
from typing import Optional

from langchain_core.load import dumps
from langchain_core.messages import HumanMessage

from src.agents.graph import fetch_zeno, fetch_zeno_anonymous
from src.shared.logging_config import get_logger

logger = get_logger(__name__)


def pack(data: dict) -> str:
    """Serialize data as NDJSON line."""
    return json.dumps(data) + "\n"


async def replay_chat(thread_id: str):
    """
    Stream thread replay from checkpoints. Yields NDJSON lines.
    """
    config = {"configurable": {"thread_id": thread_id}}

    zeno_async = await fetch_zeno()
    checkpoints = [
        c async for c in zeno_async.aget_state_history(config=config)
    ]
    checkpoints = sorted(list(checkpoints), key=lambda x: x.metadata["step"])
    checkpoints = [c for c in checkpoints if c.metadata["step"] >= 0]

    rendered_state_elements: dict = {"messages": []}

    for checkpoint in checkpoints:
        update = {"messages": []}

        for message in checkpoint.values.get("messages", []):
            if (
                message.id in rendered_state_elements["messages"]
                or not message.content
            ):
                continue
            rendered_state_elements["messages"].append(message.id)
            update["messages"].append(message)

        for key, value in checkpoint.values.items():
            if key == "messages":
                continue
            if value in rendered_state_elements.setdefault(key, []):
                continue
            rendered_state_elements[key].append(value)
            update[key] = value

        mtypes = set(m.type for m in update["messages"])
        node_type = (
            "agent"
            if mtypes == {"ai"} or len(mtypes) > 1
            else "tools"
            if mtypes == {"tool"}
            else "human"
        )

        yield pack(
            {
                "node": node_type,
                "timestamp": checkpoint.created_at,
                "update": dumps(update),
                "checkpoint_id": checkpoint.config["configurable"][
                    "checkpoint_id"
                ],
                "thread_id": checkpoint.config["configurable"]["thread_id"],
            }
        )


async def stream_chat(
    query: str,
    user_persona: Optional[str] = None,
    ui_context: Optional[dict] = None,
    ui_action_only: Optional[bool] = False,
    thread_id: Optional[str] = None,
    trace_id: Optional[str] = None,
    user: Optional[dict] = None,
):
    """Stream chat response from agent. Yields NDJSON lines."""
    trace_id = trace_id or str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}

    if not thread_id:
        zeno_async = await fetch_zeno_anonymous(user)
    else:
        zeno_async = await fetch_zeno(user)

    messages = []
    ui_action_message = []
    state_updates = {}

    if ui_context:
        for action_type, action_data in ui_context.items():
            match action_type:
                case "aoi_selected":
                    content = f"User selected AOI in UI: {action_data['aoi_name']}\n\n"
                    state_updates["aoi"] = action_data["aoi"]
                    state_updates["aoi_name"] = action_data["aoi_name"]
                    state_updates["subregion_aois"] = action_data.get(
                        "subregion_aois", []
                    )
                    state_updates["subregion"] = action_data.get("subregion", "")
                    state_updates["subtype"] = action_data.get("subtype", "")
                    state_updates["aoi_options"] = {
                        "aoi": action_data["aoi"],
                        "subregion_aois": action_data.get("subregion_aois", []),
                        "subregion": action_data.get("subregion", ""),
                        "subtype": action_data.get("subtype", ""),
                    }
                case "data_source_selected":
                    content = f"User selected data source: {action_data.get('data_source', 'unknown')}\n\n"
                    state_updates["data_source"] = action_data.get(
                        "data_source"
                    )
                case "dataset_selected":
                    ds = action_data["dataset"]
                    name = ds.get("dataset_name", ds.get("data_layer", "dataset"))
                    content = f"User selected dataset in UI: {name}\n\n"
                    state_updates["dataset"] = action_data["dataset"]
                case "daterange_selected":
                    content = f"User selected daterange in UI: start_date: {action_data['start_date']}, end_date: {action_data['end_date']}"
                    state_updates["start_date"] = action_data["start_date"]
                    state_updates["end_date"] = action_data["end_date"]
                case _:
                    content = f"User performed action in UI: {action_type}\n\n"
            ui_action_message.append(content)

    ui_message = HumanMessage(content="\n".join(ui_action_message))
    messages.append(ui_message)

    if not ui_action_only and query:
        messages.append(HumanMessage(content=query))
    else:
        messages.append(
            HumanMessage(
                content="User performed UI action only. Acknowledge the updates and ask what they would like to do next with their selections."
            )
        )

    state_updates["messages"] = messages
    state_updates["user_persona"] = user_persona

    try:
        stream = zeno_async.astream(
            state_updates,
            config=config,
            stream_mode="updates",
            subgraphs=False,
        )

        async for update in stream:
            try:
                node = next(iter(update.keys()))
                yield pack(
                    {
                        "node": node,
                        "update": dumps(update[node]),
                    }
                )
            except Exception as e:
                logger.exception(
                    "Error processing stream update",
                    error=str(e),
                    update=update,
                )
                yield pack(
                    {
                        "node": "error",
                        "update": dumps(
                            {
                                "error": True,
                                "message": str(e),
                                "error_type": type(e).__name__,
                                "type": "stream_processing_error",
                            }
                        ),
                    }
                )
                continue

        if thread_id:
            try:
                snap = await zeno_async.aget_state(config)
                vals = getattr(snap, "values", None) or {}
                ui_payload = {
                    "geo_result_summary": vals.get("geo_result_summary"),
                    "map_actions": vals.get("map_actions"),
                    "charts_data": vals.get("charts_data"),
                }
                yield pack(
                    {
                        "node": "ui_state",
                        "update": dumps(ui_payload),
                    }
                )
            except Exception as e:
                logger.warning(
                    "ui_state_snapshot_failed",
                    error=str(e),
                    thread_id=thread_id,
                )

        yield pack(
            {
                "node": "trace_info",
                "update": dumps({"trace_id": trace_id}),
            }
        )

    except Exception as e:
        logger.exception("Error during chat streaming: %s", e)
        yield pack(
            {
                "node": "error",
                "update": dumps(
                    {
                        "error": True,
                        "message": str(e),
                        "error_type": type(e).__name__,
                        "type": "stream_initialization_error",
                        "fatal": True,
                    }
                ),
            }
        )
