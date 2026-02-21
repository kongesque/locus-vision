#!/bin/bash
# LocusVision Edge Benchmark — Frontend + Backend + AI Inference
# Measures real performance metrics for Raspberry Pi 5 (8GB) deployment
# Usage: pnpm benchmark

set -euo pipefail

# Colors
G='\033[0;32m'  Y='\033[1;33m'  R='\033[0;31m'
B='\033[0;34m'  C='\033[0;36m'  D='\033[0;90m'  NC='\033[0m'
BOLD='\033[1m'

hr() { echo -e "${B}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"; }

# Linear score: maps a value from [ideal, worst] → [100, 0], clamped
linear_score() {
  local val=$1 ideal=$2 worst=$3
  if [ "$val" -le "$ideal" ]; then echo 100; return; fi
  if [ "$val" -ge "$worst" ]; then echo 0; return; fi
  echo $(( 100 - (val - ideal) * 100 / (worst - ideal) ))
}

# Inverse score: higher value = better (e.g., FPS)
inverse_score() {
  local val=$1 ideal=$2 worst=$3
  if [ "$val" -ge "$ideal" ]; then echo 100; return; fi
  if [ "$val" -le "$worst" ]; then echo 0; return; fi
  echo $(( (val - worst) * 100 / (ideal - worst) ))
}

score_color() {
  local s=$1
  if [ "$s" -ge 80 ]; then echo "$G"
  elif [ "$s" -ge 50 ]; then echo "$Y"
  else echo "$R"; fi
}

# Accumulator
WEIGHTED_TOTAL=0
WEIGHT_SUM=0

add_metric() {
  local score=$1 weight=$2
  WEIGHTED_TOTAL=$((WEIGHTED_TOTAL + score * weight))
  WEIGHT_SUM=$((WEIGHT_SUM + weight))
}

# ═══════════════════════════════════════════════════════════
hr
echo -e "${B}   🔬 LocusVision Edge Benchmark${NC}"
hr
echo ""

# ── System Info ─────────────────────────────────────────────
echo -e "${D}  Date:     $(date '+%Y-%m-%d %H:%M:%S')${NC}"
echo -e "${D}  Host:     $(hostname)${NC}"
echo -e "${D}  OS:       $(uname -s) $(uname -m)${NC}"
if [ -f /proc/cpuinfo ]; then
  CPU_MODEL=$(grep -m1 'model name' /proc/cpuinfo 2>/dev/null | cut -d: -f2 | xargs)
  echo -e "${D}  CPU:      ${CPU_MODEL:-Unknown}${NC}"
elif command -v sysctl &>/dev/null; then
  CPU_MODEL=$(sysctl -n machdep.cpu.brand_string 2>/dev/null || echo "Unknown")
  echo -e "${D}  CPU:      ${CPU_MODEL}${NC}"
fi
TOTAL_RAM_MB=$(( $(sysctl -n hw.memsize 2>/dev/null || echo 0) / 1024 / 1024 ))
if [ "$TOTAL_RAM_MB" -gt 0 ]; then
  echo -e "${D}  RAM:      ${TOTAL_RAM_MB}MB${NC}"
fi
echo ""

# ═══════════════════════════════════════════════════════════
# 1. FRONTEND BUILD
# ═══════════════════════════════════════════════════════════
echo -e "${Y}Building production bundle...${NC}"
pnpm build > /dev/null 2>&1

echo -e "${B}▸ Frontend${NC}"

# JS Bundle (gzipped) — weight 3
JS_GZIP=$(find .svelte-kit/output/client -name "*.js" -print0 2>/dev/null | xargs -0 cat 2>/dev/null | gzip -c | wc -c | tr -d ' ')
JS_KB=$((JS_GZIP / 1024))
JS_SCORE=$(linear_score "$JS_KB" 50 500)
JS_C=$(score_color "$JS_SCORE")
add_metric "$JS_SCORE" 3
echo -e "  ⚡ JS Bundle:       ${JS_KB}KB ${C}(gzip)${NC}       ${JS_C}${JS_SCORE}/100${NC}"

# CSS (gzipped) — weight 1
CSS_GZIP=$(find .svelte-kit/output/client -name "*.css" -print0 2>/dev/null | xargs -0 cat 2>/dev/null | gzip -c | wc -c | tr -d ' ')
CSS_KB=$((CSS_GZIP / 1024))
CSS_SCORE=$(linear_score "$CSS_KB" 10 200)
CSS_C=$(score_color "$CSS_SCORE")
add_metric "$CSS_SCORE" 1
echo -e "  🎨 CSS:             ${CSS_KB}KB ${C}(gzip)${NC}       ${CSS_C}${CSS_SCORE}/100${NC}"

