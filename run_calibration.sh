#!/usr/bin/env bash
# Usage: ./run_calibration.sh [--input PATH] [--model MODEL] [--dry-run] [omnicalib run options]
# Example: ./run_calibration.sh --device cpu --output /path/to/new_output
# Reuse selection: ./run_calibration.sh --model ds-none --reuse-datawash outputs/oak4p_135309
set -euo pipefail

PROJECT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

# Prefer the project Conda environment without requiring shell activation.
if [[ -n "${OMNICALIB_PYTHON:-}" ]]; then
    PYTHON_BIN="$OMNICALIB_PYTHON"
elif [[ -x "$HOME/miniforge3/envs/omnicalib-open/bin/python" ]]; then
    PYTHON_BIN="$HOME/miniforge3/envs/omnicalib-open/bin/python"
elif [[ "${CONDA_DEFAULT_ENV:-}" == "omnicalib-open" ]] && command -v python >/dev/null 2>&1; then
    PYTHON_BIN="$(command -v python)"
else
    echo 'Cannot find the omnicalib-open Python environment. Activate it or set OMNICALIB_PYTHON.' >&2
    exit 1
fi

MODEL=eucm-none
INPUT_PATH=/home/yuewang/Datasets/OAK4pNew/Layout_0909/20260909_rig01_cam_static_01_135309_ba7290
DRY_RUN=false
EXTRA_ARGS=()
while (($#)); do
    case "$1" in
        --input)
            [[ $# -ge 2 && -n "$2" ]] || { echo '--input requires a path' >&2; exit 2; }
            INPUT_PATH="$2"
            shift 2
            ;;
        --input=*) INPUT_PATH="${1#*=}"; shift ;;
        --dry-run) DRY_RUN=true; shift ;;
        --model=*) MODEL="${1#*=}"; shift ;;
        --model)
            [[ $# -ge 2 ]] || { echo '--model requires a value' >&2; exit 2; }
            MODEL="$2"
            shift 2
            ;;
        *) EXTRA_ARGS+=("$1"); shift ;;
    esac
done
case "$MODEL" in
    eucm-none) RIG_FILE="$PROJECT_DIR/configs/rig_oak4p_euroc_eucm.yaml" ;;
    ds-none) RIG_FILE="$PROJECT_DIR/configs/rig_oak4p_euroc_ds.yaml" ;;
    omni-radtan) RIG_FILE="$PROJECT_DIR/configs/rig_oak4p_euroc_omni_radtan.yaml" ;;
    *) echo "Unsupported --model: $MODEL (use eucm-none, ds-none or omni-radtan)" >&2; exit 2 ;;
esac

[[ -n "$INPUT_PATH" ]] || { echo '--input requires a path' >&2; exit 2; }
SEQUENCE_NAME="$(basename -- "${INPUT_PATH%/}")"
if [[ "$SEQUENCE_NAME" == mav0 ]]; then
    SEQUENCE_NAME="$(basename -- "$(dirname -- "${INPUT_PATH%/}")")"
fi
SEQUENCE_NAME="${SEQUENCE_NAME%.bag}"
OUTPUT_PATH="$PROJECT_DIR/outputs/${SEQUENCE_NAME}_${MODEL}"

export PYTHONPATH="$PROJECT_DIR/src${PYTHONPATH:+:$PYTHONPATH}"

# Later command-line options override these defaults. Existing results are
# protected by omnicalib; pass --overwrite explicitly if regeneration is wanted.
COMMAND=("$PYTHON_BIN" -m omnicalib_open.cli run \
    --input "$INPUT_PATH" \
    --rig "$RIG_FILE" \
    --datawash "$PROJECT_DIR/configs/datawash.yaml" \
    --target "$PROJECT_DIR/configs/target_aprilgrid_6x6.yaml" \
    --detector NN-Detector \
    --device gpu \
    --kalibr-image hkustswarm/co-calib:v1.0 \
    --output "$OUTPUT_PATH" \
    "${EXTRA_ARGS[@]}")

if "$DRY_RUN"; then
    printf '%q ' "${COMMAND[@]}"
    printf '\n'
    exit 0
fi
exec "${COMMAND[@]}"
