from dataclasses import dataclass

from src.configs.config import Config
from src.modules.agent.ports.output.model_factory import IModelFactory
from src.modules.agent.ports.output.workflow_store import IWorkflowStore
from src.modules.research.ports.output import IPageExtractor, ISearchProvider
from src.modules.diagrams.ports.output.diagram_renderer import IDiagramRenderer
from src.modules.styles.ports.output import IEmbeddingService, IVectorStore


@dataclass(frozen=True)
class WorkflowDeps:
    store: IWorkflowStore
    models: IModelFactory
    search: ISearchProvider
    extractor: IPageExtractor
    settings: Config
    vector_store: IVectorStore | None = None
    embeddings: IEmbeddingService | None = None
    renderer: IDiagramRenderer | None = None
