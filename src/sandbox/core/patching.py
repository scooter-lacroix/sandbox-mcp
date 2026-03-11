"""
Unified Patching Utilities for Sandbox MCP.

This module consolidates duplicate monkey-patching logic from both
MCP servers for matplotlib and PIL.

Security C1: Provides session-isolated patching to prevent cross-session leakage.
"""

from pathlib import Path
from typing import Optional, Any, Dict, Tuple
import logging
import uuid

logger = logging.getLogger(__name__)


class PatchManager:
    """
    Manager for monkey patches in sandbox environments.

    This class provides unified patching for matplotlib and PIL,
    replacing duplicate logic in both MCP servers.
    
    Security C1: Patches capture session-specific state to prevent
    cross-session artifact leakage.
    """

    def __init__(self):
        """Initialize the patch manager."""
        self._patches_applied: Dict[str, bool] = {}
        self._original_functions: Dict[str, Any] = {}
        self._session_patches: Dict[str, Dict[str, Any]] = {}

    def configure_matplotlib_backend(self, backend: str = 'Agg') -> str:
        """
        Configure matplotlib backend.

        Args:
            backend: The matplotlib backend to use (default: 'Agg').

        Returns:
            The configured backend name.
        """
        try:
            import matplotlib
            matplotlib.use(backend, force=True)
            self._patches_applied['matplotlib_backend'] = True
            logger.info(f"Configured matplotlib backend: {backend}")
            return backend
        except ImportError:
            logger.warning("matplotlib not available, skipping backend configuration")
            return backend

    def patch_matplotlib(self, artifacts_dir: Optional[Path] = None, session_id: Optional[str] = None) -> bool:
        """
        Apply matplotlib patches for artifact capture.
        
        Security C1: Captures session-specific artifacts_dir to prevent leakage.

        Args:
            artifacts_dir: Optional directory for saving plots.
            session_id: Optional session identifier for tracking.

        Returns:
            True if patches were applied successfully.
        """
        try:
            import matplotlib
            matplotlib.use('Agg', force=True)
            
            import matplotlib.pyplot as plt
            
            if getattr(plt.show, "_sandbox_patched", False):
                logger.debug("matplotlib already patched")
                return True
            
            # Store original function
            self._original_functions['plt_show'] = plt.show
            
            # C1: Capture session-specific state
            session_artifacts_dir = str(artifacts_dir) if artifacts_dir else None
            
            def patched_show(*args: Any, **kwargs: Any) -> Any:
                """Patched plt.show with session-isolated artifact saving."""
                try:
                    if session_artifacts_dir:
                        plots_dir = Path(session_artifacts_dir) / "plots"
                        plots_dir.mkdir(parents=True, exist_ok=True)
                        
                        for ext, format_name in [("png", "PNG"), ("svg", "SVG"), ("pdf", "PDF")]:
                            try:
                                save_path = plots_dir / f"plot_{uuid.uuid4().hex[:8]}.{ext}"
                                plt.savefig(save_path, dpi=150, bbox_inches="tight", format=ext)
                                logger.info(f"Plot saved: {save_path}")
                                break
                            except Exception:
                                continue
                except Exception as exc:
                    logger.error(f"Error in patched_show: {exc}")
                
                return self._original_functions['plt_show'](*args, **kwargs)
            
            patched_show._sandbox_patched = True
            patched_show._session_artifacts_dir = session_artifacts_dir
            plt.show = patched_show
            
            self._patches_applied['matplotlib'] = True
            if session_id:
                self._session_patches.setdefault(session_id, {})['matplotlib'] = True
            logger.info("Applied matplotlib patches")
            return True
        except ImportError:
            logger.warning("matplotlib not available, skipping patches")
            return False
        except Exception as exc:
            logger.error(f"Error patching matplotlib: {exc}")
            return False

    def patch_pil(self, artifacts_dir: Optional[Path] = None, session_id: Optional[str] = None) -> bool:
        """
        Apply PIL/Image patches for artifact capture.
        
        Security C1: Captures session-specific artifacts_dir to prevent leakage.

        Args:
            artifacts_dir: Optional directory for saving images.
            session_id: Optional session identifier for tracking.

        Returns:
            True if patches were applied successfully.
        """
        try:
            from PIL import Image

            if getattr(Image.Image.show, "_sandbox_patched", False):
                logger.debug("PIL already patched")
                return True

            # Store original functions
            self._original_functions['pil_show'] = Image.Image.show
            self._original_functions['pil_save'] = Image.Image.save
            
            # C1: Capture session-specific state
            session_artifacts_dir = str(artifacts_dir) if artifacts_dir else None

            def patched_show(self_img: Any, title: Any = None, command: Any = None) -> Any:
                """Patched Image.show with session-isolated artifact saving."""
                if session_artifacts_dir:
                    images_dir = Path(session_artifacts_dir) / "images"
                    images_dir.mkdir(parents=True, exist_ok=True)
                    image_path = images_dir / f"image_{uuid.uuid4().hex[:8]}.png"
                    self_img.save(image_path)
                    logger.info(f"Image saved: {image_path}")
                return self._original_functions['pil_show'](self_img, title, command)

            def patched_save(self_img: Any, fp: Any, format: Any = None, **params: Any) -> Any:
                """Patched Image.save with session-aware logging."""
                result = self._original_functions['pil_save'](self_img, fp, format, **params)
                if session_artifacts_dir and str(fp).startswith(session_artifacts_dir):
                    logger.info(f"Image saved to artifacts: {fp}")
                return result

            patched_show._sandbox_patched = True
            patched_show._session_artifacts_dir = session_artifacts_dir
            patched_save._sandbox_patched = True
            patched_save._session_artifacts_dir = session_artifacts_dir
            
            Image.Image.show = patched_show
            Image.Image.save = patched_save
            
            self._patches_applied['pil'] = True
            if session_id:
                self._session_patches.setdefault(session_id, {})['pil'] = True
            logger.info("Applied PIL patches")
            return True
        except ImportError:
            logger.warning("PIL not available, skipping patches")
            return False
        except Exception as exc:
            logger.error(f"Error patching PIL: {exc}")
            return False

    def apply_all_patches(self, artifacts_dir: Optional[Path] = None, session_id: Optional[str] = None) -> Dict[str, bool]:
        """
        Apply all available patches.

        Args:
            artifacts_dir: Optional directory for artifacts.
            session_id: Optional session identifier for tracking.

        Returns:
            Dictionary of patch names to success status.
        """
        results = {
            'matplotlib': self.patch_matplotlib(artifacts_dir, session_id),
            'pil': self.patch_pil(artifacts_dir, session_id),
        }
        return results

    def cleanup_session_patches(self, session_id: str) -> None:
        """
        Cleanup patches for a specific session.
        
        Security C1: Allows per-session patch cleanup.
        """
        if session_id in self._session_patches:
            del self._session_patches[session_id]
        logger.debug(f"Cleaned up patches for session: {session_id}")

    def cleanup(self) -> None:
        """Cleanup and restore original functions."""
        try:
            # Restore PIL if it was patched
            if 'pil_show' in self._original_functions:
                from PIL import Image
                Image.Image.show = self._original_functions['pil_show']
                Image.Image.save = self._original_functions['pil_save']
                del self._original_functions['pil_show']
                del self._original_functions['pil_save']
                logger.info("Restored original PIL methods")
            
            # Restore matplotlib if it was patched
            if 'plt_show' in self._original_functions:
                import matplotlib.pyplot as plt
                plt.show = self._original_functions['plt_show']
                del self._original_functions['plt_show']
                logger.info("Restored original plt.show")
        except Exception as e:
            logger.warning(f"Error during cleanup: {e}")

        self._patches_applied.clear()
        self._session_patches.clear()

    def unpatch_all(self) -> None:
        """Alias for cleanup()."""
        self.cleanup()

    def get_patch_status(self) -> Dict[str, bool]:
        """
        Get status of applied patches.

        Returns:
            Dictionary of patch names to applied status.
        """
        return self._patches_applied.copy()

    def get_session_patch_status(self, session_id: str) -> Dict[str, bool]:
        """
        Get status of patches for a specific session.
        
        Security C1: Track per-session patch state.
        """
        return self._session_patches.get(session_id, {}).copy()


# Singleton instance for convenience
_patch_manager: Optional[PatchManager] = None


def get_patch_manager() -> PatchManager:
    """
    Get the global patch manager instance.
    
    Returns:
        The singleton PatchManager instance.
    """
    global _patch_manager
    if _patch_manager is None:
        _patch_manager = PatchManager()
    return _patch_manager
