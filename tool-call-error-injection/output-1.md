╭───────────────────────────────────────────────────────────╮
│ Tool Call Error Injection & Handling                      │
│ Demonstrating model transparency when upstream APIs fail. │
│ 2 scenarios × 1 tool × 2 cities                           │
╰───────────────────────────────────────────────────────────╯

-- Scenario A: No Error Guidance --------------------------
───────────────────────────────────────────────── ROUND 1 ─────────────────────────────────────────────────
Current Conversation History ──────────────────────────────────────────────────────────────────────────────

> USER
  Message: What is the current weather in Tokyo and London?

asking llm...
Raw tool call part from model:
FunctionCall(id=None, args={'city': 'Tokyo'}, name='get_weather', partial_args=None, will_continue=None)
Executing tool get_weather with {'city': 'Tokyo'}...
  └── [SUCCESS] Weather retrieved
Raw tool call part from model:
FunctionCall(id=None, args={'city': 'London'}, name='get_weather', partial_args=None, will_continue=None)
Executing tool get_weather with {'city': 'London'}...
  └── [FAILURE] SERVICE_UNAVAILABLE
───────────────────────────────────────────────── ROUND 2 ─────────────────────────────────────────────────
Current Conversation History ──────────────────────────────────────────────────────────────────────────────

> USER
  Message: What is the current weather in Tokyo and London?

> MODEL
  Action: CALLING TOOL: get_weather({'city': 'Tokyo'})

> MODEL
  Action: CALLING TOOL: get_weather({'city': 'London'})

> USER
  Result (get_weather): {'city': 'Tokyo', 'temperature_c': 28, 'condition': 'Sunny', 'humidity_pct': 45}

> USER
  Result (get_weather): {'error': 'SERVICE_UNAVAILABLE', 'http_status': 503, 'detail': "Upstream weather 
API timed out for 'London'"}

asking llm...

-- Final Response --------------------------------------
  The current weather in Tokyo is Sunny with a temperature of 28°C and 45% humidity. I'm
  sorry, but I couldn't retrieve the weather for London. The weather API timed out.

-- Scenario B: With Explicit Guidance ---------------------
───────────────────────────────────────────────── ROUND 1 ─────────────────────────────────────────────────
Current Conversation History ──────────────────────────────────────────────────────────────────────────────

> USER
  Message: What is the current weather in Tokyo and London?

asking llm...
Raw tool call part from model:
FunctionCall(id=None, args={'city': 'Tokyo'}, name='get_weather', partial_args=None, will_continue=None)
Executing tool get_weather with {'city': 'Tokyo'}...
  └── [SUCCESS] Weather retrieved
Raw tool call part from model:
FunctionCall(id=None, args={'city': 'London'}, name='get_weather', partial_args=None, will_continue=None)
Executing tool get_weather with {'city': 'London'}...
  └── [FAILURE] SERVICE_UNAVAILABLE
───────────────────────────────────────────────── ROUND 2 ─────────────────────────────────────────────────
Current Conversation History ──────────────────────────────────────────────────────────────────────────────

> USER
  Message: What is the current weather in Tokyo and London?

> MODEL
  Action: CALLING TOOL: get_weather({'city': 'Tokyo'})

> MODEL
  Action: CALLING TOOL: get_weather({'city': 'London'})

> USER
  Result (get_weather): {'city': 'Tokyo', 'temperature_c': 28, 'condition': 'Sunny', 'humidity_pct': 45}

> USER
  Result (get_weather): {'error': 'SERVICE_UNAVAILABLE', 'http_status': 503, 'detail': "Upstream weather 
API timed out for 'London'"}

asking llm...

-- Final Response --------------------------------------
  The current weather in Tokyo is Sunny with a temperature of 28°C and humidity of 45%.
  There was an error retrieving the weather for London. The error code was
  `SERVICE_UNAVAILABLE` and the detail was "Upstream weather API timed out for
  'London'".

───────────────────────────────────────────── Overall Summary ─────────────────────────────────────────────
                                 Injection Test Results                                  
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━┓
┃ Scenario                  ┃ Rounds ┃                     Success Rate ┃ Reported 503? ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━┩
│ Scenario A                │   2    │ XXXXXXXXXX..........  1/2  (50%) │      NO       │
├───────────────────────────┼────────┼──────────────────────────────────┼───────────────┤
│ Scenario B                │   2    │ XXXXXXXXXX..........  1/2  (50%) │      YES      │
└───────────────────────────┴────────┴──────────────────────────────────┴───────────────┘

