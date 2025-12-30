from api.logger import root_logger

from pathlib import Path

log = root_logger.debug

answer_filter = None
fact_checker = None
intent_detector = None
plan_creator = None
plan_refiner = None
simbio_expert = None
answer_rater = None

try:
    base_path = Path(__file__).parent

    # ANSWER FILTER
    if (base_path / "answer_filter.txt").exists():
        answer_filter = (base_path / "answer_filter.txt").read_text(encoding="utf-8")

    # FACT CHECKER
    if (base_path / "fact_checker.txt").exists():
        fact_checker = (base_path / "fact_checker.txt").read_text(encoding="utf-8")

    # INTENT DETECTOR
    if (base_path / "intent_detector.txt").exists():
        intent_detector = (base_path / "intent_detector.txt").read_text(encoding="utf-8")

    # PLAN CREATOR
    if (base_path / "plan_creator.txt").exists():
        plan_creator = (base_path / "plan_creator.txt").read_text(encoding="utf-8")

    # PLAN_REFINER
    if (base_path / "plan_refiner.txt").exists():
        plan_refiner = (base_path / "plan_refiner.txt").read_text(encoding="utf-8")

    # SIMBIO EXPERT
    if (base_path / "simbio_expert.txt").exists():
        simbio_expert = (base_path / "simbio_expert.txt").read_text(encoding="utf-8")

    # ANSWER RATER
    if (base_path / "answer_rater.txt").exists():
        answer_rater = (base_path / "answer_rater.txt").read_text(encoding="utf-8")

except Exception as e:
    log(f"Error loading prompts: {e}")


__all__ = [
    "answer_filter",
    "fact_checker",
    "intent_detector",
    "plan_creator",
    "plan_refiner",
    "simbio_expert",
    "answer_rater",
]
