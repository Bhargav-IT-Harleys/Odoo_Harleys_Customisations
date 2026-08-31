# -*- coding: utf-8 -*-
from .base_adapter import BaseAdapter

# Importing these registers each adapter with AdapterRegistry as a side effect
# (see each package's __init__.py) - without these imports, no adapter is ever
# registered, and every lookup in AdapterRegistry silently fails.
from . import hyperpure
from . import rista
