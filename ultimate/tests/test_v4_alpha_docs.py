from pathlib import Path


def _agents_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "AGENTS.md").exists():
            return parent
    raise AssertionError("Could not locate AGENTS.md from test path")


AGENTS_ROOT = _agents_root()
def _ultimate_readme() -> Path:
    candidates = [AGENTS_ROOT / "README.md", AGENTS_ROOT / "ultimate" / "README.md"]
    existing = [path for path in candidates if path.exists()]
    for path in existing:
        if "V4 Alpha Customer Delivery Loop" in path.read_text(encoding="utf-8", errors="ignore"):
            return path
    for path in existing:
        if "Ultimate Bioinfo Workbench" in path.read_text(encoding="utf-8", errors="ignore"):
            return path
    raise AssertionError("Could not locate Ultimate README.md from test path")


def test_agents_documents_v4_customer_delivery_boundary() -> None:
    text = (AGENTS_ROOT / "AGENTS.md").read_text(encoding="utf-8")

    assert "V4 客户交付闭环" in text
    assert "customer_delivery" in text
    assert "internal_rehearsal" in text
    assert "禁止把 `internal_rehearsal` 当作客户交付" in text
    assert "客户版 delivery QA" in text
    assert "batch order scaffold" in text


def test_readme_documents_v4_alpha_customer_delivery_path() -> None:
    text = _ultimate_readme().read_text(encoding="utf-8")

    assert "V4 Alpha Customer Delivery Loop" in text
    assert "ultimate prepare-batch" in text
    assert "v4_alpha_customer_delivery_rehearsal.sbatch" in text
    assert "delivery_mode=customer_delivery_rehearsal" in text
    assert "customer_delivery_rehearsal" in text
    assert "customer_delivery" in text


def test_readme_documents_v4_beta_customer_trial_path() -> None:
    readme = Path(__file__).resolve().parents[1] / "README.md"
    text = readme.read_text(encoding="utf-8")

    assert "V4 Beta Customer Trial" in text
    assert "v4_beta_customer_trial.sbatch" in text
    assert "readme_for_customer.md" in text
    assert "raw upstream evidence is still lightweight" in text
    assert "V4 Beta remains a controlled rehearsal" in text
