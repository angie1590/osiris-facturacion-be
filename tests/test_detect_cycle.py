import uuid
from types import SimpleNamespace
from unittest.mock import Mock

from osiris.modules.inventario.categoria.service import CategoriaService


class SeqExec:
    def __init__(self, results_iter):
        self._iter = iter(results_iter)

    def __call__(self, *_args, **_kwargs):
        result = Mock()
        try:
            rows = next(self._iter)
        except StopIteration:
            rows = []
        result.all.return_value = rows
        return result


def make_session_with_sequence(results_sequence):
    """Crea una sesión falsa cuya llamada a exec(select(...)).all() devolverá
    los elementos de results_sequence de forma secuencial en cada invocación.
    """
    session = Mock()
    session.exec.side_effect = SeqExec(results_sequence)
    return session


def test_detect_cycle_returns_true_when_target_is_descendant():
    service = CategoriaService()
    # Simular: llamadas a .all() devolverán en orden:
    # 1) hijos de current (-> [child1])
    # 2) hijos de child1 (-> [target])
    # 3) hijos de target (-> [])
    target = uuid.uuid4()
    child1 = SimpleNamespace(id=uuid.uuid4(), parent_id=None)
    # second call returns a list containing an object with id equal to target
    second_level = [SimpleNamespace(id=target, parent_id=None)]
    seq = [[child1], second_level, []]
    session = make_session_with_sequence(seq)

    # current_id is some uuid; target_parent_id is target
    current_id = uuid.uuid4()

    assert service._detect_cycle(session, current_id, target) is True


def test_detect_cycle_returns_false_when_target_not_descendant():
    service = CategoriaService()
    # Simular: llamadas a .all() devolverán en orden:
    # 1) hijos de current (-> [child1, child2])
    # 2) hijos de child1 (-> [])
    # 3) hijos de child2 (-> [])
    child1 = SimpleNamespace(id=uuid.uuid4(), parent_id=None)
    child2 = SimpleNamespace(id=uuid.uuid4(), parent_id=None)
    seq = [[child1, child2], [], []]
    session = make_session_with_sequence(seq)

    current_id = uuid.uuid4()
    target = uuid.uuid4()

    assert service._detect_cycle(session, current_id, target) is False


def test_detect_cycle_detects_self_reference_immediately():
    service = CategoriaService()
    session = Mock()
    some_id = uuid.uuid4()
    # If current_id == target_parent_id, must return True without querying
    assert service._detect_cycle(session, some_id, some_id) is True
