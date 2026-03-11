# flake8: noqa: E402
import warnings
import traceback
import logging
import mimetypes
import argparse
import sys
import os
import gettext
import asyncio
from pathlib import Path
from rayforge.logging_setup import setup_logging

# ===================================================================
# SECTION 1: SAFE, MODULE-LEVEL SETUP
# This code will run for the main app AND all subprocesses.
# ===================================================================

logger = logging.getLogger(__name__)


# Suppress NumPy longdouble UserWarning when run under mingw on Windows
warnings.filterwarnings(
    "ignore",
    message="Signature.*for <class 'numpy.longdouble'> does not"
    " match any known type",
)

# Gettext MUST be initialized before importing app modules.
# This MUST run at the module level so that the `_` function is
# available to any module (in any process) that gets imported.
if hasattr(sys, "_MEIPASS"):
    # In a PyInstaller bundle, the project root is in a temporary
    # directory stored in sys._MEIPASS.
    base_dir = Path(sys._MEIPASS)  # type: ignore
else:
    # In other environments, this is safer.
    base_dir = Path(__file__).parent.parent

# Make "_" available in all modules
locale_dir = base_dir / "rayforge" / "locale"
logging.getLogger().setLevel(logging.DEBUG)
logger.debug(f"Loading locales from {locale_dir}")
gettext.install("rayforge", locale_dir)

# --------------------------------------------------------
# GObject Introspection Repository (gi)
# --------------------------------------------------------
# When running in a PyInstaller bundle, we need to set the GI_TYPELIB_PATH
# environment variable to point to the bundled typelib files.
if hasattr(sys, "_MEIPASS"):
    typelib_path = base_dir / "gi" / "repository"
    logger.info(f"GI_TYPELIB_PATH is {typelib_path}")
    os.environ["GI_TYPELIB_PATH"] = str(typelib_path)
    files = [p.name for p in typelib_path.iterdir()]
    logger.info(f"Files in typelib path: {files}")


def handle_exception(exc_type, exc_value, exc_traceback):
    """
    Catches unhandled exceptions, logs them, and shows a user-friendly dialog.
    This is crucial for --noconsole builds.
    """
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return

    # Print full traceback to stderr (console or log)
    traceback.print_exception(exc_type, exc_value, exc_traceback)

    logger.error(
        "Unhandled exception", exc_info=(exc_type, exc_value, exc_traceback)
    )
    logging.shutdown()


