#!/bin/bash
# Pi 5 Edge Benchmark — Frontend + Backend
# Measures real performance metrics for Raspberry Pi 5 (8GB) deployment
# Usage: pnpm benchmark

set -e

# Colors
G='\033[0;32m'  Y='\033[1;33m'  R='\033[0;31m'
B='\033[0;34m'  C='\033[0;36m'  D='\033[0;90m'  NC='\033[0m'

hr() { echo -e "${B}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"; }

# Linear score: maps a value from [0, worst] → [100, 0], clamped
# Usage: linear_score <value> <ideal> <worst>
linear_score() {
  local val=$1 ideal=$2 worst=$3
  if [ "$val" -le "$ideal" ]; then echo 100; return; fi
  if [ "$val" -ge "$worst" ]; then echo 0; return; fi
  echo $(( 100 - (val - ideal) * 100 / (worst - ideal) ))
}

# Color for a score
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

# ═══════════════════════════════════════════════════════
hr
echo -e "${B}   🔬 Pi 5 Edge Benchmark${NC}"
hr
echo ""

# ═══════════════════════════════════════════════════════
# 1. FRONTEND BUILD
# ═══════════════════════════════════════════════════════
echo -e "${Y}Building production bundle...${NC}"
pnpm build > /dev/null 2>&1

echo -e "${B}▸ Frontend${NC}"

# JS Bundle (gzipped) — weight 5 (most impactful)
JS_GZIP=$(find .svelte-kit/output/client -name "*.js" -print0 2>/dev/null | xargs -0 cat 2>/dev/null | gzip -c | wc -c | tr -d ' ')
JS_KB=$((JS_GZIP / 1024))
JS_SCORE=$(linear_score "$JS_KB" 50 500)
JS_C=$(score_color "$JS_SCORE")
add_metric "$JS_SCORE" 5
echo -e "  ⚡ JS Bundle:       ${JS_KB}KB ${C}(gzip)${NC}       ${JS_C}${JS_SCORE}/100${NC}"

# CSS (gzipped) — weight 2
CSS_GZIP=$(find .svelte-kit/output/client -name "*.css" -print0 2>/dev/null | xargs -0 cat 2>/dev/null | gzip -c | wc -c | tr -d ' ')
CSS_KB=$((CSS_GZIP / 1024))
CSS_SCORE=$(linear_score "$CSS_KB" 5 200)
CSS_C=$(score_color "$CSS_SCORE")
add_metric "$CSS_SCORE" 2
echo -e "  🎨 CSS:             ${CSS_KB}KB ${C}(gzip)${NC}       ${CSS_C}${CSS_SCORE}/100${NC}"

# Static Assets — weight 2
ASSET_BYTES=$(find .svelte-kit/output/client -type f \
  -not -name "*.js" -not -name "*.css" -not -name "*.html" -not -name "*.json" \
  -print0 2>/dev/null | xargs -0 cat 2>/dev/null | wc -c | tr -d ' ')
ASSET_KB=$((ASSET_BYTES / 1024))
ASSET_SCORE=$(linear_score "$ASSET_KB" 500 10000)
ASSET_C=$(score_color "$ASSET_SCORE")
add_metric "$ASSET_SCORE" 2
echo -e "  🖼️  Assets:          ${ASSET_KB}KB ${C}(raw)${NC}        ${ASSET_C}${ASSET_SCORE}/100${NC}"

# SSR Pages (count route dirs as proxy for SSR complexity) — weight 1
ROUTE_COUNT=$(find src/routes -name "+page.svelte" 2>/dev/null | wc -l | tr -d ' ')
ROUTE_SCORE=$(linear_score "$ROUTE_COUNT" 5 50)
ROUTE_C=$(score_color "$ROUTE_SCORE")
add_metric "$ROUTE_SCORE" 1
echo -e "  📄 SSR Routes:      ${ROUTE_COUNT} pages              ${ROUTE_C}${ROUTE_SCORE}/100${NC}"

# ═══════════════════════════════════════════════════════
# 2. BACKEND
# ═══════════════════════════════════════════════════════
echo ""
echo -e "${B}▸ Backend${NC}"

if [ -d "backend" ]; then
  # Python source code — weight 1
  PY_BYTES=$(find backend -type f -name "*.py" -not -path "*/.venv/*" -not -path "*/__pycache__/*" \
    -print0 2>/dev/null | xargs -0 cat 2>/dev/null | wc -c | tr -d ' ')
  PY_KB=$((PY_BYTES / 1024))
  PY_SCORE=$(linear_score "$PY_KB" 10 200)
  PY_C=$(score_color "$PY_SCORE")
  add_metric "$PY_SCORE" 1
  echo -e "  🐍 Python Code:     ${PY_KB}KB                  ${PY_C}${PY_SCORE}/100${NC}"

  # Pip dependencies — weight 2
  if [ -f "backend/requirements.txt" ]; then
    PIP_COUNT=$(grep -cve '^\s*$' backend/requirements.txt 2>/dev/null || echo 0)
  else
    PIP_COUNT=0
  fi
  PIP_SCORE=$(linear_score "$PIP_COUNT" 3 30)
  PIP_C=$(score_color "$PIP_SCORE")
  add_metric "$PIP_SCORE" 2
  echo -e "  📦 Pip Packages:    ${PIP_COUNT} pkgs               ${PIP_C}${PIP_SCORE}/100${NC}"

  # Venv disk footprint — weight 1
  if [ -d "backend/.venv" ]; then
    VENV_MB=$(du -sm backend/.venv 2>/dev/null | cut -f1)
  else
    VENV_MB=0
  fi
  VENV_SCORE=$(linear_score "$VENV_MB" 30 500)
  VENV_C=$(score_color "$VENV_SCORE")
  add_metric "$VENV_SCORE" 1
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

