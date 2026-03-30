# BankAgent Overview

This repository contains a small multi-agent loan-review workflow built with:

- `OrchestratorAgent` as the user-facing coordinator
- `CreditCheckAgent` as an A2A specialist that generates a mock credit report
- `AnalyseAgent` as an A2A specialist that evaluates the applicant against policy
- `RuleFetchMCP` as the MCP server that exposes the loan policy rules

## Current components

| Component | Role | Interface | Default endpoint | Notes |
|------|------|------|------|------|
| `OrchestratorAgent` | Coordinates the end-to-end loan review flow | CLI app using A2A client tools | n/a | Calls the downstream agents by URL |
| `CreditCheckAgent` | Extracts applicant name/address and returns a formatted mock credit report | A2A server | `http://localhost:8082` | Uses a local tool to generate mock bureau-style data |
| `AnalyseAgent` | Reviews a user profile plus credit report against policy rules | A2A server | `http://localhost:8001` | Can use either local MCP or a remote Bedrock AgentCore MCP runtime |
| `RuleFetchMCP` | Exposes loan policy rules | MCP server | `http://localhost:8000/mcp` | Provides the `get_loan_application_review_rules` tool |

## Runtime requirements

- `OrchestratorAgent`, `CreditCheckAgent`, and `AnalyseAgent` all use Amazon Bedrock via `BedrockModel`.
- You need AWS credentials and access to the configured model in `ap-southeast-2` unless you override the environment variables.
- `AnalyseAgent` defaults to a remote MCP runtime secured with Cognito.
- If you want to use the local MCP server instead, set `MCP_URL=http://localhost:8000/mcp` when starting `AnalyseAgent`.

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

## What this means today

- `OrchestratorAgent` talks to the two specialist agents over `A2A`.
- `CreditCheckAgent` does not use MCP. It extracts name and address, then returns a fixed-format mock credit report.
- `AnalyseAgent` uses `MCP` to fetch the current bank policy rules from either `RuleFetchMCP` or the configured remote MCP runtime.
- `RuleFetchMCP` is not an agent. It is the tool server behind the analysis step.
- The MCP tool currently exposed by `RuleFetchMCP` is `get_loan_application_review_rules`.

## End-to-end flow

1. The user sends a loan request to `OrchestratorAgent`.
2. `OrchestratorAgent` calls `CreditCheckAgent` over A2A to get the applicant's credit report.
3. `OrchestratorAgent` sends the applicant profile and credit report to `AnalyseAgent` over A2A.
4. `AnalyseAgent` determines the matching `policy_type` and calls MCP to fetch the relevant loan policy rules.
5. `AnalyseAgent` returns a `PASS`, `FAIL`, or `MANUAL REVIEW` decision.
6. `OrchestratorAgent` combines everything into the final response.

## Supported policy types

`RuleFetchMCP` currently serves rule sets for:

- `personal_loan`
- `vehicle_loan`
- `mortgage_refinance`

## Running the stack

Local MCP mode:

1. Start the MCP server:
   `cd RuleFetchMCP && python mcp_server.py`
2. Start the analysis A2A server against the local MCP endpoint:
   `cd AnalyseAgent && MCP_URL=http://localhost:8000/mcp uvicorn analyse_agent_a2a_server:app --host 0.0.0.0 --port 8001`
3. Start the credit-check A2A server:
   `cd CreditCheckAgent && uvicorn credit_check_a2a_server:app --host 0.0.0.0 --port 8082`
4. Run the orchestrator:
   `cd OrchestratorAgent && python orchestrator.py`

Remote MCP mode:

1. Start the analysis A2A server with its default remote MCP configuration:
   `cd AnalyseAgent && uvicorn analyse_agent_a2a_server:app --host 0.0.0.0 --port 8001`
2. Start the credit-check A2A server:
   `cd CreditCheckAgent && uvicorn credit_check_a2a_server:app --host 0.0.0.0 --port 8082`
3. Run the orchestrator:
   `cd OrchestratorAgent && python orchestrator.py`

## Repo mapping

- [OrchestratorAgent/orchestrator.py](/Users/viohan/Desktop/BankAgent/OrchestratorAgent/orchestrator.py)
- [CreditCheckAgent/credit_check_a2a_server.py](/Users/viohan/Desktop/BankAgent/CreditCheckAgent/credit_check_a2a_server.py)
- [AnalyseAgent/analyse_agent_a2a_server.py](/Users/viohan/Desktop/BankAgent/AnalyseAgent/analyse_agent_a2a_server.py)
- [RuleFetchMCP/mcp_server.py](/Users/viohan/Desktop/BankAgent/RuleFetchMCP/mcp_server.py)
