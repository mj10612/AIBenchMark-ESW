import json
import logging
from pathlib import Path
from typing import List, Optional, Dict
from aibenchmark_esw.models import TaskConfig
from aibenchmark_esw.resources import data_root


logger = logging.getLogger(__name__)


def validate_task_assets(task: TaskConfig) -> List[str]:
    """Check readable, nonempty prompt/API/source/test inputs without executing C."""
    required = [("prompt", task.task_dir / "prompt.md"),
                ("starter implementation", task.task_dir / task.entry_file),
                ("reference implementation", task.reference_path)]
    errors = []
    for folder, pattern, label in (("include", "*.h", "API header"), ("tests", "test_*.c", "test source")):
        matches = sorted((task.task_dir / folder).glob(pattern))
        if not matches:
            errors.append(f"Missing {label}: expected {folder}/{pattern}")
        required.extend((label, path) for path in matches)
    for label, path in required:
        if not path.is_file():
            errors.append(f"Missing {label}: {path.relative_to(task.task_dir).as_posix()}")
            continue
        try:
            if not path.read_text(encoding="utf-8").strip():
                errors.append(f"Empty {label}: {path.relative_to(task.task_dir).as_posix()}")
        except (OSError, UnicodeError) as error:
            errors.append(f"Unreadable {label}: {path.relative_to(task.task_dir).as_posix()} ({error})")
    return errors


class DatasetLoader:
    def __init__(self, tasks_root: Optional[Path] = None, strict: bool = True):
        self.strict = strict
        self.load_errors: Dict[str, str] = {}
        if tasks_root is None:
            self.tasks_root = data_root() / "tasks"
        else:
            self.tasks_root = Path(tasks_root).resolve()
        if not self.tasks_root.exists():
            raise FileNotFoundError(f"Benchmark task data not found: {self.tasks_root}")
        if not self.tasks_root.is_dir():
            raise NotADirectoryError(f"Benchmark task root is not a directory: {self.tasks_root}")
        self._tasks: Dict[str, TaskConfig] = {}
        self._load_all()

    def _load_all(self) -> None:
        tasks = {}

        for task_dir in sorted(self.tasks_root.iterdir()):
            if not task_dir.is_dir():
                continue
            task_json = task_dir / "task.json"
            if not task_json.is_file():
                continue

            try:
                with open(task_json, "r", encoding="utf-8") as f:
                    data = json.load(f)

                prompt_file = task_dir / "prompt.md"
                prompt_content = ""
                if prompt_file.is_file():
                    # Keep valid metadata selectable even when an asset is broken.
                    # validate_task_assets diagnoses the unreadable prompt per task.
                    try:
                        prompt_content = prompt_file.read_text(encoding="utf-8")
                    except (OSError, UnicodeError):
                        pass

                config = TaskConfig.from_dict(data, task_dir=task_dir, prompt=prompt_content)
                if config.id in tasks:
                    raise ValueError(f"Duplicate task id: {config.id}")
                tasks[config.id] = config
            except (OSError, UnicodeError, ValueError, KeyError, TypeError) as error:
                logger.error("Failed to load task at %s: %s", task_dir, error)
                if self.strict:
                    raise ValueError(f"Invalid task at {task_dir}: {error}") from error
                self.load_errors[str(task_dir)] = str(error)
        self._tasks = tasks

    def list_tasks(self, tier: Optional[int] = None, category: Optional[str] = None) -> List[TaskConfig]:
        tasks = list(self._tasks.values())
        if tier is not None:
            tasks = [t for t in tasks if t.tier == tier]
        if category is not None:
            tasks = [t for t in tasks if t.category == category]
        return sorted(tasks, key=lambda t: (t.tier, t.id))

    def get_task(self, task_id: str) -> Optional[TaskConfig]:
        return self._tasks.get(task_id)

    def get_reference_solution(self, task_id: str) -> Optional[str]:
        task = self.get_task(task_id)
        if not task:
            return None
        ref_file = task.reference_path
        if ref_file.is_file():
            with open(ref_file, "r", encoding="utf-8") as f:
                return f.read()
        return None

    def get_starter_code(self, task_id: str) -> Optional[str]:
        task = self.get_task(task_id)
        if not task:
            return None
        starter_file = task.task_dir / task.entry_file
        if starter_file.is_file():
            with open(starter_file, "r", encoding="utf-8") as f:
                return f.read()
        return None
