#!/usr/bin/env bash
# Test the A2A server (strands.multiagent.a2a.A2AServer + FastAPI)
#
# Start the server first:
#   cd AnalyseAgent && uvicorn a2a_server:app --host 0.0.0.0 --port 8001

BASE_URL="${A2A_URL:-http://localhost:8001}"

echo "=== Agent Card ==="
curl -s "${BASE_URL}/.well-known/agent.json" | jq .

echo ""
echo "=== message/send ==="
curl -s -X POST "${BASE_URL}/" \
  -H "Content-Type: application/json" \
  -d '{
  "jsonrpc": "2.0",
  "id": "req-001",
  "method": "message/send",
  "params": {
    "message": {
      "role": "user",
      "parts": [
        {
          "kind": "text",
          "text": "## User Profile\nName: Jane Doe\nAge: 34\nEmployment status: full-time\nAnnual income: $85,000\nExisting monthly debt payments: $1,200\nApplying for: personal loan for debt consolidation\n\n## Credit-Check Result\nBureau score: 710\nDebt-to-income ratio: 0.35\nCredit utilisation: 0.42\nNumber of delinquencies: 0\nBankruptcies: 0\nHard inquiries in last 6 months: 2\nExternal rating: B"
        }
      ],
      "messageId": "12345678-1234-1234-1234-123456789012"
    }
  }
}' | jq .
