#!/bin/bash
# Cron Job Logging Wrapper
# Usage: cron-wrapper.sh <job-name> <command...>
# Logs stdout+stderr to ~/holy-chip/logs/<job-name>-YYYY-MM-DD.log
# Also appends to ~/holy-chip/logs/cron-history.log (one-liner per run)

JOB_NAME="$1"
shift

LOG_DIR="$HOME/holy-chip/logs"
DATE=$(date +"%Y-%m-%d")
TIMESTAMP=$(date +"%Y-%m-%d %H:%M:%S")
LOG_FILE="$LOG_DIR/${JOB_NAME}-${DATE}.log"
HISTORY_FILE="$LOG_DIR/cron-history.log"

mkdir -p "$LOG_DIR"

echo "===== RUN START: $TIMESTAMP =====" >> "$LOG_FILE"
echo "Command: $@" >> "$LOG_FILE"
echo "" >> "$LOG_FILE"

# Run the command, capture output and exit code
START_SEC=$(date +%s)
"$@" >> "$LOG_FILE" 2>&1
EXIT_CODE=$?
END_SEC=$(date +%s)
DURATION=$((END_SEC - START_SEC))

echo "" >> "$LOG_FILE"
echo "===== RUN END: $(date +"%Y-%m-%d %H:%M:%S") | exit=$EXIT_CODE | ${DURATION}s =====" >> "$LOG_FILE"
echo "" >> "$LOG_FILE"

# One-liner history
if [ $EXIT_CODE -eq 0 ]; then
    STATUS="OK"
else
    STATUS="FAIL(exit=$EXIT_CODE)"
fi
echo "$TIMESTAMP | $JOB_NAME | $STATUS | ${DURATION}s" >> "$HISTORY_FILE"

# Output to stdout too (so Hermes cron still captures it for delivery)
cat "$LOG_FILE" | tail -50

exit $EXIT_CODE
