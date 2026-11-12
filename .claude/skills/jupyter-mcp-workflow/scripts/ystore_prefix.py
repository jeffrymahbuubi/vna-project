# Used by start-jupyter-server.ps1 / .sh via --YDocExtension.ystore_class.
# The launcher puts this folder on PYTHONPATH so jupyter_server_ydoc can import it.
#
# Why a subclass: pycrdt.store.TempFileYStore's tempfile.mkdtemp() defaults to
# the generic "tmp" prefix, indistinguishable from every other program's temp
# folders, so they could never be bulk-deleted safely. A unique prefix lets the
# launcher's cleanup step remove only the folders this server created.
#
# Checked against pycrdt-store 0.1.5 (pycrdt 0.14.4), jupyter-server-ydoc 3.0.2:
#   - TempFileYStore.__init__(self, path, metadata_callback=None, log=None); prefix_dir
#     is a class attribute read by tempfile.mkdtemp(prefix=self.prefix_dir).
#   - jupyter_server_ydoc.app.YDocExtension instantiates the configured class via
#     partial(self.ystore_class, config=self.config).
from pycrdt.store import TempFileYStore


class PrefixTempFileYStore(TempFileYStore):
    prefix_dir = "claude_jupyter_ystore_"

    def __init__(self, *args, config=None, **kwargs):
        # jupyter_server_ydoc always passes config=self.config (it assumes a
        # traitlets Configurable like its bundled SQLiteYStore). TempFileYStore
        # is a plain class with no `config` parameter, so without this override
        # every room-open crashed with "TypeError: unexpected keyword argument
        # 'config'" (HTTP 500). The MCP client then hit its 10 s sync timeout
        # silently and reported "Notebook has 0 cells".
        super().__init__(*args, **kwargs)
