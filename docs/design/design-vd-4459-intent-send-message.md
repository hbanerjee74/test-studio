# Design: intent_send_message Tool

**Issue:** [VD-4459](https://linear.app/acceleratedata/issue/VD-4459)  
**Status:** Design Review  
**Author:** AI Agent (OpenHands)  
**Date:** 2026-08-26

---

## 1. Overview

### 1.1 Problem Statement
An AgentSession can identify another Intent but cannot send that already-open Intent a normal Conversation message based on the work occurring in its own session.

### 1.2 Goal
Provide an always-available `intent_send_message` tool that sends plain text to an existing open Intent through Studio's normal send-message behavior.

### 1.3 Non-Goals
- A separate steering, correction, or interrupt protocol
- Opening, waking, or recovering the target
- Attachments, file upload, or a new message format
- Cross-Domain access or a durable cross-session relationship

---

## 2. Acceptance Criteria

| # | Criterion | Verification |
|---|-----------|--------------|
| 1 | `intent_send_message` accepts a target Intent ID and a non-empty plain-text message | Schema validation |
| 2 | The target must already be open and in the calling Intent's Domain | Domain membership check |
| 3 | The calling actor must hold the target's active edit lease when the send is admitted | Lease validation |
| 4 | The tool delegates to the existing send-message behavior, including its established in-flight-turn handling | Delegation verification |
| 5 | An unopened, read-only, terminal, invisible, cross-Domain, or foreign-lease target is rejected without delivering a message | Rejection state coverage |
| 6 | The send does not wake, reopen, or create a target AgentSession | Lifecycle verification |
| 7 | The action is scoped to the live AgentSession and creates no durable cross-session relationship | Session scope verification |
| 8 | Results identify the exact target and existing send outcome without exposing credentials or internal runtime details | Response sanitization |
| 9 | The tool follows established confirmation and dispatch-audit policies | Audit compliance |

---

## 3. Tool Schema

### 3.1 Tool Definition

```json
{
  "name": "intent_send_message",
  "description": "Send a message to an already-open Intent in the calling Intent's same Domain. The target must be open and the calling actor must hold its active edit lease.",
  "parameters": {
    "type": "object",
    "properties": {
      "intentId": {
        "type": "string",
        "description": "UUID of the target Intent to send the message to. Must be open and in the same Domain as the calling Intent."
      },
      "message": {
        "type": "string",
        "description": "Plain text message to send. Must be non-empty. Markdown formatting is supported.",
        "minLength": 1
      },
      "security_risk": {
        "type": "string",
        "enum": ["UNKNOWN", "LOW", "MEDIUM", "HIGH"],
        "description": "The LLM's assessment of the safety risk of this action."
      },
      "summary": {
        "type": "string",
        "description": "A concise summary (approximately 10 words) describing what this specific action does."
      }
    },
    "required": ["intentId", "message"],
    "additionalProperties": false
  }
}
```

### 3.2 Response Schema

```json
{
  "type": "object",
  "properties": {
    "success": {
      "type": "boolean",
      "description": "Whether the message was successfully dispatched"
    },
    "targetIntentId": {
      "type": "string",
      "description": "The UUID of the target Intent that received the message"
    },
    "message": {
      "type": "string",
      "description": "Human-readable description of the outcome"
    }
  },
  "required": ["success", "targetIntentId", "message"]
}
```

---

## 4. Implementation Design

### 4.1 Admission Flow

```
+--------------------------------------------------------------------------------+
|                         intent_send_message                                    |
+--------------------------------------------------------------------------------+
                                      |
                                      v
+--------------------------------------------------------------------------------+
|  1. VALIDATE INPUT                                                             |
|     - intentId is a valid UUID format                                          |
|     - message is non-empty string                                              |
|     - FAIL: Return 400 Bad Request with validation details                     |
+--------------------------------------------------------------------------------+
                                      |
                                      v
+--------------------------------------------------------------------------------+
|  2. RESOLVE TARGET INTENT                                                      |
|     - Lookup intent by ID                                                      |
|     - FAIL: Return 404 if intent not found                                     |
+--------------------------------------------------------------------------------+
                                      |
                                      v
+--------------------------------------------------------------------------------+
|  3. DOMAIN MEMBERSHIP CHECK                                                    |
|     - Verify target.domainId == caller.domainId                                |
|     - FAIL: Return 403 Forbidden (cross-Domain)                                |
+--------------------------------------------------------------------------------+
                                      |
                                      v
+--------------------------------------------------------------------------------+
|  4. VISIBILITY CHECK                                                           |
|     - Verify caller has visibility to target Intent                            |
|     - FAIL: Return 403 Forbidden (invisible)                                   |
+--------------------------------------------------------------------------------+
                                      |
                                      v
+--------------------------------------------------------------------------------+
|  5. STATE CHECK - Target must be OPEN                                          |
|     - Verify target.status in OPEN_STATES                                      |
|     - REJECT if: unopened, terminal, archived                                  |
|     - FAIL: Return 409 Conflict with state details                             |
+--------------------------------------------------------------------------------+
                                      |
                                      v
+--------------------------------------------------------------------------------+
|  6. EDIT LEASE VALIDATION                                                      |
|     - Fetch active lease for target Intent                                     |
|     - Verify lease.holder == caller.actorId                                    |
|     - Verify lease.status == "active"                                          |
|     - Verify lease has not expired                                             |
|     - FAIL: Return 423 Locked if foreign lease                                 |
|     - FAIL: Return 423 Locked if no active lease                               |
+--------------------------------------------------------------------------------+
                                      |
                                      v
+--------------------------------------------------------------------------------+
|  7. DELEGATE TO SEND-MESSAGE BEHAVIOR                                          |
|     - Call existing IntentMessageService.sendMessage()                         |
|     - Pass: targetIntentId, message content, caller context                    |
|     - Preserve in-flight-turn handling                                         |
+--------------------------------------------------------------------------------+
                                      |
                                      v
+--------------------------------------------------------------------------------+
|  8. RETURN RESULT                                                              |
|     - Success: Return 200 with dispatch confirmation                           |
|     - Failure: Return appropriate error code                                   |
+--------------------------------------------------------------------------------+
```

### 4.2 Rejection States (Pre-Delivery)

The following target states result in rejection **without** delivering a message:

| State Category | Specific States | HTTP Status | Error Code |
|----------------|-----------------|-------------|------------|
| Not Open | DRAFT, ARCHIVED, COMPLETED, CLOSED, DELETED | 409 Conflict | intent_not_open |
| Cross-Domain | domainId != caller.domainId | 403 Forbidden | cross_domain_access |
| Invisible | Not in caller's visibility set | 403 Forbidden | intent_not_visible |
| Foreign Lease | lease.holder != caller.actorId | 423 Locked | foreign_lease |
| No Lease | No active lease exists | 423 Locked | no_active_lease |
| Expired Lease | lease.expiresAt < now() | 423 Locked | lease_expired |

### 4.3 Lease Fencing

To prevent race conditions where the lease changes between validation and dispatch:

1. **Optimistic Check**: Perform all validations in a single transaction
2. **Lease Version**: Include lease version/timestamp in the send-message call
3. **Atomic Validation**: The send-message behavior re-validates lease ownership atomically
4. **Failure on Stale Lease**: If lease changed during processing, return 423 Locked

---

## 5. Security Considerations

### 5.1 Risk Assessment

| Risk | Severity | Mitigation |
|------|----------|------------|
| Lease bypass | HIGH | Atomic validation in send-message service |
| Cross-Domain message injection | HIGH | Domain membership check at admission |
| Message spoofing | MEDIUM | Caller attribution preserved in message metadata |
| Information leakage | MEDIUM | Error messages sanitized, no internal IDs exposed |
| Session hijacking | LOW | Existing session authentication applies |

### 5.2 Data Exposure

- **Response must NOT include**: Internal runtime IDs, lease tokens, session secrets
- **Response includes**: Target Intent ID (provided by caller), success boolean, human-readable message
- **Audit log includes**: Caller ID, target ID, timestamp, success/failure, rejection reason (if any)

---

## 6. Integration Points

### 6.1 Existing Services

| Service | Usage |
|---------|-------|
| `IntentQueryService` | Resolve target Intent by ID |
| `DomainMembershipService` | Verify Domain membership and visibility |
| `LeaseService` | Fetch and validate edit lease |
| `IntentMessageService` | Delegate message send with in-flight-turn handling |
| `AuditLogService` | Record dispatch attempts and outcomes |

### 6.2 Tool Registry

The tool must be registered in:
- Tool schema registry (for LLM tool definition)
- Capability manifest (for availability checks)
- Permission matrix (for action authorization)

---

## 7. Testing Strategy

### 7.1 Unit Tests

| Test Case | Description |
|-----------|-------------|
| Schema validation | Reject invalid UUIDs, empty messages |
| Domain boundary | Reject cross-Domain attempts |
| Visibility filter | Reject invisible Intents |
| State machine | Reject unopened, terminal, archived states |
| Lease ownership | Reject foreign lease holders |
| Lease expiration | Reject expired leases |
| Success path | Accept valid open Intent with owned lease |

### 7.2 Integration Tests

| Test Case | Description |
|-----------|-------------|
| In-flight-turn handling | Verify delegation preserves turn handling |
| Lease race condition | Simulate lease change mid-operation |
| Audit logging | Verify dispatch events logged correctly |
| Message delivery | Verify message appears in target conversation |

### 7.3 End-to-End Tests

| Test Case | Description |
|-----------|-------------|
| Full flow | Create Intent A -> Create Intent B -> Send message A->B |
| Concurrent sends | Multiple messages to same target from different callers |
| Lease transfer | Send fails after lease transferred to another actor |

---

## 8. Error Handling

### 8.1 Error Response Format

```json
{
  "success": false,
  "targetIntentId": "uuid-provided-by-caller",
  "message": "Human-readable description",
  "error": {
    "code": "error_code_enum",
    "details": "Additional context (optional)"
  }
}
```

### 8.2 Error Code Reference

| Error Code | HTTP Status | Trigger |
|------------|-------------|---------|
| invalid_input | 400 | Schema validation failure |
| intent_not_found | 404 | Target Intent does not exist |
| cross_domain_access | 403 | Target in different Domain |
| intent_not_visible | 403 | Caller lacks visibility |
| intent_not_open | 409 | Target not in open state |
| foreign_lease | 423 | Lease held by different actor |
| no_active_lease | 423 | No active lease on target |
| lease_expired | 423 | Active lease has expired |
| dispatch_failed | 500 | Internal send-message failure |

---

## 9. Related Work

### 9.1 Completed Issues (Reference Implementation)

| Issue | Tool | Reusable Patterns |
|-------|------|-------------------|
| VD-3985 | `create_intent` | Domain validation, response schema |
| VD-3991 | `fork_intent` | Lease handling, Intent state checks |
| VD-4097 | `list_intents` | Visibility filtering, Domain scoping |
| VD-4098 | `open_intent`, `close_intent`, etc. | Lease ownership, state transitions |

### 9.2 Related Designs

- `docs/design/intent/agent-initiated-intent-tools.md`
- `docs/design/intent/intent-access-token.md`
- `docs/design/intent/joint-lifecycle-and-concurrency.md`

### 9.3 Functional Specifications

- `docs/functional/intent/README.md`
- `docs/functional/intent/lifecycle.md`

---

## 10. Implementation Checklist

- [ ] Tool schema definition in registry
- [ ] Tool handler implementation
- [ ] Domain membership validation
- [ ] Visibility filtering
- [ ] Intent state validation
- [ ] Lease ownership verification
- [ ] Lease fencing (atomic check)
- [ ] Delegation to send-message service
- [ ] Response sanitization
- [ ] Audit logging integration
- [ ] Unit test coverage
- [ ] Integration test coverage
- [ ] Documentation update

---

## 11. Open Questions

1. **Rate limiting**: Should there be rate limits on messages sent to the same target Intent?
2. **Message size**: What is the maximum message length? (Current proposal: no limit beyond practical constraints)
3. **Markdown support**: Confirm full Markdown support or restrict to plain text only?
4. **Confirmation flow**: Does this tool require user confirmation before dispatching?

---

## 12. Approval

| Role | Name | Status | Date |
|------|------|--------|------|
| Author | AI Agent | Complete | 2026-08-26 |
| Reviewer | {User} | Pending | - |
| Approver | {User} | Pending | - |
