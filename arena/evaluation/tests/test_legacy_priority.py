"""Legacy fixture linearization; canonical ARC constraints remain unchanged."""
import pytest
from accounts.models import User
from planning.models import PlanningItem
from arena.datasets import importer
from arena.evaluation.features import characterize_workload
from arena.evaluation.tests.test_features import TODAY

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("priorities,order,ties", [
    ([9, 2, 5], [1, 2, 0], 0),
    ([2, 5, 5, 5, 9], [0, 1, 2, 3, 4], 1),
    ([9, 2, 9, 2, None, 5], [1, 3, 5, 0, 2], 2),
    ([None, None], [], 0),
])
def test_priority_order_and_metadata(priorities, order, ties):
    rows = [{"key": str(index), "priority": "" if priority is None else str(priority)}
            for index, priority in enumerate(priorities)]
    positions, metadata = importer.legacy_priority_positions(rows)
    assert list(positions) == [str(index) for index in order]
    assert list(positions.values()) == list(range(1, len(order) + 1))
    assert len(set(positions.values())) == len(positions)
    assert metadata == {"legacy_priority_linearized": bool(ties), "legacy_priority_tie_count": ties}
    assert importer.legacy_priority_positions(rows) == (positions, metadata)


def test_import_order_uses_csv_not_hierarchy_insertion_order(monkeypatch):
    def row(key, priority, parent=""):
        return dict(scenario="ordering", key=key, title=key, item_type="TASK", parent_key=parent,
                    duration_class="MIN_20_TO_60", completed="False", anchored="False",
                    scheduled_date="", release_date="", due_date="", priority=priority)
    # First CSV row waits for its parent: database insertion order is different.
    rows = [row("child", "5", "parent"), row("parent", "5"), row("early", "2"), row("null", "")]
    metadata = [dict(scenario="ordering", family="test", today=TODAY.isoformat())]
    monkeypatch.setattr(importer, "_rows", lambda name: rows if name == "items.csv" else metadata)
    for _ in range(2):
        result = importer.load_scenario("ordering")
        assert result == {"legacy_priority_linearized": True, "legacy_priority_tie_count": 1}
        assert list(PlanningItem.objects.filter(priority_position__isnull=False).order_by("priority_position").values_list("title", "priority_position")) == [("early", 1), ("child", 2), ("parent", 3)]
        assert PlanningItem.objects.get(title="null").priority_position is None


def test_real_fixture_repeat_and_csv_preservation():
    before = {path: path.read_bytes() for path in importer.RAW_DIR.glob("*.csv")}
    orders = []
    for _ in range(2):
        metadata = importer.load_scenario("random_1001")
        orders.append(list(PlanningItem.objects.order_by("priority_position", "title").values_list("title", "priority_position")))
        user = User.objects.get(email="arena@local.test")
        features = characterize_workload(user, TODAY).to_mapping()
        assert len(features) == 89
        assert not set(metadata) & features.keys()
    assert orders[0] == orders[1]
    assert metadata["legacy_priority_linearized"] is True
    assert metadata["legacy_priority_tie_count"] == 14
    assert before == {path: path.read_bytes() for path in before}