# Static Assets — weight 1
ASSET_BYTES=$(find .svelte-kit/output/client -type f \
  -not -name "*.js" -not -name "*.css" -not -name "*.html" -not -name "*.json" \
  -print0 2>/dev/null | xargs -0 cat 2>/dev/null | wc -c | tr -d ' ')
ASSET_KB=$((ASSET_BYTES / 1024))
ASSET_SCORE=$(linear_score "$ASSET_KB" 500 10000)
ASSET_C=$(score_color "$ASSET_SCORE")
add_metric "$ASSET_SCORE" 1
echo -e "  🖼️  Assets:          ${ASSET_KB}KB ${C}(raw)${NC}        ${ASSET_C}${ASSET_SCORE}/100${NC}"

# ═══════════════════════════════════════════════════════════
# 2. BACKEND
# ═══════════════════════════════════════════════════════════
echo ""
echo -e "${B}▸ Backend${NC}"

if [ -d "backend" ]; then
  # Pip dependencies — weight 1
  if [ -f "backend/requirements.txt" ]; then
    PIP_COUNT=$(grep -cve '^\s*$' backend/requirements.txt 2>/dev/null || echo 0)
  else
    PIP_COUNT=0
  fi
  PIP_SCORE=$(linear_score "$PIP_COUNT" 8 40)
  PIP_C=$(score_color "$PIP_SCORE")
  add_metric "$PIP_SCORE" 1
  echo -e "  📦 Pip Packages:    ${PIP_COUNT} pkgs               ${PIP_C}${PIP_SCORE}/100${NC}"

  # Venv disk footprint — weight 2
  if [ -d "backend/.venv" ]; then
    VENV_MB=$(du -sm backend/.venv 2>/dev/null | cut -f1)
  else
    VENV_MB=0
  fi
  VENV_SCORE=$(linear_score "$VENV_MB" 50 500)
  VENV_C=$(score_color "$VENV_SCORE")
  add_metric "$VENV_SCORE" 2
  echo -e "  🗂️  Venv Footprint:  ${VENV_MB}MB                  ${VENV_C}${VENV_SCORE}/100${NC}"

  # DB size — weight 1
  DB_FILE="backend/data/locusvision.db"
  if [ -f "$DB_FILE" ]; then
    DB_KB=$(( $(wc -c < "$DB_FILE" | tr -d ' ') / 1024 ))
  else
    DB_KB=0
  fi
  DB_SCORE=$(linear_score "$DB_KB" 100 102400)
  DB_C=$(score_color "$DB_SCORE")
  add_metric "$DB_SCORE" 1
  echo -e "  💾 Database:        ${DB_KB}KB ${C}(SQLite)${NC}     ${DB_C}${DB_SCORE}/100${NC}"
else
  echo -e "  ${D}No backend directory found${NC}"
fi

# ═══════════════════════════════════════════════════════════
# 3. AI / INFERENCE PERFORMANCE (the critical section)
# ═══════════════════════════════════════════════════════════
echo ""
echo -e "${B}▸ AI Inference${NC}"

PYTHON_BIN=""
if [ -f "backend/.venv/bin/python" ]; then
  PYTHON_BIN="backend/.venv/bin/python"
elif command -v python3 &>/dev/null; then
  PYTHON_BIN="python3"
fi

