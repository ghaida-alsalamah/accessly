"""Select one persistence provider explicitly, retaining PostgreSQL as default."""
from firebase_runtime import enabled
if enabled():
    import firestore_store as store
else:
    import db as store
