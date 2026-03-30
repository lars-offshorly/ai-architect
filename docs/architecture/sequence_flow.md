# Sequence Flow

## Conversation Flow

```
FE                    API Router           ConversationFlow       Interpreter         Replier
 |                        |                      |                     |                 |
 |-- POST /sessions ----→ |                      |                     |                 |
 |                        |-- process_turn() --→ |                     |                 |
 |                        |                      |-- interpret() ----→ |                 |
 |                        |                      |                     |-- extract() -→  |
 |                        |                      |                     |-- classify() →  |
 |                        |                      |←-- extracted, suggested -------------- |
 |                        |                      |                     |                 |
 |                        |                      | [top bundle found?] |                 |
 |                        |                      |                     |                 |
 |                        |                      |-- build_clarification() --------→      |
 |                        |                      |←-- (missing_field, question) --------- |
 |                        |                      |                     |                 |
 |                        | [missing fields?]    |                     |                 |
 |                        |  → status: awaiting_input                  |                 |
 |                        | [slots complete, unconfirmed?]             |                 |
 |                        |  → status: pending_confirmation            |                 |
 |                        | [confirmed?]         |                     |                 |
 |                        |  → status: ready_for_preview               |                 |
 |←-- response ---------- |                      |                     |                 |
```

## Preview Flow

```
FE                    API Router           PreviewFlow       PreviewGenerator      AppGenerator
 |                        |                    |                    |                   |
 |-- POST /preview -----→ |                    |                    |                   |
 |                        |-- flow.run() ----→ |                    |                   |
 |                        |                    |-- generate() ----→ |                   |
 |                        |                    |                    |-- fetch template   |
 |                        |                    |                    |-- inject extracted |
 |                        |                    |                    |-- validate         |
 |                        |                    |←-- preview, dummy  |                   |
 |                        |                    |-- assemble() ----------------------------→|
 |                        |                    |                    |                   |-- load app.json
 |                        |                    |                    |                   |-- validate
 |                        |                    |                    |                   |-- format payload
 |                        |                    |←-- AppPayload --------------------------------|
 |←-- AppPayloadResponse  |                    |                    |                   |
```
