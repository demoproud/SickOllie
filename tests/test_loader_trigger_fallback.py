from __future__ import annotations

import importlib.util
import json
import sys
import types
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_NAME = "sickollie_loader_test_pack"


def _install_runtime_stubs() -> None:
    package = types.ModuleType(PACKAGE_NAME)
    package.__path__ = [str(ROOT)]
    sys.modules[PACKAGE_NAME] = package

    folder_paths = types.ModuleType("folder_paths")
    folder_paths.get_filename_list = lambda _kind: []
    folder_paths.get_full_path_or_raise = lambda _kind, _name: "/tmp/fake.safetensors"
    sys.modules["folder_paths"] = folder_paths

    comfy = types.ModuleType("comfy")
    comfy.__path__ = []
    comfy_sd = types.ModuleType("comfy.sd")
    comfy_utils = types.ModuleType("comfy.utils")
    comfy.sd = comfy_sd
    comfy.utils = comfy_utils
    sys.modules["comfy"] = comfy
    sys.modules["comfy.sd"] = comfy_sd
    sys.modules["comfy.utils"] = comfy_utils
    sys.modules.setdefault("torch", types.ModuleType("torch"))


def _load(name: str):
    qualified = f"{PACKAGE_NAME}.{name}"
    spec = importlib.util.spec_from_file_location(qualified, ROOT / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[qualified] = module
    spec.loader.exec_module(module)
    return module


_install_runtime_stubs()
_load("civitai_trigger")
LOADERS = (_load("loader_core"), _load("studio_loader_core"))


class LoaderTriggerFallbackTests(unittest.TestCase):
    def test_civitai_fallback_is_shared_by_classic_and_studio(self) -> None:
        for loader in LOADERS:
            with self.subTest(module=loader.__name__), mock.patch.object(
                loader,
                "_load_safetensors_metadata",
                return_value={},
            ), mock.patch.object(
                loader,
                "detect_civitai_trigger",
                return_value=("Gadget & the Gadgetinis", "civitai.trainedWords"),
            ):
                self.assertEqual(
                    loader._detect_main_trigger("Gadget.safetensors"),
                    ("Gadget & the Gadgetinis", "civitai.trainedWords"),
                )

    def test_saved_override_beats_all_automatic_detection(self) -> None:
        custom = "jester, blue-skinned tiefling, curved horns, long pointed ears, violet eyes"
        for loader in LOADERS:
            with self.subTest(module=loader.__name__), mock.patch.object(
                loader, "_saved_trigger_override", return_value=(custom, "user.override")
            ), mock.patch.object(loader, "_detect_automatic_trigger") as automatic:
                self.assertEqual(loader._detect_main_trigger("Jester.safetensors"), (custom, "user.override"))
                automatic.assert_not_called()

    def test_saved_override_is_not_reported_as_detected_evidence(self) -> None:
        custom = "jester, blue-skinned tiefling, curved horns"
        for loader in LOADERS:
            with self.subTest(module=loader.__name__), mock.patch.object(
                loader, "_saved_trigger_override", return_value=(custom, "user.override")
            ), mock.patch.object(
                loader, "_load_safetensors_metadata", return_value={"trigger_words": "embedded_trigger"}
            ), mock.patch.object(loader, "detect_civitai_triggers", return_value=([], "")):
                candidates = loader._trigger_candidates("Jester.safetensors")
                self.assertFalse(any(item.get("source") == "user.override" for item in candidates))
                self.assertTrue(any(item.get("raw") == "embedded_trigger" for item in candidates))

    def test_embedded_trigger_remains_first_priority(self) -> None:
        for loader in LOADERS:
            with self.subTest(module=loader.__name__), mock.patch.object(
                loader,
                "_load_safetensors_metadata",
                return_value={"trigger_words": "embedded_trigger"},
            ), mock.patch.object(loader, "detect_civitai_trigger") as fallback:
                self.assertEqual(
                    loader._detect_main_trigger("Gadget.safetensors"),
                    ("embedded_trigger", "trigger_words"),
                )
                fallback.assert_not_called()

    def test_modelspec_title_is_never_an_automatic_trigger(self) -> None:
        for loader in LOADERS:
            with self.subTest(module=loader.__name__), mock.patch.object(
                loader,
                "_load_safetensors_metadata",
                return_value={"modelspec.title": "Generic model title"},
            ), mock.patch.object(
                loader,
                "detect_civitai_trigger",
                return_value=("", ""),
            ):
                self.assertEqual(
                    loader._detect_main_trigger("Gadget.safetensors"),
                    ("", ""),
                )

    def test_weighted_civitai_recipe_is_not_auto_injected(self) -> None:
        recipe = "C- String_ByMrJohn, (cstring, minimal c-string underwear:1.6), no side straps"
        for loader in LOADERS:
            with self.subTest(module=loader.__name__), mock.patch.object(
                loader, "_load_safetensors_metadata", return_value={}
            ), mock.patch.object(
                loader, "detect_civitai_trigger", return_value=(recipe, "civitai.trainedWords")
            ):
                self.assertEqual(loader._detect_main_trigger("Gadget.safetensors"), ("", ""))

    def test_studio_custom_trigger_persists_in_catalog_and_can_be_cleared(self) -> None:
        studio = LOADERS[1]
        solo_catalog = _load("solo_catalog") if f"{PACKAGE_NAME}.solo_catalog" not in sys.modules else sys.modules[f"{PACKAGE_NAME}.solo_catalog"]
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            model = Path(tmp) / "Jester.safetensors"
            model.write_bytes(b"fake-lora-content")
            catalog = solo_catalog.SoloCatalog(Path(tmp) / "catalog.sqlite3")
            custom = "jester, blue-skinned tiefling, curved horns, long pointed ears, violet eyes"
            with mock.patch.object(studio, "_TRIGGER_CATALOG", catalog), mock.patch.object(
                studio.folder_paths, "get_full_path_or_raise", return_value=str(model)
            ), mock.patch.object(
                studio, "_detect_automatic_trigger", return_value=("Jester", "trigger_words")
            ):
                self.assertEqual(studio._save_trigger_override("Jester.safetensors", custom), (custom, "user.override"))
                self.assertEqual(studio._detect_main_trigger("Jester.safetensors"), (custom, "user.override"))
                self.assertTrue(studio._clear_trigger_override("Jester.safetensors"))
                self.assertEqual(studio._detect_main_trigger("Jester.safetensors"), ("Jester", "trigger_words"))

    def test_studio_trigger_overrides_are_independent_per_lora(self) -> None:
        studio = LOADERS[1]
        solo_catalog = _load("solo_catalog") if f"{PACKAGE_NAME}.solo_catalog" not in sys.modules else sys.modules[f"{PACKAGE_NAME}.solo_catalog"]
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            jester_model = Path(tmp) / "Jester.safetensors"
            shion_model = Path(tmp) / "Shion.safetensors"
            jester_model.write_bytes(b"jester-lora")
            shion_model.write_bytes(b"shion-lora")
            catalog = solo_catalog.SoloCatalog(Path(tmp) / "catalog.sqlite3")
            paths = {
                "Jester.safetensors": str(jester_model),
                "Shion.safetensors": str(shion_model),
            }
            jester = "jester, blue-skinned tiefling, curved horns, long pointed ears, violet eyes, blue arrow-tipped tail"
            shion = "shion, female android, white synthetic skin, segmented forehead armor, red oni horns"
            with mock.patch.object(studio, "_TRIGGER_CATALOG", catalog), mock.patch.object(
                studio.folder_paths, "get_full_path_or_raise", side_effect=lambda _kind, name: paths[name]
            ):
                studio._save_trigger_override("Jester.safetensors", jester)
                studio._save_trigger_override("Shion.safetensors", shion)
                self.assertEqual(studio._detect_main_trigger("Jester.safetensors"), (jester, "user.override"))
                self.assertEqual(studio._detect_main_trigger("Shion.safetensors"), (shion, "user.override"))
                self.assertEqual(studio._detect_main_trigger("Jester.safetensors"), (jester, "user.override"))


    def test_epoch_family_signature_requires_same_folder_and_same_filename_except_epoch(self) -> None:
        trigger_resolution = sys.modules[f"{PACKAGE_NAME}.trigger_resolution"]
        selected = "SickOllie/characters/karissa/karissa_krea2_epoch_06.safetensors"
        candidates = [
            f"SickOllie/characters/karissa/karissa_krea2_epoch_{epoch:02d}.safetensors"
            for epoch in range(3, 11)
        ] + [
            "SickOllie/characters/karissa/karissa_other_epoch_06.safetensors",
            "SickOllie/characters/elsewhere/karissa_krea2_epoch_06.safetensors",
        ]
        signature = trigger_resolution.epoch_family_signature(selected)
        matches = trigger_resolution.matching_epoch_family(selected, candidates)

        self.assertEqual(signature["folder"], "SickOllie/characters/karissa")
        self.assertEqual(signature["pattern"], "karissa_krea2_epoch_*.safetensors")
        self.assertEqual(len(matches), 8)
        self.assertNotIn(candidates[-1], matches)
        self.assertNotIn(candidates[-2], matches)

    def test_studio_epoch_family_override_applies_to_matching_epochs_and_future_epochs(self) -> None:
        studio = LOADERS[1]
        solo_catalog = _load("solo_catalog") if f"{PACKAGE_NAME}.solo_catalog" not in sys.modules else sys.modules[f"{PACKAGE_NAME}.solo_catalog"]
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            catalog = solo_catalog.SoloCatalog(Path(tmp) / "catalog.sqlite3")
            custom = "karissa, freckles, large round green eyes"
            names = [
                "SickOllie/characters/karissa/karissa_krea2_epoch_03.safetensors",
                "SickOllie/characters/karissa/karissa_krea2_epoch_06.safetensors",
                "SickOllie/characters/karissa/karissa_krea2_epoch_10.safetensors",
            ]
            with mock.patch.object(studio, "_TRIGGER_CATALOG", catalog), mock.patch.object(
                studio, "_detect_automatic_trigger", return_value=("automatic", "trigger_words")
            ):
                self.assertEqual(
                    studio._save_trigger_family_override(names[1], custom),
                    (custom, "user.family_override"),
                )
                self.assertEqual(studio._detect_main_trigger(names[0]), (custom, "user.family_override"))
                self.assertEqual(studio._detect_main_trigger(names[2]), (custom, "user.family_override"))
                # A newly-added epoch inherits the persistent family rule without
                # needing another per-file save.
                future = "SickOllie/characters/karissa/karissa_krea2_epoch_11.safetensors"
                self.assertEqual(studio._detect_main_trigger(future), (custom, "user.family_override"))
                unrelated = "SickOllie/characters/karissa/karissa_other_epoch_11.safetensors"
                self.assertEqual(studio._detect_main_trigger(unrelated), ("automatic", "trigger_words"))

    def test_exact_trigger_override_beats_epoch_family_and_clear_reveals_family(self) -> None:
        studio = LOADERS[1]
        solo_catalog = _load("solo_catalog") if f"{PACKAGE_NAME}.solo_catalog" not in sys.modules else sys.modules[f"{PACKAGE_NAME}.solo_catalog"]
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            model = Path(tmp) / "karissa_krea2_epoch_06.safetensors"
            model.write_bytes(b"karissa-epoch-six")
            catalog = solo_catalog.SoloCatalog(Path(tmp) / "catalog.sqlite3")
            family = "karissa family trigger"
            exact = "epoch six special trigger"
            name = "characters/karissa/karissa_krea2_epoch_06.safetensors"
            with mock.patch.object(studio, "_TRIGGER_CATALOG", catalog), mock.patch.object(
                studio.folder_paths, "get_full_path_or_raise", return_value=str(model)
            ), mock.patch.object(
                studio, "_detect_automatic_trigger", return_value=("automatic", "trigger_words")
            ):
                studio._save_trigger_family_override(name, family)
                studio._save_trigger_override(name, exact)
                self.assertEqual(studio._detect_main_trigger(name), (exact, "user.override"))
                self.assertTrue(studio._clear_trigger_override(name))
                self.assertEqual(studio._detect_main_trigger(name), (family, "user.family_override"))
                self.assertTrue(studio._clear_trigger_family_override(name))
                self.assertEqual(studio._detect_main_trigger(name), ("automatic", "trigger_words"))


    def test_classic_loader_reads_the_same_epoch_family_rule(self) -> None:
        classic, studio = LOADERS
        solo_catalog = _load("solo_catalog") if f"{PACKAGE_NAME}.solo_catalog" not in sys.modules else sys.modules[f"{PACKAGE_NAME}.solo_catalog"]
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            catalog = solo_catalog.SoloCatalog(Path(tmp) / "catalog.sqlite3")
            name = "characters/karissa/karissa_krea2_epoch_06.safetensors"
            sibling = "characters/karissa/karissa_krea2_epoch_09.safetensors"
            custom = "shared karissa trigger"
            with mock.patch.object(studio, "_TRIGGER_CATALOG", catalog):
                studio._save_trigger_family_override(name, custom)
            with mock.patch.object(classic, "_TRIGGER_CATALOG", catalog), mock.patch.object(
                classic, "_detect_automatic_trigger", return_value=("automatic", "trigger_words")
            ):
                self.assertEqual(classic._detect_main_trigger(sibling), (custom, "user.family_override"))

    def test_studio_secondary_stack_accepts_new_and_legacy_shapes(self) -> None:
        studio = LOADERS[1]
        new_values = studio.LoaderCoreEngine._dynamic_secondary_values({
            "secondary_lora_stack": [
                {"on": True, "lora": "characters/a.safetensors", "strength": 1.2},
                {"on": False, "lora": "styles/b.safetensors", "strength": 0.5},
            ]
        })
        json_values = studio.LoaderCoreEngine._dynamic_secondary_values({
            "secondary_lora_stack": json.dumps([
                {"on": True, "lora": "characters/a.safetensors", "strength": 1.2},
                {"on": False, "lora": "styles/b.safetensors", "strength": 0.5},
            ])
        })
        legacy_values = studio.LoaderCoreEngine._dynamic_secondary_values({
            "secondary_lora_2": {"on": False, "lora": "styles/b.safetensors", "strength": 0.5},
            "secondary_lora_1": {"on": True, "lora": "characters/a.safetensors", "strength": 1.2},
        })

        self.assertEqual(new_values, [
            ("secondary_lora_1", True, "characters/a.safetensors", 1.2),
            ("secondary_lora_2", False, "styles/b.safetensors", 0.5),
        ])
        self.assertEqual(json_values, new_values)
        self.assertEqual(legacy_values, new_values)


    def test_studio_load_core_applies_enabled_json_secondary(self) -> None:
        studio = LOADERS[1]
        engine = studio.LoaderCoreEngine()
        stack = json.dumps([
            {"on": True, "lora": "characters/a.safetensors", "strength": 1.25},
            {"on": False, "lora": "styles/b.safetensors", "strength": 0.5},
        ])

        with mock.patch.object(engine, "_load_base_model", return_value="base"), \
             mock.patch.object(engine, "_load_lora_state", return_value=("state-a", {})) as load_state, \
             mock.patch.object(engine, "_apply_model_lora", return_value="with-secondary") as apply_lora, \
             mock.patch.object(studio, "_folder_loras", return_value=[]):
            result = engine.load_core(
                diffusion_model="model.safetensors",
                weight_dtype="default",
                folder_name=studio.ALL_FOLDERS,
                epoch_filter=studio.ALL_EPOCHS,
                main_enabled=False,
                main_lora=studio.NO_LORA,
                main_strength=1.0,
                include_subfolders=True,
                loop_folder=True,
                control_after_generate="fixed",
                skip_none_during_cycle=True,
                off_name="no_lora",
                auto_clean_name=False,
                cleanup_rules=studio.DEFAULT_CLEAN_NAME_MODE,
                library_filter=studio.ALL_LIBRARY_STATES,
                lora_sort=studio.SORT_NAME,
                secondary_lora_stack=stack,
            )

        self.assertEqual(result[0], "with-secondary")
        load_state.assert_called_once_with("characters/a.safetensors")
        apply_lora.assert_called_once_with("base", "state-a", 1.25, {})

    def test_studio_secondary_stack_is_declared_execution_input(self) -> None:
        studio = LOADERS[1]
        optional = studio.LoaderCoreEngine.INPUT_TYPES()["optional"]
        self.assertIn("secondary_lora_stack", optional.data)
        self.assertEqual(optional.data["secondary_lora_stack"][0], "STRING")


    def test_inactive_main_lora_never_emits_trigger(self) -> None:
        for loader in LOADERS:
            for enabled, strength in ((False, 1.0), (True, 0.0)):
                with self.subTest(module=loader.__name__, enabled=enabled, strength=strength):
                    engine = loader.LoaderCoreEngine()
                    with mock.patch.object(engine, "_load_base_model", return_value="base"), \
                         mock.patch.object(loader, "_folder_loras", return_value=["characters/jester.safetensors"]), \
                         mock.patch.object(loader, "_detect_main_trigger", return_value=("should-not-emit", "user.override")) as detect:
                        result = engine.load_core(
                            diffusion_model="model.safetensors",
                            weight_dtype="default",
                            folder_name=loader.ALL_FOLDERS,
                            epoch_filter=loader.ALL_EPOCHS,
                            main_enabled=enabled,
                            main_lora="characters/jester.safetensors",
                            main_strength=strength,
                            include_subfolders=True,
                            loop_folder=True,
                            control_after_generate="fixed",
                            skip_none_during_cycle=True,
                            off_name="no_lora",
                            auto_clean_name=False,
                            cleanup_rules=loader.DEFAULT_CLEAN_NAME_MODE,
                        )

                    trigger_index = loader.LoaderCoreEngine.RETURN_NAMES.index("main_trigger")
                    self.assertEqual(result[trigger_index], "")
                    detect.assert_not_called()

    def test_studio_loader_emits_full_saved_override_on_main_trigger_output(self) -> None:
        studio = LOADERS[1]
        engine = studio.LoaderCoreEngine()
        override = (
            "jester, blue-skinned tiefling, uniformly blue skin over her entire body, "
            "curved horns, long pointed ears, violet eyes, blue arrow-tipped tail"
        )

        with mock.patch.object(engine, "_load_base_model", return_value="base"), \
             mock.patch.object(engine, "_load_lora_state", return_value=("state", {})), \
             mock.patch.object(engine, "_apply_model_lora", return_value="with-main"), \
             mock.patch.object(studio, "_folder_loras", return_value=["characters/jester.safetensors"]), \
             mock.patch.object(studio, "_detect_main_trigger", return_value=(override, "user.override")):
            result = engine.load_core(
                diffusion_model="model.safetensors",
                weight_dtype="default",
                folder_name=studio.ALL_FOLDERS,
                epoch_filter=studio.ALL_EPOCHS,
                main_enabled=True,
                main_lora="characters/jester.safetensors",
                main_strength=1.0,
                include_subfolders=True,
                loop_folder=True,
                control_after_generate="fixed",
                skip_none_during_cycle=True,
                off_name="no_lora",
                auto_clean_name=False,
                cleanup_rules=studio.DEFAULT_CLEAN_NAME_MODE,
                library_filter=studio.ALL_LIBRARY_STATES,
                lora_sort=studio.SORT_NAME,
            )

        self.assertEqual(studio.LoaderCoreEngine.RETURN_NAMES[2], "main_trigger")
        self.assertEqual(result[1], "jester")
        self.assertEqual(result[2], override)


if __name__ == "__main__":
    unittest.main()
