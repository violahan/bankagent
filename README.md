# BankAgent Demo Overview


```text
┌──────────────────────────────────────────────────────────────────────────────┐
│  User / OrchestratorAgent                                                    │
│                                                                              │
│  Receives a loan application request and coordinates the full workflow.      │
└───────────────────────────────┬───────────────────────────────────────────────┘
                                │  A2A Protocol
                                ▼
                 ┌─────────────────────────────────────────────────────────────┐
                 │  AnalyseAgent                                               │
                 │                                                             │
                 │ 1. read user profile                                        │
                 │ 2. call MCP to generate credit check                        │
                 │ 3. call MCP to fetch bank rules                             │
                 │ 4. return credit analysis                                   │
                 └──────────────────────┬──────────────────────────────────────┘
                                        │  MCP Protocol
                                        │
                                        ▼
                       ┌─────────────────────────────────────────────────────┐
                       │  CreditServicesMCP                                  │
                       │  MCP Server (tools/resources)                       │
                       │                                                     │
                       │  Exposes rules + credit-check tools                 │
                       └─────────────────────────────────────────────────────┘
```

## What this means

- `OrchestratorAgent` talks only to `AnalyseAgent` over `A2A`.
- `AnalyseAgent` uses `MCP` to fetch the current bank policy rules and generate the applicant credit-check result from `CreditServicesMCP`.
- `CreditServicesMCP` is not an agent. It is the tool server behind the analysis step.
- All credit-check logic now lives in `CreditServicesMCP/mcp_server.py`.

## End-to-end flow

1. The user sends a loan request to `OrchestratorAgent`.
2. `OrchestratorAgent` sends the application details to `AnalyseAgent` over A2A.
3. `AnalyseAgent` calls `CreditServicesMCP` over MCP to generate the applicant's credit report.
4. `AnalyseAgent` calls `CreditServicesMCP` over MCP to fetch the relevant rules.
5. `AnalyseAgent` returns a `PASS`, `FAIL`, or `MANUAL REVIEW` decision.
6. `OrchestratorAgent` combines everything into the final response.

## Repo mapping

- [OrchestratorAgent/orchestrator.py](/Users/viohan/Desktop/BankAgent/OrchestratorAgent/orchestrator.py)
- [AnalyseAgent/analyse_agent_a2a_server.py](/Users/viohan/Desktop/BankAgent/AnalyseAgent/analyse_agent_a2a_server.py)
- [CreditServicesMCP/mcp_server.py](/Users/viohan/Desktop/BankAgent/CreditServicesMCP/mcp_server.py)
