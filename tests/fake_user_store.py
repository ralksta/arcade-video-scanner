"""
fake_user_store.py
------------------
Attrappe des Nutzer-Stores für Routen-Tests.

Warum nicht einfach ein `MagicMock()`: Seit die Routen ihre Änderungen über
`update_user(name, mutate)` schreiben, muss die Attrappe den Änderer **wirklich
aufrufen**. Ein blankes MagicMock gibt stumm ein wahres Objekt zurück, die
Änderung findet nie statt — und der Test darüber ist grün, ohne die Route
geprüft zu haben. Genau das ist beim Umbau in drei Testdateien gleichzeitig
passiert.

Die Nachbildung ist absichtlich dieselbe Reihenfolge wie im echten Store
(lesen, ändern, schreiben), damit ein Test, der auf `add_user` horcht, weiter
funktioniert.
"""
from unittest.mock import MagicMock


def make_fake_user_db(user=None):
    """Ein MagicMock-Store, dessen `update_user()` tatsächlich ändert.

    Args:
        user: Das Objekt, das `get_user()` liefern soll. None erzeugt eines mit
              den üblichen leeren Feldern.

    Returns:
        (user_db, user)
    """
    if user is None:
        user = MagicMock()
        user.data.available_tags = []
        user.data.auto_tag_rules = []
        user.data.tags = {}
        user.data.favorites = []
        user.data.vaulted = []

    user_db = MagicMock()
    user_db.get_user.return_value = user

    def update_user(username, mutate):
        current = user_db.get_user(username)
        if current is None:
            return False
        mutate(current)
        user_db.add_user(current)
        return True

    user_db.update_user.side_effect = update_user
    return user_db, user
