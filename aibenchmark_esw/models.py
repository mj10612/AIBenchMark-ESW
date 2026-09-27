from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from pathlib import Path


@dataclass
class TaskLimits:
    max_flash_bytes: int = 2048
    max_ram_bytes: int = 256
    timeout_seconds: int = 10


@dataclass
class TaskWeights:
    functional: float = 0.6
    memory: float = 0.2
    safety: float = 0.2


@dataclass
class TaskConfig:
    id: str
    name: str
    tier: int
    category: str
    target_standard: str
    description: str
    limits: TaskLimits
    weights: TaskWeights
    entry_file: str
    task_dir: Path
    prompt: str = ""

    @classmethod
    def from_dict(cls, data: Dict[str, Any], task_dir: Path, prompt: str = "") -> "TaskConfig":
        limits_data = data.get("limits", {})
        limits = TaskLimits(
            max_flash_bytes=limits_data.get("max_flash_bytes", 2048),
            max_ram_bytes=limits_data.get("max_ram_bytes", 256),
            timeout_seconds=limits_data.get("timeout_seconds", 10),
        )
        weights_data = data.get("weights", {})
        weights = TaskWeights(
            functional=weights_data.get("functional", 0.6),
            memory=weights_data.get("memory", 0.2),
            safety=weights_data.get("safety", 0.2),
        )
        return cls(
            id=data["id"],
            name=data.get("name", data["id"]),
            tier=data.get("tier", 1),
            category=data.get("category", "general"),
            target_standard=data.get("target_standard", "c99"),
            description=data.get("description", ""),
            limits=limits,
            weights=weights,
            entry_file=data.get("entry_file", "src/solution.c"),
            task_dir=task_dir,
            prompt=prompt,
        )


@dataclass
class CompilationResult:
    success: bool
    output: str
    binary_path: Optional[Path] = None
    error_message: Optional[str] = None


@dataclass
class TestResult:
    total_tests: int = 0
    passed_tests: int = 0
    failed_tests: int = 0
    ignored_tests: int = 0
    output: str = ""
    passed: bool = False


@dataclass
class SizeMetrics:
    flash_bytes: int = 0
    ram_bytes: int = 0
    ref_flash_bytes: int = 0
    ref_ram_bytes: int = 0


@dataclass
class StaticSafetyMetrics:
    error_count: int = 0
    warning_count: int = 0
    violations: List[str] = field(default_factory=list)


@dataclass
class DimensionScores:
    functional_score: float = 0.0  # 0.0 - 100.0
    memory_score: float = 0.0      # 0.0 - 100.0
    safety_score: float = 0.0      # 0.0 - 100.0
    total_score: float = 0.0       # 0.0 - 100.0


@dataclass
class TaskEvaluationResult:
    task_id: str
    tier: int
    model_name: str
    compiled: bool
    test_result: TestResult
    size_metrics: SizeMetrics
    safety_metrics: StaticSafetyMetrics
    scores: DimensionScores
    execution_time_sec: float
    error_log: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "tier": self.tier,
            "model_name": self.model_name,
            "compiled": self.compiled,
            "test_result": {
                "total": self.test_result.total_tests,
                "passed": self.test_result.passed_tests,
                "failed": self.test_result.failed_tests,
                "ignored": self.test_result.ignored_tests,
                "all_passed": self.test_result.passed,
            },
            "size_metrics": {
                "flash_bytes": self.size_metrics.flash_bytes,
                "ram_bytes": self.size_metrics.ram_bytes,
                "ref_flash_bytes": self.size_metrics.ref_flash_bytes,
                "ref_ram_bytes": self.size_metrics.ref_ram_bytes,
            },
            "safety_metrics": {
                "error_count": self.safety_metrics.error_count,
                "warning_count": self.safety_metrics.warning_count,
            },
            "scores": {
                "functional": round(self.scores.functional_score, 2),
                "memory": round(self.scores.memory_score, 2),
                "safety": round(self.scores.safety_score, 2),
                "total": round(self.scores.total_score, 2),
            },
            "execution_time_sec": round(self.execution_time_sec, 3),
            "error_log": self.error_log,
        }
