"""Contract tests for the bounded runner using synthetic, non-FE doubles.

The adapter and solver in these tests are deliberately mocked.  They exercise
identity, staging, process, and completion contracts only; passing here is not
evidence that a finite-element model or solver result is physically valid.
"""

import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import fea_readiness.runner as runner_module
from fea_readiness.contracts import sha256, rule
from fea_readiness.pipeline import prepare
from fea_readiness.runner import run_checked


THEORY = {
    "kind": "hertz_line",
    "inputs": {
        "q_N_per_mm": 10,
        "R1_mm": 10,
        "R2_mm": 10,
        "E1_MPa": 210000,
        "nu1": 0.3,
        "E2_MPa": 210000,
        "nu2": 0.3,
    },
}


class RunnerExecutionTests(unittest.TestCase):
    """Synthetic process tests for runner plumbing, not real FE execution."""

    def _case(self, root):
        inp = root / "model.inp"
        meta = inp.with_suffix(".meta.json")
        solver = root / "synthetic-solver.exe"
        inp.write_text("synthetic input\n", encoding="ascii")
        meta.write_text('{"synthetic": true}\n', encoding="ascii")
        solver.write_bytes(b"synthetic solver placeholder\n")
        spec = {
            "case_id": "synthetic-runner-contract",
            "units": "N-mm-MPa",
            "theory": THEORY,
            "native": {"profile": "m37_l3", "input": str(inp)},
        }
        return spec, inp, meta, solver

    @staticmethod
    def _synthetic_adapter(spec):
        # Synthetic adapter only: this does not parse or validate a physical FE model.
        source = Path(spec["native"]["input"]).resolve()
        return {
            "checks": [rule("synthetic_adapter", "PASS", "TEST ONLY; synthetic adapter")],
            "files": [str(source), str(source.with_suffix(".meta.json"))],
        }

    def _prepared(self, spec):
        return prepare(spec)

    @staticmethod
    def _solver_process(*, final=True, returncode=0, timeout=False):
        """Return a mocked subprocess.run callable for a synthetic solver."""

        should_timeout = timeout

        def fake_run(argv, cwd, stdout, stderr, timeout, shell, env, **kwargs):
            if should_timeout:
                raise subprocess.TimeoutExpired(argv, timeout)
            if final:
                (Path(cwd) / "job.sta").write_text(
                    "2 4 1 3 2.0 1.0 0.25\n", encoding="ascii"
                )
            else:
                (Path(cwd) / "job.sta").write_text(
                    "1 4 1 3 1.0 1.0 0.25\n", encoding="ascii"
                )
            (Path(cwd) / "job.dat").write_text("synthetic raw output\n", encoding="ascii")
            stdout.write(b"Job finished\n")
            return SimpleNamespace(returncode=returncode)

        return fake_run

    def _run(self, spec, prepared, solver, run_dir, process):
        return run_checked(
            spec,
            prepared,
            solver,
            sha256(solver),
            run_dir,
            timeout_s=1,
        )

    def test_success_writes_run_record_and_keeps_engineering_acceptance_false(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            spec, _inp, _meta, solver = self._case(root)
            with patch("fea_readiness.pipeline.native_check", side_effect=self._synthetic_adapter):
                prepared = self._prepared(spec)
                self.assertTrue(prepared["ready_for_diagnostic_solve"])
                with patch(
                    "fea_readiness.runner.subprocess.run",
                    side_effect=self._solver_process(final=True, returncode=0),
                ) as mocked:
                    report = self._run(spec, prepared, solver, root / "run", mocked)
            self.assertTrue(report["complete"])
            self.assertFalse(report["engineering_accepted"])
            self.assertEqual(report["returncode"], 0)
            self.assertTrue((root / "run" / "run.json").is_file())
            self.assertEqual(mocked.call_count, 1)

    def test_existing_run_directory_is_rejected_before_solver_launch(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            spec, _inp, _meta, solver = self._case(root)
            run_dir = root / "existing"
            run_dir.mkdir()
            with patch("fea_readiness.pipeline.native_check", side_effect=self._synthetic_adapter):
                prepared = self._prepared(spec)
                with patch("fea_readiness.runner.subprocess.run") as mocked:
                    with self.assertRaises(FileExistsError):
                        self._run(spec, prepared, solver, run_dir, mocked)
            mocked.assert_not_called()

    def test_incomplete_final_step_is_not_complete(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            spec, _inp, _meta, solver = self._case(root)
            with patch("fea_readiness.pipeline.native_check", side_effect=self._synthetic_adapter):
                prepared = self._prepared(spec)
                with patch(
                    "fea_readiness.runner.subprocess.run",
                    side_effect=self._solver_process(final=False, returncode=0),
                ):
                    report = self._run(spec, prepared, solver, root / "run", None)
            self.assertFalse(report["complete"])
            self.assertFalse(report["final_step_complete"])

    def test_nonzero_solver_exit_is_not_complete(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            spec, _inp, _meta, solver = self._case(root)
            with patch("fea_readiness.pipeline.native_check", side_effect=self._synthetic_adapter):
                prepared = self._prepared(spec)
                with patch(
                    "fea_readiness.runner.subprocess.run",
                    side_effect=self._solver_process(final=True, returncode=17),
                ):
                    report = self._run(spec, prepared, solver, root / "run", None)
            self.assertFalse(report["complete"])
            self.assertEqual(report["returncode"], 17)

    def test_timeout_is_recorded_and_not_complete(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            spec, _inp, _meta, solver = self._case(root)
            with patch("fea_readiness.pipeline.native_check", side_effect=self._synthetic_adapter):
                prepared = self._prepared(spec)
                with patch(
                    "fea_readiness.runner.subprocess.run",
                    side_effect=self._solver_process(timeout=True),
                ):
                    report = self._run(spec, prepared, solver, root / "run", None)
            self.assertFalse(report["complete"])
            self.assertTrue(report["timed_out"])
            self.assertIsNone(report["returncode"])

    def test_solver_hash_mismatch_is_rejected_before_staging(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            spec, _inp, _meta, solver = self._case(root)
            with patch("fea_readiness.pipeline.native_check", side_effect=self._synthetic_adapter):
                prepared = self._prepared(spec)
                with patch("fea_readiness.runner.subprocess.run") as mocked:
                    with self.assertRaisesRegex(ValueError, "Solver executable identity mismatch"):
                        run_checked(spec, prepared, solver, "0" * 64, root / "run", timeout_s=1)
            mocked.assert_not_called()
            self.assertFalse((root / "run").exists())

    def test_staged_input_or_meta_drift_is_rejected(self):
        for drift_name in ("job.inp", "job.meta.json"):
            with self.subTest(drift_name=drift_name), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                spec, _inp, _meta, solver = self._case(root)
                real_copy2 = runner_module.shutil.copy2

                def copy_and_drift(source, destination, *, _real=real_copy2):
                    result = _real(source, destination)
                    if Path(destination).name == drift_name:
                        Path(destination).write_bytes(Path(destination).read_bytes() + b"drift\n")
                    return result

                with patch("fea_readiness.pipeline.native_check", side_effect=self._synthetic_adapter):
                    prepared = self._prepared(spec)
                    with patch.object(runner_module.shutil, "copy2", side_effect=copy_and_drift):
                        with self.assertRaisesRegex(ValueError, "Staged input identity drift"):
                            run_checked(spec, prepared, solver, sha256(solver), root / "run", timeout_s=1)
                self.assertFalse((root / "run" / "run.json").exists())


if __name__ == "__main__":
    unittest.main()
