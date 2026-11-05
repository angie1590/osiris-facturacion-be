#!/usr/bin/env bash
set -euo pipefail

wheel_path="lib/fe_ec-0.1.0-py3-none-any-3.whl"
wheel_url="${FE_EC_WHEEL_URL:?Set FE_EC_WHEEL_URL to the private wheel URL}"
expected_sha256="${FE_EC_WHEEL_SHA256:?Set FE_EC_WHEEL_SHA256 for the pinned wheel}"
temporary_file="$(mktemp)"
trap 'rm -f "$temporary_file"' EXIT

curl_args=(--fail --location --silent --show-error --retry 3)
if [[ -n "${FE_EC_WHEEL_TOKEN:-}" ]]; then
  curl_args+=(--header "Authorization: Bearer ${FE_EC_WHEEL_TOKEN}")
fi

curl "${curl_args[@]}" "$wheel_url" --output "$temporary_file"
printf '%s  %s\n' "$expected_sha256" "$temporary_file" | shasum -a 256 --check --status
mkdir -p "$(dirname "$wheel_path")"
mv "$temporary_file" "$wheel_path"
trap - EXIT
printf 'Verified private wheel: %s\n' "$wheel_path"