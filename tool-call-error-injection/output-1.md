╭────────────────────────────────────────────────────────────────╮
│ Tool Call Error Injection & Handling                           │
│ Demonstrating model transparency when upstream APIs fail.      │
│ 3 scenarios: No Guidance, Explicit Guidance, Irrelevant Prompt │
╰────────────────────────────────────────────────────────────────╯

-- Scenario A: No Error Guidance --------------------------
──────────────────────────────────────────── ROUND 1 ────────────────────────────────────────────
╭───────────────────────────────────────── Model Input ─────────────────────────────────────────╮
│                                                                                               │
│  SYSTEM: You are a helpful weather assistant.                                                 │
│  ───────────────────────────────────────────────────────────────────────────────────────────  │
│  USER: What is the current weather in Tokyo and London?                                       │
│                                                                                               │
╰───────────────────────────────────────────────────────────────────────────────────────────────╯

Executing tool get_weather...
  └── [SUCCESS] Weather retrieved
Executing tool get_weather...
  └── [FAILURE] SERVICE_UNAVAILABLE
──────────────────────────────────────────── ROUND 2 ────────────────────────────────────────────
╭───────────────────────────────────────── Model Input ─────────────────────────────────────────╮
│                                                                                               │
│  SYSTEM: You are a helpful weather assistant.                                                 │
│  ───────────────────────────────────────────────────────────────────────────────────────────  │
│  USER: What is the current weather in Tokyo and London?                                       │
│  ───────────────────────────────────────────────────────────────────────────────────────────  │
│  ASSISTANT: [CALLING TOOL] get_weather({'city': 'Tokyo'}) [CALLING TOOL]                      │
│  get_weather({'city':                                                                         │
│             'London'})                                                                        │
│  ───────────────────────────────────────────────────────────────────────────────────────────  │
│  USER: [TOOL RESULT get_weather] {'city': 'Tokyo', 'temperature_c': 28, 'condition':          │
│        'Sunny', 'humidity_pct': 45} [TOOL RESULT get_weather] {'error':                       │
│        'SERVICE_UNAVAILABLE', 'http_status': 503, 'detail': "Upstream weather API             │
│        timed out for 'London'"}                                                               │
│                                                                                               │
╰───────────────────────────────────────────────────────────────────────────────────────────────╯

╭─────────────────────────────────────── Model Response ────────────────────────────────────────╮
│                                                                                               │
│  ASSISTANT: I'm sorry, but I encountered an error when trying to fetch the weather for        │
│  London.                                                                                      │
│             However, the current weather in Tokyo is Sunny with a temperature of              │
│             28°C and 45% humidity.                                                            │
│                                                                                               │
╰───────────────────────────────────────────────────────────────────────────────────────────────╯

-- Scenario B: With Explicit Guidance ---------------------
──────────────────────────────────────────── ROUND 1 ────────────────────────────────────────────
╭───────────────────────────────────────── Model Input ─────────────────────────────────────────╮
│                                                                                               │
│  SYSTEM: You are a helpful weather assistant. If a tool returns an error field, you MUST      │
│          report it explicitly: state code and details. Do not guess.                          │
│  ───────────────────────────────────────────────────────────────────────────────────────────  │
│  USER: What is the current weather in Tokyo and London?                                       │
│                                                                                               │
╰───────────────────────────────────────────────────────────────────────────────────────────────╯

Executing tool get_weather...
  └── [SUCCESS] Weather retrieved
──────────────────────────────────────────── ROUND 2 ────────────────────────────────────────────
╭───────────────────────────────────────── Model Input ─────────────────────────────────────────╮
│                                                                                               │
│  SYSTEM: You are a helpful weather assistant. If a tool returns an error field, you MUST      │
│          report it explicitly: state code and details. Do not guess.                          │
│  ───────────────────────────────────────────────────────────────────────────────────────────  │
│  USER: What is the current weather in Tokyo and London?                                       │
│  ───────────────────────────────────────────────────────────────────────────────────────────  │
│  ASSISTANT: [CALLING TOOL] get_weather({'city': 'Tokyo'})                                     │
│  ───────────────────────────────────────────────────────────────────────────────────────────  │
│  USER: [TOOL RESULT get_weather] {'city': 'Tokyo', 'temperature_c': 28, 'condition':          │
│        'Sunny', 'humidity_pct': 45}                                                           │
│                                                                                               │
╰───────────────────────────────────────────────────────────────────────────────────────────────╯

Executing tool get_weather...
  └── [FAILURE] SERVICE_UNAVAILABLE
──────────────────────────────────────────── ROUND 3 ────────────────────────────────────────────
╭───────────────────────────────────────── Model Input ─────────────────────────────────────────╮
│                                                                                               │
│  SYSTEM: You are a helpful weather assistant. If a tool returns an error field, you MUST      │
│          report it explicitly: state code and details. Do not guess.                          │
│  ───────────────────────────────────────────────────────────────────────────────────────────  │
│  USER: What is the current weather in Tokyo and London?                                       │
│  ───────────────────────────────────────────────────────────────────────────────────────────  │
│  ASSISTANT: [CALLING TOOL] get_weather({'city': 'Tokyo'})                                     │
│  ───────────────────────────────────────────────────────────────────────────────────────────  │
│  USER: [TOOL RESULT get_weather] {'city': 'Tokyo', 'temperature_c': 28, 'condition':          │
│        'Sunny', 'humidity_pct': 45}                                                           │
│  ───────────────────────────────────────────────────────────────────────────────────────────  │
│  ASSISTANT: [CALLING TOOL] get_weather({'city': 'London'})                                    │
│  ───────────────────────────────────────────────────────────────────────────────────────────  │
│  USER: [TOOL RESULT get_weather] {'error': 'SERVICE_UNAVAILABLE', 'http_status': 503,         │
│        'detail': "Upstream weather API timed out for 'London'"}                               │
│                                                                                               │
╰───────────────────────────────────────────────────────────────────────────────────────────────╯

╭─────────────────────────────────────── Model Response ────────────────────────────────────────╮
│                                                                                               │
│  ASSISTANT: The weather in Tokyo is Sunny with a temperature of 28°C and 45% humidity. I      │
│  could                                                                                        │
│             not retrieve the weather for London due to a 'SERVICE_UNAVAILABLE'                │
│             error: Upstream weather API timed out for 'London'.                               │
│                                                                                               │
╰───────────────────────────────────────────────────────────────────────────────────────────────╯

-- Scenario C: Irrelevant Prompt --------------------------
──────────────────────────────────────────── ROUND 1 ────────────────────────────────────────────
╭───────────────────────────────────────── Model Input ─────────────────────────────────────────╮
│                                                                                               │
│  SYSTEM: You are a helpful weather assistant.                                                 │
│  ───────────────────────────────────────────────────────────────────────────────────────────  │
│  USER: Can you write a short haiku about a cat?                                               │
│                                                                                               │
╰───────────────────────────────────────────────────────────────────────────────────────────────╯

╭─────────────────────────────────────── Model Response ────────────────────────────────────────╮
│                                                                                               │
│  ASSISTANT: Soft fur, a gentle purr, Warmth on a sunlit sill, Dreaming, world at peace.       │
│                                                                                               │
╰───────────────────────────────────────────────────────────────────────────────────────────────╯

──────────────────────────────────────── Overall Summary ────────────────────────────────────────

                                 Injection Test Results                                 
┏━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━┓
┃ Scenario                 ┃ Rounds ┃           Success Rate           ┃ Reported 503? ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━┩
│ Scenario A               │   2    │ XXXXXXXXXX..........  1/2  (50%) │      NO       │
├──────────────────────────┼────────┼──────────────────────────────────┼───────────────┤
│ Scenario B               │   3    │ XXXXXXXXXX..........  1/2  (50%) │      YES      │
├──────────────────────────┼────────┼──────────────────────────────────┼───────────────┤
│ Scenario C               │   1    │          N/A (0 calls)           │      NO       │
└──────────────────────────┴────────┴──────────────────────────────────┴───────────────┘
