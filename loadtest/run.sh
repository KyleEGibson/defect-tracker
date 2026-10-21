#!/usr/bin/env bash
# Run the JMeter plan in a container on the compose network, against the web
# container (nginx -> API -> PostgreSQL), then enforce thresholds.
#   docker compose up -d --build --wait && ./loadtest/run.sh [users] [loops]
set -euo pipefail
cd "$(dirname "$0")/.."
USERS=${1:-20}
LOOPS=${2:-25}
NETWORK=$(docker network ls --filter name=defect-tracker_default --format '{{.Name}}' | head -1)
rm -rf loadtest/results && mkdir -p loadtest/results
docker run --rm --network "$NETWORK" -v "$PWD/loadtest:/plan" justb4/jmeter:5.5 \
  -n -t /plan/tracker.jmx -Jhost=web -Jport=80 -Jusers="$USERS" -Jloops="$LOOPS" \
  -Jjmeter.save.saveservice.output_format=csv \
  -l /plan/results/results.jtl -e -o /plan/results/report
python3 loadtest/check_results.py loadtest/results/results.jtl
