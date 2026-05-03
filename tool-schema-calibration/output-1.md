╭────────────────────────────────────────────────────────────────────╮
│ Tool Schema Calibration                                            │
│ Measuring the impact of description quality on LLM tool selection. │
│ 50 queries x 2 strategies (Loose vs Tight)                         │
╰────────────────────────────────────────────────────────────────────╯

-- Loose Schema Calibration --------------------------------------

╭──────────────────────────────────────────── Model Input ────────────────────────────────────────────╮
│                                                                                                     │
│  USER: How is the weather in Tokyo right now?                                                       │
│                                                                                                     │
╰─────────────────────────────────────────────────────────────────────────────────────────────────────╯

╭────────────────────────────────────────── Model Response ───────────────────────────────────────────╮
│                                                                                                     │
│  ASSISTANT: Selected tool: get_weather_current                                                      │
│                                                                                                     │
╰─────────────────────────────────────────────────────────────────────────────────────────────────────╯

  Run #01: o  1.2s     Run #02: o  1.0s     Run #03: o  0.7s     Run #04: o  1.0s     Run #05: o  1.0s   
  Run #06: o  0.9s     Run #07: o  1.0s     Run #08: o  0.9s     Run #09: o  0.8s     Run #10: o  1.0s   
  Run #11: o  1.0s     Run #12: o  0.9s     Run #13: o  0.9s     Run #14: o  0.9s     Run #15: o  1.0s   
  Run #16: o  0.9s     Run #17: o  1.0s     Run #18: o  1.0s     Run #19: o  1.0s     Run #20: o  0.9s   
  Run #21: o  1.0s     Run #22: o  1.1s     Run #23: o  0.9s     Run #24: o  0.9s     Run #25: o  0.9s   
  Run #26: o  0.9s     Run #27: o  1.1s     Run #28: o  1.0s     Run #29: o  0.9s     Run #30: o  1.0s   
  Run #31: o  1.9s     Run #32: o  1.0s     Run #33: o  0.9s     Run #34: o  0.8s     Run #35: o  0.8s   
  Run #36: o  1.1s     Run #37: o  1.0s     Run #38: o  1.6s     Run #39: o  1.1s     Run #40: o  1.0s   
  Run #41: o  1.0s     Run #42: o  1.1s     Run #43: o  0.9s     Run #44: o  1.2s     Run #45: o  1.1s   
  Run #46: o  1.2s     Run #47: o  1.1s     Run #48: o  1.0s     Run #49: o  1.0s     Run #50: o  0.9s   


────────────────────────────────────────── Intermediate Results ──────────────────────────────────────────
Loose Accuracy: XXXXXXX.............  18/50  (36%)

-- Tight Schema Calibration --------------------------------------

╭───────────────────────────────────────────── Model Input ──────────────────────────────────────────────╮
│                                                                                                        │
│  USER: How is the weather in Tokyo right now?                                                          │
│                                                                                                        │
╰────────────────────────────────────────────────────────────────────────────────────────────────────────╯

╭──────────────────────────────────────────── Model Response ────────────────────────────────────────────╮
│                                                                                                        │
│  ASSISTANT: Selected tool: get_weather_current                                                         │
│                                                                                                        │
╰────────────────────────────────────────────────────────────────────────────────────────────────────────╯

  Run #01: o  1.0s     Run #02: o  1.0s     Run #03: o  0.8s     Run #04: o  1.0s     Run #05: o  0.8s   
  Run #06: o  0.9s     Run #07: o  1.0s     Run #08: o  1.0s     Run #09: o  0.9s     Run #10: o  1.0s   
  Run #11: o  1.0s     Run #12: o  0.8s     Run #13: o  2.0s     Run #14: o  0.9s     Run #15: o  1.0s   
  Run #16: o  0.8s     Run #17: o  1.0s     Run #18: o  0.9s     Run #19: o  1.0s     Run #20: o  1.0s   
  Run #21: o  1.0s     Run #22: o  1.0s     Run #23: o  1.0s     Run #24: o  0.8s     Run #25: o  0.9s   
  Run #26: o  0.9s     Run #27: o  1.1s     Run #28: o  1.0s     Run #29: o  1.0s     Run #30: o  1.0s   
  Run #31: o  1.1s     Run #32: o  0.8s     Run #33: o  0.9s     Run #34: o  0.7s     Run #35: o  0.9s   
  Run #36: o  1.1s     Run #37: o  0.8s     Run #38: o  1.0s     Run #39: o  0.9s     Run #40: o  1.1s   
  Run #41: o  0.8s     Run #42: o  1.0s     Run #43: o  1.0s     Run #44: o  1.0s     Run #45: o  1.1s   
  Run #46: o  1.1s     Run #47: o  1.9s     Run #48: o  1.1s     Run #49: o  1.0s     Run #50: o  0.9s   


──────────────────────────────────────────── Overall Summary ─────────────────────────────────────────────

                           Calibration Results                           
┏━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Strategy                 ┃ Score ┃ Accuracy Bar                       ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ Loose (Overlapping)      │ 18/50 │ XXXXXXX.............  18/50  (36%) │
├──────────────────────────┼───────┼────────────────────────────────────┤
│ Tight (Disambiguated)    │ 32/50 │ XXXXXXXXXXXXX.......  32/50  (64%) │
├──────────────────────────┼───────┼────────────────────────────────────┤
│ Accuracy Delta           │  +14  │                                    │
└──────────────────────────┴───────┴────────────────────────────────────┘

VERDICT: Significant Improvement! Tightening schemas clearly reduces LLM confusion.
