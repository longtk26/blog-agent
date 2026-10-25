import os
import sys
from pathlib import Path

# Ensure api root is on PYTHONPATH
API_ROOT = Path(__file__).resolve().parents[4]
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

import yaml

from src.configs import config
from src.configs.logger import get_logger

logger = get_logger(__name__)
DATASET_PATH = API_ROOT / "evals" / "dataset.yaml"
DATASET_NAME = "blog-agent-eval"


def sync_dataset() -> int:
    if not DATASET_PATH.exists():
        print(f"Dataset file not found: {DATASET_PATH}", file=sys.stderr)
        return 1

    with open(DATASET_PATH, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    examples = data.get("examples", [])
    if not examples:
        print("No examples found in dataset.yaml", file=sys.stderr)
        return 1

    print(f"Loaded {len(examples)} examples from {DATASET_PATH.name}")

    if not config.langsmith_api_key:
        print("LANGSMITH_API_KEY is not configured. Dataset parsed and validated successfully (offline mode).")
        return 0

    try:
        from langsmith import Client

        client = Client(
            api_key=config.langsmith_api_key.get_secret_value(),
            api_url=config.langsmith_endpoint,
        )

        # Get or create dataset
        dataset = None
        for ds in client.list_datasets(dataset_name=DATASET_NAME):
            if ds.name == DATASET_NAME:
                dataset = ds
                break

        if dataset is None:
            dataset = client.create_dataset(
                dataset_name=DATASET_NAME,
                description="Evaluation dataset for blog-agent (Epic 9 quality benchmark)",
            )
            print(f"Created new LangSmith dataset: {DATASET_NAME} (id: {dataset.id})")
        else:
            print(f"Found existing LangSmith dataset: {DATASET_NAME} (id: {dataset.id})")

        # Get existing examples to avoid duplicates
        existing_examples = {
            (ex.metadata or {}).get("example_id"): ex.id
            for ex in client.list_examples(dataset_id=dataset.id)
            if ex.metadata and "example_id" in ex.metadata
        }

        synced = 0
        for ex in examples:
            example_id = ex["id"]
            inputs = ex["inputs"]
            outputs = ex["reference"]
            metadata = {"example_id": example_id, "topic": inputs.get("topic")}

            if example_id in existing_examples:
                client.update_example(
                    example_id=existing_examples[example_id],
                    inputs=inputs,
                    outputs=outputs,
                    metadata=metadata,
                )
            else:
                client.create_example(
                    inputs=inputs,
                    outputs=outputs,
                    metadata=metadata,
                    dataset_id=dataset.id,
                )
            synced += 1

        print(f"Successfully synced {synced} examples to LangSmith dataset '{DATASET_NAME}'")
        return 0
    except Exception as exc:
        print(f"Failed to sync dataset to LangSmith: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(sync_dataset())
