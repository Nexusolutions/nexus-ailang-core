#!/usr/bin/env python3
"""Tests for modules with 0% coverage: dap, jit, event_loop, doctor,
selector, experiment, project_templates, llvm_backend, modules (FIX1-6)."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


class TestDAP(unittest.TestCase):
    """FIX1: DAP server tests."""

    def test_dap_server_init(self):
        from ailang.dap import DAPServer
        s = DAPServer()
        self.assertIsNotNone(s)
        self.assertEqual(s.seq, 1)
        self.assertIsNone(s.dbg)

    def test_dap_capabilities(self):
        from ailang.dap import DAPServer
        s = DAPServer()
        # Check it has all the handler methods
        for method in ['_handle_initialize', '_handle_launch', '_handle_set_breakpoints',
                       '_handle_continue', '_handle_step', '_handle_threads',
                       '_handle_stack_trace', '_handle_scopes', '_handle_variables',
                       '_handle_evaluate', '_handle_terminate', '_handle_disconnect']:
            self.assertTrue(hasattr(s, method), f"DAPServer missing {method}")


class TestJIT(unittest.TestCase):
    """FIX2: JIT compiler tests."""

    def test_jit_init(self):
        from ailang.backends.native.jit import JITCompiler
        jit = JITCompiler(threshold=10)
        self.assertEqual(jit.threshold, 10)
        self.assertTrue(jit.enabled)

    def test_jit_record_call(self):
        from ailang.backends.native.jit import JITCompiler
        jit = JITCompiler(threshold=3)
        self.assertFalse(jit.record_call('fn1'))  # call 1
        self.assertFalse(jit.record_call('fn1'))  # call 2
        self.assertTrue(jit.record_call('fn1'))   # call 3 = threshold

    def test_jit_stats(self):
        from ailang.backends.native.jit import JITCompiler
        jit = JITCompiler(threshold=5)
        jit.record_call('a')
        jit.record_call('a')
        stats = jit.stats()
        self.assertEqual(stats['total_functions'], 1)
        self.assertEqual(stats['total_calls'], 2)

    def test_jit_reset(self):
        from ailang.backends.native.jit import JITCompiler
        jit = JITCompiler(threshold=5)
        jit.record_call('a')
        jit.reset()
        self.assertEqual(len(jit._profiles), 0)


class TestEventLoop(unittest.TestCase):
    """FIX3: Event loop tests."""

    def test_future_set_result(self):
        from ailang.runtime.event_loop import Future
        f = Future()
        self.assertFalse(f.done)
        f.set_result(42)
        self.assertTrue(f.done)
        self.assertEqual(f.result(), 42)

    def test_future_set_error(self):
        from ailang.runtime.event_loop import Future
        f = Future()
        err = ValueError("test error")
        f.set_error(err)
        self.assertTrue(f.done)
        with self.assertRaises(ValueError):
            f.result()

    def test_future_callback(self):
        from ailang.runtime.event_loop import Future
        f = Future()
        results = []
        f.add_done_callback(lambda fut: results.append(fut.result()))
        f.set_result(99)
        self.assertEqual(results, [99])

    def test_event_loop_simple_task(self):
        from ailang.runtime.event_loop import EventLoop, Future
        loop = EventLoop()

        def simple_coro():
            return 42
            yield  # make it a generator

        fut = loop.create_task(simple_coro(), name='test')
        loop.run_until_complete(fut)
        self.assertTrue(fut.done)
        self.assertEqual(fut.result(), 42)

    def test_event_loop_await_future(self):
        from ailang.runtime.event_loop import EventLoop, Future
        loop = EventLoop()

        def awaiting_coro():
            inner = Future()
            inner.set_result("hello")
            val = yield inner  # await
            return val.upper()

        fut = loop.create_task(awaiting_coro(), name='await')
        loop.run_until_complete(fut)
        self.assertEqual(fut.result(), "HELLO")

    def test_event_loop_concurrent(self):
        from ailang.runtime.event_loop import EventLoop
        loop = EventLoop()

        def compute(n):
            return n * 2
            yield

        futs = [loop.create_task(compute(i), name=f'c{i}') for i in range(5)]
        loop.run_until_complete()
        results = [f.result() for f in futs]
        self.assertEqual(results, [0, 2, 4, 6, 8])


class TestDoctor(unittest.TestCase):
    """FIX4: Doctor tests."""

    def test_doctor_runs(self):
        from ailang.doctor import run_doctor
        # doctor should return 0 (all OK) or 1 (some fail)
        rc = run_doctor()
        self.assertIn(rc, [0, 1])

    def test_doctor_checks_runtime(self):
        from ailang.doctor import _check_runtime
        result = _check_runtime()
        self.assertTrue(result['ok'])

    def test_doctor_checks_vm(self):
        from ailang.doctor import _check_vm
        result = _check_vm()
        self.assertTrue(result['ok'])


class TestSelector(unittest.TestCase):
    """FIX5a: Selector module tests."""

    def test_selector_calibration(self):
        from ailang.lang.stdlib.selector import AdaptiveSelector
        s = AdaptiveSelector(['a', 'b', 'c'])
        self.assertEqual(s.next_strategy(), 'a')
        self.assertEqual(s.next_strategy(), 'b')
        self.assertEqual(s.next_strategy(), 'c')
        self.assertTrue(s.calibrated)

    def test_selector_chooses_best(self):
        from ailang.lang.stdlib.selector import AdaptiveSelector
        s = AdaptiveSelector(['greedy', 'local', 'qaoa'])
        s.calibrated = True
        s.update('greedy', 0.5, 40, 10)
        s.update('local', 0.2, 45, 20)
        s.update('qaoa', 0.8, 30, 100)
        self.assertEqual(s.next_strategy(), 'local')  # lowest loss

    def test_selector_compute_loss(self):
        from ailang.lang.stdlib.selector import AdaptiveSelector
        s = AdaptiveSelector(['a'])
        loss = s.compute_loss(quality=80, quality_ref=100, cost=10, cost_ref=20)
        # L = 0.7 * (1 - 80/100) + 0.3 * min(10/20, 1) = 0.14 + 0.15 = 0.29
        self.assertAlmostEqual(loss, 0.29, places=2)

    def test_bootstrap_paired(self):
        from ailang.lang.stdlib.selector import bootstrap_paired
        result = bootstrap_paired([0.05, 0.10, 0.03], [0.06, 0.08, 0.05])
        self.assertIn('mean_difference', result)
        self.assertIn('ci_95', result)
        self.assertIn('significant', result)


class TestExperiment(unittest.TestCase):
    """FIX5b: Experiment module tests."""

    def test_experiment_create(self):
        from ailang.lang.stdlib.experiment import create
        exp = create('test-exp')
        self.assertEqual(exp.name, 'test-exp')

    def test_experiment_record_and_summary(self):
        from ailang.lang.stdlib.experiment import create
        exp = create('maxcut')
        exp.set_seeds([1, 2, 3])
        exp.set_baselines(['greedy'])
        exp.record('greedy', 1, {'gap': 0.0, 'evaluations': 10})
        exp.record('greedy', 2, {'gap': 0.1, 'evaluations': 10})
        exp.record('greedy', 3, {'gap': 0.05, 'evaluations': 10})
        summary = exp.summary()
        self.assertIn('greedy', summary)
        self.assertAlmostEqual(summary['greedy']['mean_gap'], 0.05, places=2)


class TestProjectTemplates(unittest.TestCase):
    """FIX5c: Project templates tests."""

    def test_list_templates(self):
        from ailang.project_templates import list_templates
        templates = list_templates()
        self.assertIn('app', templates)
        self.assertIn('lib', templates)
        self.assertIn('web', templates)
        self.assertIn('script', templates)

    def test_create_app_template(self):
        import tempfile, os
        from ailang.project_templates import create_project
        with tempfile.TemporaryDirectory() as tmp:
            root = create_project('testapp', 'app', dest=tmp)
            self.assertTrue((root / 'main.ailang').exists())
            self.assertTrue((root / 'ailang.toml').exists())
            self.assertTrue((root / 'README.md').exists())

    def test_create_lib_template(self):
        import tempfile
        from ailang.project_templates import create_project
        with tempfile.TemporaryDirectory() as tmp:
            root = create_project('testlib', 'lib', dest=tmp)
            self.assertTrue((root / 'lib.ailang').exists())

    def test_create_web_template(self):
        import tempfile
        from ailang.project_templates import create_project
        with tempfile.TemporaryDirectory() as tmp:
            root = create_project('testapi', 'web', dest=tmp)
            self.assertTrue((root / 'server.ailang').exists())

    def test_create_script_template(self):
        import tempfile
        from ailang.project_templates import create_project
        with tempfile.TemporaryDirectory() as tmp:
            root = create_project('testscript', 'script', dest=tmp)
            self.assertTrue((root / 'main.ailang').exists())


class TestLLVMBackend(unittest.TestCase):
    """FIX6: LLVM backend tests."""

    def test_llvm_ir_generation(self):
        try:
            import llvmlite
        except ImportError:
            self.skipTest("llvmlite not installed")
        from ailang.backends.native import compile_to_llvm_ir
        ir = compile_to_llvm_ir("fn add(a, b) { return a + b }")
        self.assertIn("define", ir)
        self.assertIn("i64", ir)

    def test_llvm_with_variables(self):
        try:
            import llvmlite
        except ImportError:
            self.skipTest("llvmlite not installed")
        from ailang.backends.native import compile_to_llvm_ir
        ir = compile_to_llvm_ir("fn compute(a, b) { let x = a + b\n let y = x * 2\n return y }")
        self.assertIn("alloca", ir)
        self.assertIn("store", ir)
        self.assertIn("load", ir)


class TestWASMBackend(unittest.TestCase):
    """FIX6b: WASM backend tests (no external deps needed)."""

    def test_wat_generation(self):
        from ailang.backends.wasm import compile_to_wat
        wat = compile_to_wat("fn add(a, b) { return a + b }")
        self.assertIn("(module", wat)
        self.assertIn("func", wat)

    def test_wat_with_variables(self):
        from ailang.backends.wasm import compile_to_wat
        wat = compile_to_wat("fn compute(a, b) { let x = a + b\n return x }")
        self.assertIn("local", wat)
        self.assertIn("i64.add", wat)

    def test_wat_main_export(self):
        from ailang.backends.wasm import compile_to_wat
        wat = compile_to_wat("1 + 2")
        self.assertIn("(module", wat)
        self.assertIn("main", wat)


class TestModuleResolver(unittest.TestCase):
    """FIX7: ModuleResolver tests."""

    def test_builtin_load(self):
        from ailang.modules import ModuleResolver
        r = ModuleResolver()
        mod = r.load('math')
        self.assertIsNotNone(mod)

    def test_user_module_load(self):
        import tempfile, os
        from ailang.modules import ModuleResolver
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, 'hello.ailang'), 'w') as f:
                f.write('let greeting = "hi"\nlet n = 42\n')
            r = ModuleResolver(module_path=[tmp])
            mod = r.load('hello')
            self.assertEqual(mod.greeting, "hi")
            self.assertEqual(mod.n, 42)

    def test_module_not_found(self):
        from ailang.modules import ModuleResolver, ModuleNotFoundError
        r = ModuleResolver()
        with self.assertRaises(ModuleNotFoundError):
            r.load('nonexistent_module_xyz')

    def test_circular_dependency_detection(self):
        import tempfile, os
        from ailang.modules import ModuleResolver, CircularImportError
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, 'a.ailang'), 'w') as f:
                f.write('import b\nlet a_val = 1\n')
            with open(os.path.join(tmp, 'b.ailang'), 'w') as f:
                f.write('import a\nlet b_val = 2\n')
            r = ModuleResolver(module_path=[tmp])
            with self.assertRaises(CircularImportError):
                r.load('a')

    def test_module_cache(self):
        import tempfile, os
        from ailang.modules import ModuleResolver
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, 'cached.ailang'), 'w') as f:
                f.write('let x = 100\n')
            r = ModuleResolver(module_path=[tmp])
            r.load('cached')
            r.load('cached')  # should use cache
            stats = r.stats()
            self.assertEqual(stats['cache_hits'], 1)


class TestSpawnFuture(unittest.TestCase):
    """FIX8: spawn returns a capturable result."""

    def test_spawn_returns_value(self):
        from ailang.lang.interpreter import run_source
        # spawn is a statement, but the spawned function's return
        # is captured internally. Test that spawn doesn't crash.
        result = run_source("""
fn worker() { return 42 }
let f = spawn worker()
f
""")
        # spawn returns something (could be None or the result)
        self.assertIsNotNone(result)


if __name__ == "__main__":
    unittest.main(verbosity=2)
