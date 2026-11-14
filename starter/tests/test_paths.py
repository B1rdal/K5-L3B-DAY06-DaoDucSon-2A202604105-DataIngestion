import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from src.paths import cache_path


class PortablePathTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='day6 relocated ')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'Moved project' / 'starter'
        self.root.mkdir(parents=True)
        self.root_patch = patch('src.paths.ROOT', self.root)
        self.root_patch.start()
        self.addCleanup(self.root_patch.stop)
        self.env_patch = patch.dict(os.environ, {}, clear=True)
        self.env_patch.start()
        self.addCleanup(self.env_patch.stop)

    def test_default_cache_follows_project_not_working_directory(self):
        self.assertEqual(cache_path('fastembed'), self.root / '.cache/fastembed')
        self.assertEqual(cache_path('rerankers'), self.root / '.cache/rerankers')
        self.assertEqual(cache_path('fastembed', 'custom/models'), self.root / 'custom/models')

    def test_absolute_environment_override_wins_over_config(self):
        external = Path(self.temp.name) / 'Shared models'
        os.environ['DAY6_MODEL_CACHE'] = str(external)
        self.assertEqual(cache_path('fastembed', 'config/cache'), external)

    def test_env_file_is_loaded_from_relocated_project(self):
        (self.root / '.env').write_text('DAY6_RERANKER_CACHE=local rerankers\n', encoding='utf-8')
        self.assertEqual(cache_path('rerankers'), self.root / 'local rerankers')

    def test_model_and_reranker_paths_are_independent(self):
        os.environ['DAY6_MODEL_CACHE'] = 'embedding cache'
        self.assertEqual(cache_path('fastembed'), self.root / 'embedding cache')
        self.assertEqual(cache_path('rerankers'), self.root / '.cache/rerankers')
        with self.assertRaises(ValueError):
            cache_path('unknown')
