cd "$(dirname "$0")"
source jarvis-env/bin/activate
source ~/.jarvis_secret 2>/dev/null
echo "══════ JARVIS DOCTOR ══════"
grep -c "^export" ~/.jarvis_secret 2>/dev/null | sed 's/^/secret exports: /'
lsof -ti :4710 | xargs kill -9 2>/dev/null; sleep 1
nohup python3 jarvis_gateway.py > jarvis_gateway.log 2>&1 &
echo "gateway launched → jarvis_gateway.log"; sleep 5
S=$(curl -s -m 5 localhost:4710/api/status)
echo "STATUS → ${S:-✗ NO RESPONSE}"
T0=$(date +%s%N); C=$(curl -s -m 30 -X POST localhost:4710/api/chat -H 'Content-Type: application/json' -d '{"text":"one word: ready?"}'); T1=$(date +%s%N)
echo "CHAT   → $(echo $C | head -c 110)  ($(( (T1-T0)/1000000 ))ms)"
T0=$(date +%s%N); curl -s -m 60 -X POST localhost:4710/api/speak -H 'Content-Type: application/json' -d '{"text":"warm"}' -o /tmp/jd.wav; T1=$(date +%s%N)
file /tmp/jd.wav | grep -qi "wave\|audio" && echo "SPEAK  → ✓ warm ($(( (T1-T0)/1000000 ))ms)" || echo "SPEAK  → ✗ $(head -c 90 /tmp/jd.wav)"
python3 -c "import numpy,soundfile;soundfile.write('/tmp/jw.wav',numpy.zeros(8000,dtype='float32'),16000)" 2>/dev/null
T0=$(date +%s%N); curl -s -m 120 -X POST localhost:4710/api/transcribe -F "audio=@/tmp/jw.wav" > /dev/null; T1=$(date +%s%N)
echo "EARS   → ✓ warm ($(( (T1-T0)/1000000 ))ms)"
echo "── last log ──"; tail -4 jarvis_gateway.log
echo "═══════════════════════════"
