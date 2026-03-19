# BankAgent Demo Overview

| Demo | What it shows | LLM key needed? |
|------|--------------|-----------------|
| **Demo 1** — MCP Server | How tools are exposed and called via the Model Context Protocol | No |
| **Demo 2** — LangChain Agent + MCP | How an LLM autonomously picks and calls tools | No (Ollama, free & local) |
| **Demo 3** — A2A Protocol | How independent agents discover each other and exchange tasks | No |

## How the pieces fit together

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│  User / OrchestratorAgent                                                    │
│                                                                              │
│  Receives a loan application request and coordinates the full workflow.      │
└───────────────┬──────────────────────────────────────┬───────────────────────┘
                │  A2A Protocol (HTTP)                 │  A2A Protocol (HTTP)
                ▼                                      ▼
┌─────────────────────────────┐          ┌─────────────────────────────────────┐
│  CreditCheckAgent           │          │  AnalyseAgent                       │
│  (A2A server)               │          │  (A2A server)                       │
│                             │          │                                     │
│  Looks up applicant credit  │          │  Uses MCP tools internally          │
│  data and returns a report  │          │  to fetch bank credit policy        │
└─────────────────────────────┘          └──────────────────┬──────────────────┘
                                                            │  MCP Protocol
                                                            │  (streamable HTTP)
                                                            ▼
                                           ┌─────────────────────────────────────┐
                                           │  RuleFetchMCP                       │
                                           │  MCP Server (tools/resources)       │
                                           │                                     │
                                           │  Exposes get_credit_check_rules     │
                                           └─────────────────────────────────────┘
```

## What this means

- `OrchestratorAgent` talks to the two specialist agents over `A2A`.
- `CreditCheckAgent` does not use MCP. It only returns the applicant's credit-check result.
- `AnalyseAgent` uses `MCP` to fetch the current bank policy rules from `RuleFetchMCP`.
- `RuleFetchMCP` is not an agent. It is the tool server behind the analysis step.

## End-to-end flow

1. The user sends a loan request to `OrchestratorAgent`.
2. `OrchestratorAgent` calls `CreditCheckAgent` over A2A to get the applicant's credit report.
3. `OrchestratorAgent` sends the applicant profile and credit report to `AnalyseAgent` over A2A.
4. `AnalyseAgent` calls `RuleFetchMCP` over MCP to fetch the relevant rules.
5. `AnalyseAgent` returns a `PASS`, `FAIL`, or `MANUAL REVIEW` decision.
6. `OrchestratorAgent` combines everything into the final response.

## Repo mapping

- [OrchestratorAgent/orchestrator.py](/Users/viohan/Desktop/BankAgent/OrchestratorAgent/orchestrator.py)
- [CreditCheckAgent/credit_check_a2a_server.py](/Users/viohan/Desktop/BankAgent/CreditCheckAgent/credit_check_a2a_server.py)
- [AnalyseAgent/analyse_agent_a2a_server.py](/Users/viohan/Desktop/BankAgent/AnalyseAgent/analyse_agent_a2a_server.py)
- [RuleFetchMCP/mcp_server.py](/Users/viohan/Desktop/BankAgent/RuleFetchMCP/mcp_server.py)
