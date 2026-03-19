#curl -X POST http://0.0.0.0:8082/ \
#-H "Content-Type: application/json" \
#-d '{
#  "jsonrpc": "2.0",
#  "id": "req-001",
#  "method": "message/send",
#  "params": {
#    "message": {
#      "role": "user",
#      "parts": [
#        {
#          "kind": "text",
#          "text": "I want the credit check result from Jane Doe whose address is 123 Maple Street, Springfield, IL 62704."
#        }
#      ],
#      "messageId": "12345678-1234-1234-1234-123456789012"
#    }
#  }
#}' | jq .

# test query agent card
curl http://0.0.0.0:8082/.well-known/agent-card.json | jq .