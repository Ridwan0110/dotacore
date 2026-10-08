## Possible Bugs
- `/frontend/registry.py:69 (return engine.run())`: The return statement should return the object. So proposed solution is `return engine.run`.