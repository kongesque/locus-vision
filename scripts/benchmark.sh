#!/bin/bash
# Pi 5 App Benchmark - Granular Analysis
# Usage: ./scripts/benchmark.sh

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}   🔬 Edge Device Analysis (Pi 5 Target)${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# Build first
echo -e "${YELLOW}Building production bundle...${NC}"
pnpm build > /dev/null 2>&1

echo -e "${BLUE}Analyzing metrics...${NC}"
echo ""

TOTAL_SCORE=0
METRICS_COUNT=4 # JS, CSS, Assets, Dependencies

# Helper function for Gzip size
get_gzip_size() {
  find .svelte-kit/output/client -name "$1" -print0 | xargs -0 cat | gzip -c | wc -c
}

# Helper function for Raw size
get_raw_size() {
  find .svelte-kit/output/client -name "$1" -print0 | xargs -0 cat | wc -c
}

# 1. JavaScript Bundle (Gzipped)
JS_RAW_BYTES=$(get_raw_size "*.js")
JS_GZIP_BYTES=$(get_gzip_size "*.js")
JS_GZIP_KB=$((JS_GZIP_BYTES / 1024))
JS_RAW_KB=$((JS_RAW_BYTES / 1024))

if [ "$JS_GZIP_KB" -lt 150 ]; then
  JS_SCORE=100
  JS_COLOR=$GREEN
elif [ "$JS_GZIP_KB" -lt 300 ]; then
  JS_SCORE=90
  JS_COLOR=$GREEN
elif [ "$JS_GZIP_KB" -lt 500 ]; then
  JS_SCORE=70
  JS_COLOR=$YELLOW
else
  JS_SCORE=40
  JS_COLOR=$RED
fi
TOTAL_SCORE=$((TOTAL_SCORE + JS_SCORE))
echo -e "⚡ JavaScript:       ${JS_GZIP_KB}KB ${CYAN}(gzipped)${NC} ${JS_COLOR}($JS_SCORE/100)${NC}"

# 2. CSS Bundle (Gzipped)
CSS_GZIP_BYTES=$(get_gzip_size "*.css")
CSS_GZIP_KB=$((CSS_GZIP_BYTES / 1024))

if [ "$CSS_GZIP_KB" -lt 50 ]; then
  CSS_SCORE=100
  CSS_COLOR=$GREEN
elif [ "$CSS_GZIP_KB" -lt 100 ]; then
  CSS_SCORE=85
  CSS_COLOR=$GREEN
elif [ "$CSS_GZIP_KB" -lt 200 ]; then
  CSS_SCORE=60
  CSS_COLOR=$YELLOW
else
  CSS_SCORE=30
  CSS_COLOR=$RED
fi
TOTAL_SCORE=$((TOTAL_SCORE + CSS_SCORE))
echo -e "🎨 CSS:              ${CSS_GZIP_KB}KB ${CYAN}(gzipped)${NC} ${CSS_COLOR}($CSS_SCORE/100)${NC}"

# 3. Static Assets (Raw)
ASSET_BYTES=$(find .svelte-kit/output/client -type f -not -name "*.js" -not -name "*.css" -not -name "*.html" -not -name "*.json" -print0 | xargs -0 cat | wc -c)
ASSET_KB=$((ASSET_BYTES / 1024))

if [ "$ASSET_KB" -lt 2000 ]; then
  ASSET_SCORE=100
  ASSET_COLOR=$GREEN
elif [ "$ASSET_KB" -lt 5000 ]; then
  ASSET_SCORE=90
  ASSET_COLOR=$GREEN
elif [ "$ASSET_KB" -lt 10000 ]; then
  ASSET_SCORE=70
  ASSET_COLOR=$YELLOW
else
  ASSET_SCORE=40
  ASSET_COLOR=$RED
fi
TOTAL_SCORE=$((TOTAL_SCORE + ASSET_SCORE))
echo -e "🖼️  Assets:           ${ASSET_KB}KB ${CYAN}(raw)${NC}     ${ASSET_COLOR}($ASSET_SCORE/100)${NC}"

# 4. Dependencies
DEP_COUNT=$(node -p "Object.keys(require('./package.json').dependencies || {}).length")
if [ "$DEP_COUNT" -lt 20 ]; then
  DEP_SCORE=100
  DEP_COLOR=$GREEN
elif [ "$DEP_COUNT" -lt 35 ]; then
  DEP_SCORE=85
  DEP_COLOR=$GREEN
elif [ "$DEP_COUNT" -lt 50 ]; then
  DEP_SCORE=60
  DEP_COLOR=$YELLOW
else
  DEP_SCORE=40
  DEP_COLOR=$RED
fi
TOTAL_SCORE=$((TOTAL_SCORE + DEP_SCORE))
echo -e "📚 Dependencies:     ${DEP_COUNT} pkgs          ${DEP_COLOR}($DEP_SCORE/100)${NC}"

# --- Real-World Pi 5 Performance Est. ---
# Specs:
# - SD Card: ~80MB/s Read (UHS-I)
# - Network: ~100MB/s (Gigabit LAN)
# - CPU Parse: ~5MB/s (Cortex-A76 estimate for complex JS)

TOTAL_BUNDLE_KB=$((JS_RAW_KB + CSS_GZIP_KB + ASSET_KB))

# Calculations in milliseconds
TIME_DISK=$((TOTAL_BUNDLE_KB * 1000 / 80000)) # 80MB/s
TIME_NETWORK=$((TOTAL_BUNDLE_KB * 1000 / 100000)) # 100MB/s (LAN)
TIME_PARSE=$((JS_RAW_KB * 1000 / 5000)) # 5MB/s Parse Speed
TOTAL_TIME=$((TIME_DISK + TIME_NETWORK + TIME_PARSE))

echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}   ⏱️  Real-World Pi 5 Load Time (Estimated)${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

if [ "$TOTAL_TIME" -lt 100 ]; then
  TIME_COLOR=$GREEN
  TIME_VERDICT="⚡ Instant"
elif [ "$TOTAL_TIME" -lt 300 ]; then
  TIME_COLOR=$GREEN
  TIME_VERDICT="🚀 Very Fast"
elif [ "$TOTAL_TIME" -lt 1000 ]; then
  TIME_COLOR=$YELLOW
  TIME_VERDICT="⚠️  Noticeable"
else
  TIME_COLOR=$RED
  TIME_VERDICT="❌ Slow"
fi

echo -e "   ${TIME_COLOR}Est. Cold Start:    ~${TOTAL_TIME}ms (${TIME_VERDICT})${NC}"
echo -e "     • Disk Read (SD):   ${TIME_DISK}ms"
echo -e "     • Network (LAN):    ${TIME_NETWORK}ms"
echo -e "     • CPU Parse (A76):  ${TIME_PARSE}ms"

# Final Score Calculation
FINAL_SCORE=$((TOTAL_SCORE / METRICS_COUNT))

echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

# Grade
if [ "$FINAL_SCORE" -ge 90 ]; then
  GRADE="A+"
  FINAL_COLOR=$GREEN
  VERDICT="🚀 Perfect for Pi 5! Highly optimized."
elif [ "$FINAL_SCORE" -ge 80 ]; then
  GRADE="A"
  FINAL_COLOR=$GREEN
  VERDICT="✅ Excellent performance on Pi 5."
elif [ "$FINAL_SCORE" -ge 70 ]; then
  GRADE="B"
  FINAL_COLOR=$GREEN
  VERDICT="👍 Good. Solid performance."
elif [ "$FINAL_SCORE" -ge 60 ]; then
  GRADE="C"
  FINAL_COLOR=$YELLOW
  VERDICT="⚠️  Acceptable, but room for improvement."
else
  GRADE="F"
  FINAL_COLOR=$RED
  VERDICT="❌ Heavy. Will feel sluggish on Pi 5."
fi

echo -e "   ${FINAL_COLOR}FINAL SCORE: ${FINAL_SCORE}/100 (${GRADE})${NC}"
echo -e "   ${VERDICT}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