def main():
    # ===================================================================
    # SECTION 2: MAIN APPLICATION ENTRY POINT
    # This function contains all logic that should ONLY run in the
    # main process.
    # ===================================================================

    # Set the global exception handler.
    sys.excepthook = handle_exception

    # We need Adw for the class definition, so this one import is okay here.
    import gi

    gi.require_version("Adw", "1")
    from gi.repository import Adw, GLib
    from rayforge.context import get_context

    class App(Adw.Application):
        def __init__(self, args):
            super().__init__(application_id="org.rayforge.rayforge")
            self.set_accels_for_action("win.quit", ["<Ctrl>Q"])
            self.args = args
            self.win = None

        def do_activate(self):
            # Import the window here to avoid module-level side-effects
            from rayforge.ui_gtk.mainwindow import MainWindow

            self.win = MainWindow(application=self)

            if self.args.output or self.args.headless:
                # Non-interactive path: skip window presentation and
                # load files (if any) directly via an idle callback.
                if self.args.filenames:
                    GLib.idle_add(self._load_initial_files, None)
                elif self.args.output:
                    # No input files — run export on empty document.
                    GLib.idle_add(self._headless_export_and_quit)
            else:
                # Normal interactive path.
                if self.args.filenames:
                    self.win.connect("map", self._load_initial_files)
                self.win.present()

            # Now that the UI is active, trigger the initial machine connections.
            context = get_context()
            if context.machine_mgr:
                context.machine_mgr.initialize_connections()

        def _load_initial_files(self, widget):
            """
            Loads files passed via the command line. This is called from the
            'map' signal handler to ensure the main window is fully initialized.
            """
            from rayforge.core.vectorization_spec import TraceSpec

            assert self.win is not None
            for filename in self.args.filenames:
                mime_type, _ = mimetypes.guess_type(filename)
                vectorization_spec = (
                    None if self.args.direct_vector else TraceSpec()
                )
                self.win.doc_editor.file.load_file_from_path(
                    filename=Path(filename),
                    mime_type=mime_type,
                    vectorization_spec=vectorization_spec,
                )

            if self.args.output:
                editor = self.win.doc_editor

                def _on_settled(sender, **kwargs):
                    editor.document_settled.disconnect(_on_settled)
                    self._headless_export_and_quit()

                editor.document_settled.connect(_on_settled)

            return GLib.SOURCE_REMOVE  # ensure this handler only runs once

        def _headless_export_and_quit(self):
            """
            Assembles the job G-code, writes it to --output, then quits.
            """
            from rayforge.context import get_context

            assert self.win is not None
            artifact_store = get_context().artifact_store
            output_path = Path(self.args.output)

            def when_done(handle, error):
                try:
                    if error:
                        logger.error(
                            "Headless export failed: %s",
                            error,
                            exc_info=error,
                        )
                        return
                    if not handle:
                        logger.error(
                            "Headless export: pipeline returned no artifact."
                        )
                        return
                    from rayforge.core.artifact import JobArtifact

                    artifact = artifact_store.get(handle)
                    if not isinstance(artifact, JobArtifact):
                        logger.error(
                            "Headless export: unexpected artifact type."
                        )
                        return
                    if artifact.machine_code_bytes is None:
                        logger.error(
                            "Headless export: artifact contains no G-code."
                        )
                        return
                    gcode_str = (
                        artifact.machine_code_bytes.tobytes().decode("utf-8")
                    )
                    output_path.write_text(gcode_str, encoding="utf-8")
                    logger.info(
                        "Headless: G-code exported to %s", output_path
                    )
                except Exception as e:
                    logger.error(
                        "Headless export to %s failed.",
                        output_path,
                        exc_info=e,
                    )
                finally:
                    if handle:
                        artifact_store.release(handle)
                    GLib.idle_add(self.quit)

            self.win.doc_editor.file.assemble_job_in_background(
                when_done=when_done
            )

    # Import version for the --version flag.
    from rayforge import __version__

    parser = argparse.ArgumentParser(
        description=_("A GCode generator for laser cutters.")
    )
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__}"
    )
    parser.add_argument(
        "filenames",
        help=_("Paths to one or more input SVG or image files."),
        nargs="*",
    )
    parser.add_argument(
        "--direct-vector",
        action="store_true",
        help=_("Import SVG files as direct vectors instead of tracing them."),
    )
    parser.add_argument(
        "--loglevel",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help=_("Set the logging level (default: INFO)"),
    )
    parser.add_argument(
        "--output",
        metavar="PATH",
        help=_(
            "Export generated G-code to PATH and exit"
            " (requires one or more input files)."
        ),
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help=_(
            "Run without showing the GUI window."
            " Combine with --output to export G-code non-interactively."
        ),
    )

    args = parser.parse_args()

    # Set logging level based on the command-line argument.
    setup_logging(args.loglevel)
    logger.info(f"Application starting with log level {args.loglevel.upper()}")

    # ===================================================================
    # SECTION 3: PLATFORM SPECIFIC INITIALIZATION
    # ===================================================================

    # When running on Windows, spawned subprocesses do not
    # know where to find the necessary DLLs (for cairo, rsvg, etc.).
    # We must explicitly add the executable's directory to the
    # DLL search path *before* any subprocesses are created.
    # This must be done inside the main() guard.
    if sys.platform == "win32":
        logger.info(
            f"Windows build detected. Adding '{base_dir}' to DLL search path."
        )
        os.add_dll_directory(str(base_dir))

    # Set the PyOpenGL platform before importing anything that uses OpenGL.
    # 'egl' is generally the best choice for GTK4 on modern Linux (Wayland/X11).
    # On Windows and macOS, letting PyOpenGL auto-detect is more reliable.
    if sys.platform.startswith("linux"):
        logger.info("Linux detected. Setting PYOPENGL_PLATFORM=egl")
        os.environ.setdefault("PYOPENGL_PLATFORM", "egl")

    # Print PyCairo version
    import cairo

    logger.info(f"PyCairo version: {cairo.version}")

    # Register the standalone 'cairo' module
    # as a foreign type *before* the GObject-introspected cairo is loaded.
    gi.require_foreign("cairo")

    # Now, when gi.repository.cairo is loaded, it will know how to
    # interact with the already-imported standalone module.
    gi.require_version("cairo", "1.0")
    gi.require_version("Gtk", "4.0")
    gi.require_version("GdkPixbuf", "2.0")

    # Initialize the 3D canvas module to check for OpenGL availability.
    # This must be done after setting the platform env var and after
    # making Gtk available in gi, as the canvas uses Gtk.
    # The rest of the app can now check `rayforge.canvas3d.initialized`.
    # It is safe to import other modules that depend on canvas3d after this.
    from rayforge.ui_gtk import canvas3d

    canvas3d.initialize()

    # Import modules that depend on GTK or manage global state
    import rayforge.shared.tasker

    # Initialize the full application context. This creates all managers
    # and sets up the backward-compatibility shim for old code.
    get_context().initialize_full_context()

    # Run application
    app = App(args)
    exit_code = app.run(None)
    assert app.win is not None

    # ===================================================================
    # SECTION 4: SHUTDOWN SEQUENCE
    # ===================================================================

    logger.info("Application exiting.")
    context = get_context()

    # 1. Define an async function to shut down high-level components.
    async def shutdown_async():
        logger.info("Starting graceful async shutdown...")
        # The context now handles shutting down all its owned managers
        # (machine_mgr, camera_mgr, artifact_store) in the correct order.
        await context.shutdown()
        logger.info("Async shutdown complete.")

    # 2. Run the async shutdown on the TaskManager's event loop and wait for it.
    loop = rayforge.shared.tasker.task_mgr.loop
    if loop.is_running():
        logger.info(f"Running async shutdown on loop {loop}...")
        future = asyncio.run_coroutine_threadsafe(shutdown_async(), loop)
        try:
            # Block until the async cleanup is finished.
            future.result(timeout=10)
        except Exception as e:
            logger.error(f"Error during graceful shutdown: {e}")
    else:
        logger.warning(
            "Task manager loop not running, skipping async shutdown."
        )

    # 3. Save configuration. This happens AFTER async tasks are done.
    logger.info("Saving configuration")
    if context.config_mgr:
        context.config_mgr.save()
        logger.info("Saved config.")
    else:
        logger.info("No config manager to save.")

    # 4. As the final step, clean up the document editor,
    # and shut down the task manager itself.
    # The context shutdown (including artifact store) now happens in the async
    # part above, so we only need to clean up the editor here.
    logger.info("Cleaning up DocEditor")
    app.win.doc_editor.cleanup()
    logger.info("DocEditor cleaned up.")

    logger.info("Shutting down TaskManager")
    rayforge.shared.tasker.task_mgr.shutdown()
    logger.info("Task manager shut down.")

    return exit_code

if __name__ == "__main__":
    from multiprocessing import freeze_support

    freeze_support()  # needed to use multiprocessing in PyInstaller bundles
    sys.exit(main())
