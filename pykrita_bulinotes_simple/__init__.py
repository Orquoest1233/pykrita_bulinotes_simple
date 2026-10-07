# -----------------------------------------------------------------------------
# Buli Notes Simple - Main entry
# Punto de entrada del plugin. Registra el docker en Krita.
# -----------------------------------------------------------------------------
from krita import Krita, DockWidgetFactory, DockWidgetFactoryBase
from .docker import BuliNotesDocker

# Metadatos (Krita los lee para el listado de plugins)
__version__ = "1.1.0"

DOCKER_ID = "bulinotes_simple_dock"

instance = Krita.instance()
dock_factory = DockWidgetFactory(
    DOCKER_ID,
    DockWidgetFactoryBase.DockRight,
    BuliNotesDocker
)
instance.addDockWidgetFactory(dock_factory)