INFER_OK="False"
if [ -n "$PYTHON_BIN" ] && [ -f "scripts/bench_inference.py" ]; then
  echo -e "  ${D}Running inference benchmark (100 frames)...${NC}"
  INFER_JSON=$($PYTHON_BIN scripts/bench_inference.py --frames 100 --warmup 10 2>/dev/null || echo '{"success": false, "error": "script failed"}')

  INFER_OK=$(echo "$INFER_JSON" | python3 -c "import sys,json; print(json.load(sys.stdin).get('success', False))" 2>/dev/null || echo "False")

  if [ "$INFER_OK" = "True" ]; then
    # Helper to extract values from JSON
    jval() { echo "$INFER_JSON" | python3 -c "import sys,json; d=json.load(sys.stdin); print($1)" 2>/dev/null; }

    # Show hardware detection + projection warning
    IS_PROJECTED=$(jval "d.get('is_projected', False)")
    HW_NAME=$(jval "d.get('hardware', 'Unknown')")
    if [ "$IS_PROJECTED" = "True" ]; then
      echo -e "  ${Y}⚠ Running on ${HW_NAME} — values projected to Pi 5 (×12 latency)${NC}"
      LABEL="≈Pi5"
    else
      echo -e "  ${G}✓ Running on ${HW_NAME} — native measurements${NC}"
      LABEL=""
    fi
    echo ""

    # Model load time — weight 3
    LOAD_MS=$(jval "int(d['model_load_ms'])")
    LOAD_SCORE=$(linear_score "$LOAD_MS" 500 5000)
    LOAD_C=$(score_color "$LOAD_SCORE")
    add_metric "$LOAD_SCORE" 3
    if [ "$IS_PROJECTED" = "True" ]; then
      LOAD_MEASURED=$(jval "int(d['model_load_ms_measured'])")
      echo -e "  🧩 Model Load:      ${LOAD_MS}ms ${D}(measured: ${LOAD_MEASURED}ms)${NC}  ${LOAD_C}${LOAD_SCORE}/100${NC}"
    else
      echo -e "  🧩 Model Load:      ${LOAD_MS}ms                 ${LOAD_C}${LOAD_SCORE}/100${NC}"
    fi

    # Model size — informational
    MODEL_MB=$(jval "d.get('model_size_mb', '?')")
    echo -e "  📐 Model Size:      ${MODEL_MB}MB ${C}(ONNX)${NC}"

    # Detection FPS — weight 5
    DETECT_FPS=$(jval "int(d['detect']['fps'])")
    DETECT_P50=$(jval "d['detect']['p50_ms']")
    DETECT_P99=$(jval "d['detect']['p99_ms']")
    DETECT_SCORE=$(inverse_score "$DETECT_FPS" 30 3)
    DETECT_C=$(score_color "$DETECT_SCORE")
    add_metric "$DETECT_SCORE" 5
    if [ "$IS_PROJECTED" = "True" ]; then
      DETECT_FPS_M=$(jval "int(d['detect_measured']['fps'])")
      echo -e "  🎯 Detection:       ${LABEL} ${DETECT_FPS} FPS ${C}(P50: ${DETECT_P50}ms P99: ${DETECT_P99}ms)${NC} ${D}[dev: ${DETECT_FPS_M}]${NC}  ${DETECT_C}${DETECT_SCORE}/100${NC}"
    else
      echo -e "  🎯 Detection:       ${DETECT_FPS} FPS ${C}(P50: ${DETECT_P50}ms P99: ${DETECT_P99}ms)${NC}  ${DETECT_C}${DETECT_SCORE}/100${NC}"
    fi

    # Tracking FPS — weight 6
    TRACK_FPS=$(jval "int(d['track']['fps'])")
    TRACK_P50=$(jval "d['track']['p50_ms']")
    TRACK_P95=$(jval "d['track']['p95_ms']")
    TRACK_P99=$(jval "d['track']['p99_ms']")
    TRACK_SCORE=$(inverse_score "$TRACK_FPS" 25 2)
    TRACK_C=$(score_color "$TRACK_SCORE")
    add_metric "$TRACK_SCORE" 6
    if [ "$IS_PROJECTED" = "True" ]; then
      TRACK_FPS_M=$(jval "int(d['track_measured']['fps'])")
      echo -e "  🔍 Track+Detect:    ${LABEL} ${TRACK_FPS} FPS ${C}(P50: ${TRACK_P50}ms P95: ${TRACK_P95}ms)${NC} ${D}[dev: ${TRACK_FPS_M}]${NC}  ${TRACK_C}${TRACK_SCORE}/100${NC}"
    else
      echo -e "  🔍 Track+Detect:    ${TRACK_FPS} FPS ${C}(P50: ${TRACK_P50}ms P95: ${TRACK_P95}ms P99: ${TRACK_P99}ms)${NC}  ${TRACK_C}${TRACK_SCORE}/100${NC}"
    fi

    # Full pipeline FPS — weight 8 (most important)
    PIPELINE_ERR=$(jval "d.get('pipeline',{}).get('error','')")
    if [ -z "$PIPELINE_ERR" ]; then
      PIPE_FPS=$(jval "int(d['pipeline']['fps'])")
      PIPE_P50=$(jval "d['pipeline']['p50_ms']")
      PIPE_P95=$(jval "d['pipeline']['p95_ms']")
      PIPE_P99=$(jval "d['pipeline']['p99_ms']")
      PIPE_SCORE=$(inverse_score "$PIPE_FPS" 20 2)
      PIPE_C=$(score_color "$PIPE_SCORE")
      add_metric "$PIPE_SCORE" 8
      if [ "$IS_PROJECTED" = "True" ]; then
        PIPE_FPS_M=$(jval "int(d['pipeline_measured']['fps'])")
        echo -e "  🚀 Full Pipeline:   ${LABEL} ${PIPE_FPS} FPS ${C}(P50: ${PIPE_P50}ms P95: ${PIPE_P95}ms)${NC} ${D}[dev: ${PIPE_FPS_M}]${NC}  ${PIPE_C}${PIPE_SCORE}/100${NC}"
      else
        echo -e "  🚀 Full Pipeline:   ${PIPE_FPS} FPS ${C}(P50: ${PIPE_P50}ms P95: ${PIPE_P95}ms P99: ${PIPE_P99}ms)${NC}  ${PIPE_C}${PIPE_SCORE}/100${NC}"
      fi
    else
      echo -e "  ${D}🚀 Full Pipeline:   (error: ${PIPELINE_ERR})${NC}"
    fi

    # Peak memory — weight 4
    PEAK_RSS=$(jval "int(d['peak_rss_mb'])")
    MEM_SCORE=$(linear_score "$PEAK_RSS" 80 512)
    MEM_C=$(score_color "$MEM_SCORE")
    add_metric "$MEM_SCORE" 4
    if [ "$IS_PROJECTED" = "True" ]; then
      PEAK_RSS_M=$(jval "int(d['peak_rss_mb_measured'])")
      echo -e "  🧠 Peak Memory:     ${LABEL} ${PEAK_RSS}MB ${C}(RSS)${NC} ${D}[dev: ${PEAK_RSS_M}MB]${NC}  ${MEM_C}${MEM_SCORE}/100${NC}"
    else
      echo -e "  🧠 Peak Memory:     ${PEAK_RSS}MB ${C}(RSS)${NC}        ${MEM_C}${MEM_SCORE}/100${NC}"
    fi
  else
    INFER_ERR=$(echo "$INFER_JSON" | python3 -c "import sys,json; print(json.load(sys.stdin).get('error', 'unknown'))" 2>/dev/null || echo "unknown")
    echo -e "  ${R}Inference benchmark failed: ${INFER_ERR}${NC}"
  fi
