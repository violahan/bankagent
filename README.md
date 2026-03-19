# BankAgent Demo Overview


```text
┌──────────────────────────────────────────────────────────────────────────────┐
│  User / OrchestratorAgent                                                    │
│                                                                              │
│  Receives a loan application request and coordinates the full workflow.      │
└───────────────┬──────────────────────────────────────┬───────────────────────┘
                │  A2A Protocol                        │  A2A Protocol 
                ▼                                      ▼
┌─────────────────────────────┐          ┌───────────────────────────────────────┐
│  CreditCheckAgent           │          │  AnalyseAgent                         │
│                             │          │                                       │
│                             │          │ 1. read user profile and credit check │
│  Looks up applicant credit  │          │ 2. fetch bank rules from MCP          │
│  data and returns a report  │          │ 3. then conduct analysis              │
└─────────────────────────────┘          └──────────────────┬────────────────────┘
                                                            │  MCP Protocol
                                                            │ 
                                                            ▼
                                           ┌─────────────────────────────────────┐
                                           │  CreditServicesMCP                  │
                                           │  MCP Server (tools/resources)       │
                                           │                                     │
                                           │  Exposes rules + credit-check tools │
                                           └─────────────────────────────────────┘
```

## What this means

- `OrchestratorAgent` talks to the two specialist agents over `A2A`.
- `CreditCheckAgent` does not use MCP. It only returns the applicant's credit-check result.
- `AnalyseAgent` uses `MCP` to fetch the current bank policy rules from `CreditServicesMCP`.
- `CreditServicesMCP` is not an agent. It is the tool server behind the analysis step.
- `CreditServicesMCP` now also exposes the same mock credit-check behavior used by `CreditCheckAgent`.

## End-to-end flow

1. The user sends a loan request to `OrchestratorAgent`.
2. `OrchestratorAgent` calls `CreditCheckAgent` over A2A to get the applicant's credit report.
3. `OrchestratorAgent` sends the applicant profile and credit report to `AnalyseAgent` over A2A.
4. `AnalyseAgent` calls `CreditServicesMCP` over MCP to fetch the relevant rules.
5. `AnalyseAgent` returns a `PASS`, `FAIL`, or `MANUAL REVIEW` decision.
6. `OrchestratorAgent` combines everything into the final response.

## Repo mapping

- [OrchestratorAgent/orchestrator.py](/Users/viohan/Desktop/BankAgent/OrchestratorAgent/orchestrator.py)
- [CreditCheckAgent/credit_check_a2a_server.py](/Users/viohan/Desktop/BankAgent/CreditCheckAgent/credit_check_a2a_server.py)
- [AnalyseAgent/analyse_agent_a2a_server.py](/Users/viohan/Desktop/BankAgent/AnalyseAgent/analyse_agent_a2a_server.py)
- [CreditServicesMCP/mcp_server.py](/Users/viohan/Desktop/BankAgent/CreditServicesMCP/mcp_server.py)
- [shared_credit_check.py](/Users/viohan/Desktop/BankAgent/shared_credit_check.py)
