"""Recalibrate selected observations without repeating frame selection."""
import json
from pathlib import Path

import yaml

from .cache import read_cache, write_cache
from .models import FrameRecord
from .nn_detector import NNDetector
from .pipeline import detect_groups
from .rig import load_rig
from .sources import _read_timestamp_rows, read_bag, synchronize


def run_reusing_datawash(*, previous, source, rig_file, target_file, output,
                        detector, config, model_path, device, kalibr_image, detection_cache=None,
                        kalibr_args=None):
    from .orchestrator import _run_kalibr

    previous = previous.resolve()
    old = json.loads((previous / "summary.json").read_text())
    if source != Path(old["input"]).resolve() or detector != old["detector"]:
        raise ValueError("Reusing Datawash requires the same input and detector")
    rig = load_rig(rig_file)
    old_rig = load_rig(old["rig"])
    signature = lambda r: [(c.camera_id, c.topic, c.directory, c.frame_id) for c in r.cameras]
    if signature(rig) != signature(old_rig) or rig.sync_tolerance_ns != old_rig.sync_tolerance_ns:
        raise ValueError("Only camera models may change when reusing Datawash")
    if yaml.safe_load(target_file.read_text()) != yaml.safe_load(Path(old["target"]).read_text()):
        raise ValueError("Reusing Datawash requires the same target")
    clean_bag = Path(old["datawash"]["clean_ros1_bag"])
    if not clean_bag.is_file():
        raise FileNotFoundError(clean_bag)
    # Never write into an existing run, even when --overwrite was supplied.
    if output.exists():
        raise FileExistsError(f"Reuse requires a new output directory: {output}")
    selected_cache = (Path(detection_cache).resolve() if detection_cache is not None else
                      previous / "datawash" / "detections_selected.detcache")
    if detection_cache is not None and (detector != "nn" or not selected_cache.is_dir()):
        raise ValueError("--detection-cache requires NN-Detector and an existing cache directory")
    cached = selected_cache.is_dir()
    if cached and detector == "nn":
        manifest, detections = read_cache(selected_cache, expected_model=model_path, expected_detector=detector)
        if manifest["camera_ids"] != list(rig.camera_ids):
            raise ValueError("Detection cache camera IDs do not match the rig")
        if detection_cache is not None:
            selected = read_bag(clean_bag, rig)
            expected = {(camera, f.timestamp_ns) for camera, frames in selected.items() for f in frames}
            actual = {(d.camera_id, d.timestamp_ns) for d in detections}
            if actual != expected or len(detections) != len(expected):
                raise ValueError("Detection cache observations do not match the selected bag")
    output.mkdir(parents=True)
    # Freeze the effective configurations for future model comparisons.
    effective_rig = output / "rig.yaml"
    effective_rig.write_text(rig_file.read_text())
    effective_target = output / "target.yaml"
    effective_target.write_text(target_file.read_text())
    providers = []
    if detector == "nn" and not cached:
        if old["input_type"] != "sequence":
            raise ValueError("Missing NN cache: recovery currently requires original image sequences")
        selected = read_bag(clean_bag, rig)
        records = {}
        for camera in rig.cameras:
            wanted = {f.timestamp_ns for f in selected[camera.camera_id]}
            directory = source / camera.directory
            if not directory.exists():
                directory = source / "mav0" / camera.directory
            rows = _read_timestamp_rows(directory)
            frames = [FrameRecord(camera.camera_id, i, t, p.read_bytes(), p.suffix[1:], p)
                      for i, t, p in rows if t in wanted]
            if len(frames) != len(wanted):
                raise ValueError(f"Cannot uniquely recover selected original frames: {camera.camera_id}")
            records[camera.camera_id] = frames
        nn = NNDetector(model_path, device=device)
        detections = detect_groups(synchronize(records, rig.sync_tolerance_ns), detector=nn, config=config)
        providers = list(nn.providers)
        # Old completed runs did not retain the confidence threshold explicitly.
        # The original configuration is required when rebuilding their cache.
        selected_cache = write_cache(
            output / "datawash" / "detections_selected.detcache", detections,
            model_path=model_path, confidence_threshold=config.detector_confidence,
            camera_ids=rig.camera_ids, detector=detector,
        )
    elif detector == "nn":
        # Keep a local copy of the small cache; the large bag remains read-only.
        import shutil
        destination = output / "datawash" / "detections_selected.detcache"
        shutil.copytree(selected_cache, destination)
        selected_cache = destination
    _run_kalibr(detector=detector, clean_bag=clean_bag, selected_cache=selected_cache,
                rig_path=effective_rig, target_path=effective_target,
                output_dir=output / "kalibr", docker_image=kalibr_image, kalibr_args=kalibr_args)
    summary = dict(old)
    summary.update(output=str(output), rig=str(effective_rig), target=str(effective_target),
                   models=list(rig.kalibr_models), kalibr_output=str(output / "kalibr"),
                   kalibr_image=kalibr_image, requested_device=device,
                   reused_datawash_from=str(previous), rebuilt_selected_detections=not cached and detector == "nn")
    summary["kalibr_args"] = list(kalibr_args or [])
    summary["datawash"] = dict(old["datawash"])
    summary["datawash"]["execution_providers"] = providers
    (output / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    return summary
