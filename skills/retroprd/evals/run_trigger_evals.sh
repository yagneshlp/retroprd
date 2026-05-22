#!/usr/bin/env bash
# Trigger eval runner for the retroprd skill.
#
# Reads eval_queries.json, runs each query N times via `claude -p`, and checks
# whether the retroprd Skill was invoked. Outputs a JSON array with per-query
# trigger rates and a pass/fail summary.
#
# Usage:
#   bash run_trigger_evals.sh [queries_file] [runs_per_query] [threshold]
#
# Arguments:
#   queries_file    Path to eval_queries.json (default: ./eval_queries.json)
#   runs_per_query  Number of runs per query (default: 3)
#   threshold       Trigger-rate threshold for pass/fail (default: 0.5)
#
# Requirements:
#   - claude CLI in PATH (claude --version to verify)
#   - jq in PATH
#   - The retroprd skill installed where the claude CLI can find it

set -euo pipefail

QUERIES_FILE="${1:-$(dirname "$0")/eval_queries.json}"
RUNS="${2:-3}"
THRESHOLD="${3:-0.5}"
SKILL_NAME="retroprd"

if ! command -v claude &>/dev/null; then
  echo "ERROR: claude CLI not found in PATH. Install it with: npm install -g @anthropic-ai/claude-code" >&2
  exit 1
fi

if ! command -v jq &>/dev/null; then
  echo "ERROR: jq not found in PATH." >&2
  exit 1
fi

if [[ ! -f "$QUERIES_FILE" ]]; then
  echo "ERROR: Queries file not found: $QUERIES_FILE" >&2
  exit 1
fi

# Returns 0 if the retroprd skill was invoked in a claude -p run, 1 otherwise.
check_triggered() {
  local query="$1"
  claude -p "$query" --output-format json 2>/dev/null \
    | jq -e --arg skill "$SKILL_NAME" \
      '[.. | objects | select(.type == "tool_use" and .name == "Skill") | .input.skill] | any(. == $skill)' \
      >/dev/null 2>&1
}

count=$(jq 'length' "$QUERIES_FILE")
results=()

echo "Running trigger evals: $count queries × $RUNS runs = $((count * RUNS)) total invocations" >&2
echo "Skill: $SKILL_NAME  |  Pass threshold: $THRESHOLD" >&2
echo "" >&2

for i in $(seq 0 $((count - 1))); do
  query=$(jq -r ".[$i].query" "$QUERIES_FILE")
  should_trigger=$(jq -r ".[$i].should_trigger" "$QUERIES_FILE")
  triggers=0

  echo "Query $((i + 1))/$count (should_trigger=$should_trigger): ${query:0:80}..." >&2

  for run in $(seq 1 "$RUNS"); do
    echo "  Run $run/$RUNS..." >&2
    if check_triggered "$query"; then
      triggers=$((triggers + 1))
    fi
  done

  trigger_rate=$(echo "scale=4; $triggers / $RUNS" | bc)

  # Determine pass/fail
  if [[ "$should_trigger" == "true" ]]; then
    passed=$(echo "$trigger_rate >= $THRESHOLD" | bc -l)
  else
    passed=$(echo "$trigger_rate < $THRESHOLD" | bc -l)
  fi

  result=$(jq -n \
    --arg query "$query" \
    --argjson should_trigger "$should_trigger" \
    --argjson triggers "$triggers" \
    --argjson runs "$RUNS" \
    --argjson trigger_rate "$trigger_rate" \
    --argjson passed "$passed" \
    '{
      query: $query,
      should_trigger: $should_trigger,
      triggers: $triggers,
      runs: $runs,
      trigger_rate: $trigger_rate,
      passed: ($passed == 1)
    }')
  results+=("$result")

  status=$([[ "$passed" == "1" ]] && echo "PASS" || echo "FAIL")
  echo "  → triggers=$triggers/$RUNS rate=$trigger_rate [$status]" >&2
done

# Assemble output JSON
printf '%s\n' "${results[@]}" | jq -s '
  . as $all |
  {
    results: $all,
    summary: {
      total: ($all | length),
      passed: ($all | map(select(.passed)) | length),
      failed: ($all | map(select(.passed | not)) | length),
      pass_rate: (($all | map(select(.passed)) | length) / ($all | length)),
      should_trigger_pass_rate: (
        ($all | map(select(.should_trigger == true and .passed == true)) | length) /
        [($all | map(select(.should_trigger == true)) | length), 1] | max
      ),
      should_not_trigger_pass_rate: (
        ($all | map(select(.should_trigger == false and .passed == true)) | length) /
        [($all | map(select(.should_trigger == false)) | length), 1] | max
      )
    }
  }
'
