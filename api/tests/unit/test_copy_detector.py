from src.modules.articles.domain.copy_detector import check_copy_overlap
from src.modules.shared.domain.entities import IssueSeverity


def test_copy_overlap_clean_text():
    draft = "This is a completely original explanation of vector embeddings and cosine similarity."
    reference = ["In machine learning, we use neural networks to optimize loss functions."]
    issues = check_copy_overlap(draft, reference, reference_type="sample")
    assert len(issues) == 0


def test_copy_overlap_blocker():
    sentence = "the quick brown fox jumps over the lazy dog and runs through the forest"
    draft = f"{sentence} {sentence} repeatedly to verify high overlap."
    reference = [f"{sentence} and other unrelated text here."]

    issues = check_copy_overlap(draft, reference, reference_type="sample", block_threshold=0.30)
    assert len(issues) == 1
    assert issues[0].severity == IssueSeverity.BLOCKER
    assert "verbatim" in issues[0].message


def test_copy_overlap_ignores_code_blocks():
    identical_code = """```python
import numpy as np
def cosine_sim(a, b):
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))
```"""
    draft = f"Here is how you compute cosine similarity:\n{identical_code}\nIt calculates the angle."
    reference = [f"Reference implementation:\n{identical_code}\nDifferent prose entirely."]

    issues = check_copy_overlap(draft, reference, reference_type="source")
    assert len(issues) == 0


def test_copy_overlap_catches_long_verbatim_run():
    # 45 identical consecutive words in a 300-word draft (overlap < 15% but run >= 40)
    words = [f"uniqueterm{i}" for i in range(45)]
    run_text = " ".join(words)

    padding = " ".join([f"originaldraftword{i}" for i in range(300)])
    draft = f"{padding} {run_text} more original words here."
    reference = [f"unrelated reference words {run_text} other reference words."]

    issues = check_copy_overlap(draft, reference, reference_type="sample", max_run_words=40)
    assert len(issues) == 1
    assert "consecutive run" in issues[0].message
