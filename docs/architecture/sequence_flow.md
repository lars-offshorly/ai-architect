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
FE                    API Router           PreviewFlow       PreviewGenerator   BundleTemplateLoader  StaticDashboardOutputRegistry
 |                        |                    |                    |                   |                          |
 |-- POST /preview -----→ |                    |                    |                   |                          |
 |                        |-- flow.run() ----→ |                    |                   |                          |
 |                        |                    |-- generate() ----→ |                   |                          |
 |                        |                    |                    |-- extract context  |                          |
 |                        |                    |                    |-- resolve flags    |                          |
 |                        |                    |                    |-- sample data      |                          |
 |                        |                    |                    |-- build KPIs       |                          |
 |                        |                    |                    |-- emit_preview     |                          |
 |                        |                    |←-- generation_json, dummy_data_json     |                          |
 |                        |                    |                    |                   |                          |
 |                        |                    |-- _apply_bundle_template() ----------→ |                          |
 |                        |                    |                    |                   |-- load app-0*.json        |
 |                        |                    |                    |                   |-- overlay stores          |
 |                        |                    |←-- stores overlaid |                   |                          |
 |                        |                    |                    |                   |                          |
 |                        |                    |-- _enrich_dashboard_widgets() --------------------------------→   |
 |                        |                    |                    |                   |                          |-- resolve variant
 |                        |                    |                    |                   |                          |-- load dashboard_output_templates/*.json
 |                        |                    |←-- dashboard_widgets injected --------------------------------    |
 |                        |                    |                    |                   |                          |
 |                        |                    |-- build AppPayload |                   |                          |
 |←-- AppPayload -------- |                    |                    |                   |                          |
```
