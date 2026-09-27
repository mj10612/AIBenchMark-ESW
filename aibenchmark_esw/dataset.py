import json
from pathlib import Path
from typing import List, Optional, Dict
from aibenchmark_esw.models import TaskConfig


class DatasetLoader:
    def __init__(self, tasks_root: Optional[Path] = None):
        if tasks_root is None:
            # Default to tasks/ under project root
            project_root = Path(__file__).resolve().parent.parent
            self.tasks_root = project_root / "tasks"
        else:
            self.tasks_root = Path(tasks_root)
        self._tasks: Dict[str, TaskConfig] = {}
        self._load_all()

    def _load_all(self) -> None:
        self._tasks.clear()
        if not self.tasks_root.exists():
            return

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
                    with open(prompt_file, "r", encoding="utf-8") as pf:
                        prompt_content = pf.read()

                config = TaskConfig.from_dict(data, task_dir=task_dir, prompt=prompt_content)
                self._tasks[config.id] = config
            except Exception as e:
                print(f"[Warning] Failed to load task at {task_dir}: {e}")

    def list_tasks(self, tier: Optional[int] = None) -> List[TaskConfig]:
        tasks = list(self._tasks.values())
        if tier is not None:
            tasks = [t for t in tasks if t.tier == tier]
        return sorted(tasks, key=lambda t: (t.tier, t.id))

    def get_task(self, task_id: str) -> Optional[TaskConfig]:
        return self._tasks.get(task_id)

    def get_reference_solution(self, task_id: str) -> Optional[str]:
        task = self.get_task(task_id)
        if not task:
            return None
        # Reference solution filename matches entry_file basename under reference/
        ref_file = task.task_dir / "reference" / Path(task.entry_file).name
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
