#!/usr/bin/env bash
# 创建一份可审阅、可重建的 Seed-TTS-Eval 补丁工作副本；不会下载模型或运行评分。
set -Eeuo pipefail

script_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
source_root=${SEED_TTS_EVAL_SOURCE_ROOT:-}
work_root=${SEED_TTS_EVAL_ROOT:-}
patch_file="$script_dir/patches/0001-seed-tts-local-offline.patch"

[[ -n "$source_root" ]] || { echo "必须设置 SEED_TTS_EVAL_SOURCE_ROOT（干净的官方 Seed-TTS-Eval Git 仓库）。" >&2; exit 2; }
[[ -n "$work_root" ]] || { echo "必须设置 SEED_TTS_EVAL_ROOT（新的补丁工作副本目录）。" >&2; exit 2; }
[[ -f "$patch_file" ]] || { echo "补丁文件不存在：$patch_file" >&2; exit 2; }

source_root=$(cd "$source_root" && pwd)
work_root=$(python3 -c 'import os, sys; print(os.path.abspath(sys.argv[1]))' "$work_root")
git -C "$source_root" rev-parse --is-inside-work-tree >/dev/null
if [[ -e "$work_root" ]]; then
  echo "目标工作副本已存在，为避免覆盖而停止：$work_root" >&2
  exit 2
fi

revision=$(git -C "$source_root" rev-parse HEAD)
git -C "$source_root" worktree add --detach "$work_root" "$revision"
if ! git -C "$work_root" apply --check "$patch_file"; then
  git -C "$source_root" worktree remove --force "$work_root"
  echo "补丁无法应用到当前官方提交；请先审阅差异，不要手工混入未记录改动。" >&2
  exit 2
fi
git -C "$work_root" apply "$patch_file"
patch_hash=$(sha256sum "$patch_file" | awk '{print $1}')
python3 - "$work_root/freeze-patch.json" "$revision" "$patch_hash" <<'PY'
import json
import sys
from datetime import datetime, timezone

path, revision, patch_sha256 = sys.argv[1:]
with open(path, "w", encoding="utf-8") as handle:
    json.dump(
        {
            "official_revision": revision,
            "patch_file": "0001-seed-tts-local-offline.patch",
            "patch_sha256": patch_sha256,
            "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        },
        handle,
        ensure_ascii=False,
        indent=2,
    )
    handle.write("\n")
PY
git -C "$work_root" diff --check
git -C "$work_root" diff --stat
echo "已创建并冻结补丁工作副本：$work_root"
