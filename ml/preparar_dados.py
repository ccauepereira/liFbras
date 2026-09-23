#!/usr/bin/env python3
"""Inspect and make a deterministic landmark-only subset of LIBRAS-EQT-UECE."""

from __future__ import annotations

import argparse
import io
import json
from collections import Counter, defaultdict
from pathlib import Path
from zipfile import ZipFile

import numpy as np


ROOT = "Landmarks/Libras-EQT-UECE (Hand Landmarks)/"
DEFAULT_ZIP = Path("dataset/libras-eqt-uece/Landmarks.zip")
DEFAULT_OUTPUT = Path("dataset/libras-eqt-uece/mvp-hand-landmarks.npz")


def iter_landmark_files(archive: ZipFile):
    for name in sorted(archive.namelist()):
        if not name.startswith(ROOT) or not name.endswith(".npy"):
            continue
        relative = name[len(ROOT) :].split("/")
        if len(relative) != 3:
            continue
        class_name, signer, filename = relative
        yield name, class_name, signer, filename


def read_array(archive: ZipFile, name: str) -> np.ndarray:
    array = np.load(io.BytesIO(archive.read(name)), allow_pickle=False)
    if array.ndim != 2 or array.shape[1] != 126:
        raise ValueError(f"unexpected shape for {name}: {array.shape}")
    if array.dtype != np.float32:
        raise ValueError(f"unexpected dtype for {name}: {array.dtype}")
    return array


def hand_presence(array: np.ndarray) -> np.ndarray:
    blocks = array.reshape(array.shape[0], 2, 21, 3)
    return np.any(blocks != 0, axis=(2, 3))


def inspect_archive(archive_path: Path) -> dict:
    class_stats = defaultdict(
        lambda: {
            "files": 0,
            "frames": 0,
            "frame_min": None,
            "frame_max": None,
            "one_hand_frame_fraction": [],
            "both_hand_frame_fraction": [],
            "zero_hand_frame_fraction": [],
        }
    )
    shapes = Counter()
    signers = Counter()
    frame_lengths = []
    finite_files = 0
    with ZipFile(archive_path) as archive:
        for name, class_name, signer, _ in iter_landmark_files(archive):
            array = read_array(archive, name)
            presence = hand_presence(array)
            stats = class_stats[class_name]
            stats["files"] += 1
            stats["frames"] += int(array.shape[0])
            stats["frame_min"] = array.shape[0] if stats["frame_min"] is None else min(stats["frame_min"], array.shape[0])
            stats["frame_max"] = array.shape[0] if stats["frame_max"] is None else max(stats["frame_max"], array.shape[0])
            stats["one_hand_frame_fraction"].append(float(np.mean(presence.sum(axis=1) == 1)))
            stats["both_hand_frame_fraction"].append(float(np.mean(presence.all(axis=1))))
            stats["zero_hand_frame_fraction"].append(float(np.mean(~presence.any(axis=1))))
            shapes[str(array.shape)] += 1
            signers[signer] += 1
            frame_lengths.append(array.shape[0])
            finite_files += int(np.isfinite(array).all())

    classes = {}
    for class_name, stats in sorted(class_stats.items()):
        classes[class_name] = {
            "files": stats["files"],
            "frames": stats["frames"],
            "frame_min": stats["frame_min"],
            "frame_max": stats["frame_max"],
            "one_hand_frame_fraction": round(float(np.mean(stats["one_hand_frame_fraction"])), 6),
            "both_hand_frame_fraction": round(float(np.mean(stats["both_hand_frame_fraction"])), 6),
            "zero_hand_frame_fraction": round(float(np.mean(stats["zero_hand_frame_fraction"])), 6),
        }
    return {
        "archive": str(archive_path),
        "root": ROOT,
        "files": sum(item["files"] for item in classes.values()),
        "classes": len(classes),
        "signers": dict(sorted(signers.items())),
        "shapes": dict(sorted(shapes.items())),
        "dtype": "float32",
        "all_files_finite": finite_files == sum(item["files"] for item in classes.values()),
        "frame_min": min(frame_lengths),
        "frame_max": max(frame_lengths),
        "frame_mean": round(float(np.mean(frame_lengths)), 4),
        "class_stats": classes,
    }


def prepare_subset(archive_path: Path, output_path: Path, selected_classes: list[str]) -> dict:
    selected = set(selected_classes)
    sequences = []
    labels = []
    signers = []
    sources = []
    with ZipFile(archive_path) as archive:
        available = {class_name for _, class_name, _, _ in iter_landmark_files(archive)}
        missing = sorted(selected - available)
        if missing:
            raise ValueError("classes not found: " + ", ".join(missing))
        for name, class_name, signer, _ in iter_landmark_files(archive):
            if class_name not in selected:
                continue
            sequences.append(read_array(archive, name))
            labels.append(class_name)
            signers.append(signer)
            sources.append(name)

    if not sequences:
        raise ValueError("no files selected")
    label_names = sorted(set(labels))
    label_ids = np.asarray([label_names.index(label) for label in labels], dtype=np.int64)
    offsets = np.zeros(len(sequences) + 1, dtype=np.int64)
    offsets[1:] = np.cumsum([sequence.shape[0] for sequence in sequences])
    features = np.concatenate(sequences, axis=0).astype(np.float32, copy=False)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        output_path,
        features=features,
        offsets=offsets,
        label_ids=label_ids,
        label_names=np.asarray(label_names),
        signers=np.asarray(signers),
        source_files=np.asarray(sources),
        schema_version=np.asarray("lifbras-eqt-uece-hand-v1"),
    )
    return {
        "output": str(output_path),
        "classes": label_names,
        "samples": len(sequences),
        "frames": int(features.shape[0]),
        "feature_shape": [126],
        "preserved_source_splits": False,
        "transforms": ["archive selection", "concatenate variable-length sequences with offsets"],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-zip", type=Path, default=DEFAULT_ZIP)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--inspect", action="store_true")
    mode.add_argument("--prepare", action="store_true")
    parser.add_argument("--class", dest="classes", action="append", default=[])
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.dataset_zip.is_file():
        raise SystemExit(f"dataset archive not found: {args.dataset_zip}")
    result = inspect_archive(args.dataset_zip) if args.inspect else prepare_subset(args.dataset_zip, args.output, args.classes)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
