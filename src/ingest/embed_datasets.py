from pathlib import Path

from langchain_core.documents import Document
from langchain_core.vectorstores import InMemoryVectorStore
from langchain_google_genai import GoogleGenerativeAIEmbeddings

import src.shared.env  # noqa: F401
from src.agents.tools.datasets_config import DATASETS
from src.shared.config import SharedSettings

embeddings = GoogleGenerativeAIEmbeddings(
    model=SharedSettings.dataset_embeddings_model,
    task_type="RETRIEVAL_DOCUMENT",
)
index = InMemoryVectorStore(embeddings)

data_dir = Path("data").absolute()

analytics_docs = []

for ds in DATASETS:
    content = {
        "DATA_LAYER": ds["dataset_name"],
        "DESCRIPTION": ds["description"],
        "CONTEXTUAL_LAYERS": ds["context_layers"],
        "DATE": ds["content_date"],
        "USAGE NOTES": ds["function_usage_notes"],
    }

    formatted_content = "\n\n".join(
        [
            f"{key}\n{value}"
            for key, value in content.items()
            if value is not None
        ]
    )

    analytics_docs.append(
        Document(
            id=ds["dataset_id"],
            page_content=formatted_content,
        )
    )

index.add_documents(documents=analytics_docs)

index.dump(data_dir / SharedSettings.dataset_embeddings_db)