# ═══════════════════════════════════════════════════════
# 3. RUNTIME MEASUREMENTS (if backend is running)
# ═══════════════════════════════════════════════════════
echo ""
echo -e "${B}▸ Runtime${NC}"

BACKEND_RUNNING=false
if curl -sf http://127.0.0.1:8000/api/auth/setup-status > /dev/null 2>&1; then
  BACKEND_RUNNING=true
fi

if [ "$BACKEND_RUNNING" = true ]; then
  # API latency — average of 3 calls, weight 4 (critical metric)
  API_TOTAL_MS=0
  API_CALLS=3
  for i in $(seq 1 $API_CALLS); do
    # time_total in seconds, convert to ms
    T=$(curl -sf -o /dev/null -w "%{time_total}" http://127.0.0.1:8000/api/auth/setup-status)
    MS=$(echo "$T * 1000" | bc | cut -d'.' -f1)
    API_TOTAL_MS=$((API_TOTAL_MS + MS))
  done
  API_AVG_MS=$((API_TOTAL_MS / API_CALLS))
  API_SCORE=$(linear_score "$API_AVG_MS" 5 200)
  API_C=$(score_color "$API_SCORE")
  add_metric "$API_SCORE" 4
  echo -e "  🌐 API Latency:     ${API_AVG_MS}ms ${C}(avg ×${API_CALLS})${NC}     ${API_C}${API_SCORE}/100${NC}"

  # Backend memory (RSS) — weight 3
  # Find the uvicorn worker process
  UVICORN_PID=$(pgrep -f "uvicorn main:app" | head -1 2>/dev/null || true)
  if [ -n "$UVICORN_PID" ]; then
    RSS_KB=$(ps -o rss= -p "$UVICORN_PID" 2>/dev/null | tr -d ' ')
    RSS_MB=$((RSS_KB / 1024))
    MEM_SCORE=$(linear_score "$RSS_MB" 30 512)
    MEM_C=$(score_color "$MEM_SCORE")
    add_metric "$MEM_SCORE" 3
    echo -e "  🧠 Backend RAM:     ${RSS_MB}MB ${C}(RSS)${NC}        ${MEM_C}${MEM_SCORE}/100${NC}"
  else
    echo -e "  ${D}🧠 Backend RAM:     (uvicorn PID not found)${NC}"
  fi
else
  echo -e "  ${D}Backend not running — skipping runtime metrics.${NC}"
  echo -e "  ${D}Start with: cd backend && uvicorn main:app --reload${NC}"
fi

# ═══════════════════════════════════════════════════════
# 4. PI 5 LOAD TIME ESTIMATE
# ═══════════════════════════════════════════════════════
JS_RAW=$(find .svelte-kit/output/client -name "*.js" -print0 2>/dev/null | xargs -0 cat 2>/dev/null | wc -c | tr -d ' ')
JS_RAW_KB=$((JS_RAW / 1024))
TOTAL_TRANSFER_KB=$((JS_KB + CSS_KB + ASSET_KB))

TIME_DISK=$((TOTAL_TRANSFER_KB * 1000 / 80000))    # 80MB/s UHS-I SD
TIME_NET=$((TOTAL_TRANSFER_KB * 1000 / 100000))     # 100MB/s GbE LAN
TIME_PARSE=$((JS_RAW_KB * 1000 / 5000))              # ~5MB/s Cortex-A76 parse

# Add API latency if measured
if [ "$BACKEND_RUNNING" = true ]; then
  TIME_API=$API_AVG_MS
else
  TIME_API=0
fi
TOTAL_TIME=$((TIME_DISK + TIME_NET + TIME_PARSE + TIME_API))

echo ""
hr
echo -e "${B}   ⏱️  Pi 5 Estimated Cold Start${NC}"
hr
if [ "$TOTAL_TIME" -lt 100 ]; then TC=$G; TV="⚡ Instant"
elif [ "$TOTAL_TIME" -lt 300 ]; then TC=$G; TV="🚀 Very Fast"
elif [ "$TOTAL_TIME" -lt 1000 ]; then TC=$Y; TV="⚠️  Noticeable"
else TC=$R; TV="❌ Slow"
fi
echo -e "   ${TC}~${TOTAL_TIME}ms (${TV})${NC}"
echo -e "     Disk ${TIME_DISK}ms · Network ${TIME_NET}ms · Parse ${TIME_PARSE}ms · API ${TIME_API}ms"

# ═══════════════════════════════════════════════════════
# FINAL WEIGHTED SCORE
# ═══════════════════════════════════════════════════════
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