else
  echo -e "  ${D}Skipped — Python venv or bench_inference.py not found.${NC}"
  echo -e "  ${D}Setup: cd backend && python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt${NC}"
fi

# ═══════════════════════════════════════════════════════════
# 4. RUNTIME SERVER CHECKS (if backend is running)
# ═══════════════════════════════════════════════════════════
echo ""
echo -e "${B}▸ Live Server${NC}"

BACKEND_RUNNING=false
if curl -sf http://127.0.0.1:8000/api/auth/setup-status > /dev/null 2>&1; then
  BACKEND_RUNNING=true
fi

if [ "$BACKEND_RUNNING" = true ]; then
  # API latency — average of 20 calls (skip first 3 warm-up), weight 3
  API_LATENCIES=()
  for i in $(seq 1 23); do
    T=$(curl -sf -o /dev/null -w "%{time_total}" http://127.0.0.1:8000/api/auth/setup-status)
    MS=$(echo "$T * 1000" | bc | cut -d'.' -f1)
    if [ "$i" -gt 3 ]; then
      API_LATENCIES+=("$MS")
    fi
  done

  # Sort and compute percentiles
  IFS=$'\n' SORTED=($(printf '%s\n' "${API_LATENCIES[@]}" | sort -n)); unset IFS
  API_COUNT=${#SORTED[@]}
  API_P50_IDX=$(( API_COUNT * 50 / 100 ))
  API_P95_IDX=$(( API_COUNT * 95 / 100 ))
  API_P50=${SORTED[$API_P50_IDX]}
  API_P95=${SORTED[$API_P95_IDX]}

  API_SUM=0
  for v in "${API_LATENCIES[@]}"; do API_SUM=$((API_SUM + v)); done
  API_AVG=$((API_SUM / API_COUNT))

  API_SCORE=$(linear_score "$API_P50" 15 300)
  API_C=$(score_color "$API_SCORE")
  add_metric "$API_SCORE" 3
  echo -e "  🌐 API Latency:     P50: ${API_P50}ms P95: ${API_P95}ms ${C}(avg: ${API_AVG}ms ×${API_COUNT})${NC}  ${API_C}${API_SCORE}/100${NC}"

  # Backend memory (RSS) — weight 3
  UVICORN_PID=$(pgrep -f "uvicorn main:app" | head -1 2>/dev/null || true)
  if [ -n "$UVICORN_PID" ]; then
    RSS_KB=$(ps -o rss= -p "$UVICORN_PID" 2>/dev/null | tr -d ' ')
    RSS_MB=$((RSS_KB / 1024))
    SERVER_MEM_SCORE=$(linear_score "$RSS_MB" 80 512)
    SERVER_MEM_C=$(score_color "$SERVER_MEM_SCORE")
    add_metric "$SERVER_MEM_SCORE" 3
    echo -e "  🧠 Server RAM:      ${RSS_MB}MB ${C}(RSS)${NC}        ${SERVER_MEM_C}${SERVER_MEM_SCORE}/100${NC}"
  else
    echo -e "  ${D}🧠 Server RAM:      (uvicorn PID not found)${NC}"
  fi
else
  echo -e "  ${D}Backend not running — skipping live server metrics.${NC}"
  echo -e "  ${D}Start with: cd backend && uvicorn main:app --reload${NC}"
fi

# ═══════════════════════════════════════════════════════════
# 5. PI 5 LOAD TIME ESTIMATE
# ═══════════════════════════════════════════════════════════
JS_RAW=$(find .svelte-kit/output/client -name "*.js" -print0 2>/dev/null | xargs -0 cat 2>/dev/null | wc -c | tr -d ' ')
JS_RAW_KB=$((JS_RAW / 1024))
TOTAL_TRANSFER_KB=$((JS_KB + CSS_KB + ASSET_KB))

# Pi 5 estimates: SD random-read ~5MB/s, LAN ~100MB/s, Cortex-A76 parse ~15MB/s
TIME_DISK=$((TOTAL_TRANSFER_KB * 1000 / 5000))      # 5MB/s random read on SD
TIME_NET=$((TOTAL_TRANSFER_KB * 1000 / 100000))      # 100MB/s GbE LAN
TIME_PARSE=$((JS_RAW_KB * 1000 / 15000))              # ~15MB/s V8 on Cortex-A76

# Add API + model load if measured
if [ "$BACKEND_RUNNING" = true ]; then
  TIME_API=$API_AVG
else
  TIME_API=0
fi
MODEL_LOAD_EST=0
if [ -n "$PYTHON_BIN" ] && [ "$INFER_OK" = "True" ] 2>/dev/null; then
  MODEL_LOAD_EST=${LOAD_MS:-0}
fi
TOTAL_TIME=$((TIME_DISK + TIME_NET + TIME_PARSE + TIME_API + MODEL_LOAD_EST))

echo ""
hr
echo -e "${B}   ⏱️  Pi 5 Estimated Cold Start${NC}"
hr
if [ "$TOTAL_TIME" -lt 500 ]; then TC=$G; TV="⚡ Fast"
elif [ "$TOTAL_TIME" -lt 2000 ]; then TC=$G; TV="🚀 Reasonable"
elif [ "$TOTAL_TIME" -lt 5000 ]; then TC=$Y; TV="⚠️  Noticeable"
else TC=$R; TV="❌ Slow"
fi
echo -e "   ${TC}~${TOTAL_TIME}ms (${TV})${NC}"
echo -e "     Disk ${TIME_DISK}ms · Net ${TIME_NET}ms · Parse ${TIME_PARSE}ms · API ${TIME_API}ms · Model ${MODEL_LOAD_EST}ms"

# ═══════════════════════════════════════════════════════════
# FINAL WEIGHTED SCORE
# ═══════════════════════════════════════════════════════════
if [ "$WEIGHT_SUM" -gt 0 ]; then
  FINAL=$((WEIGHTED_TOTAL / WEIGHT_SUM))
else
  FINAL=0
fi

echo ""
hr
if [ "$FINAL" -ge 90 ]; then   GRADE="A+"; FC=$G; V="🚀 Optimized for edge."
elif [ "$FINAL" -ge 80 ]; then GRADE="A";  FC=$G; V="✅ Excellent for Pi 5."
elif [ "$FINAL" -ge 70 ]; then GRADE="B";  FC=$G; V="👍 Solid performance."
elif [ "$FINAL" -ge 50 ]; then GRADE="C";  FC=$Y; V="⚠️  Could be lighter."
else                           GRADE="F";  FC=$R; V="❌ Too heavy for edge."
fi
echo -e "   ${FC}SCORE: ${FINAL}/100 (${GRADE})${NC} — ${WEIGHT_SUM} weight across metrics"
echo -e "   ${V}"
hr
