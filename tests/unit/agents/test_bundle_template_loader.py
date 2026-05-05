from __future__ import annotations


def test_bundle_template_loader_returns_deep_copy(shared_template_loader) -> None:
    tpl1 = shared_template_loader.load("hr_management", "app-01")
    assert tpl1 is not None
    tpl1["_mutated_by_test"] = True

    tpl2 = shared_template_loader.load("hr_management", "app-01")
    assert tpl2 is not None
    assert tpl2.get("_mutated_by_test") is None
