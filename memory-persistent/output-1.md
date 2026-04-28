╭─────────────────────────────────────────────────────────────╮
│ Memory That Persists Across Sessions                        │
│ Ephemeral in-context memory vs. persistent external memory. │
│ 2 agents × 2 sessions × 3 turns each                        │
╰─────────────────────────────────────────────────────────────╯

────────────────────────────────── Part 1 — No-Memory Agent ───────────────────────────────────
  In-context history only. Each session starts with an empty messages list.

───────────────────────────────── Session 1  ·  sharing facts ─────────────────────────────────

╭──────────────────────────────────────── Model Input ────────────────────────────────────────╮
│                                                                                             │
│  SYSTEM: You are a helpful assistant. Answer only from what has been shared in this         │
│          conversation. If you don't know something, say so clearly.                         │
│  ─────────────────────────────────────────────────────────────────────────────────────────  │
│  USER: Hi! My name is Alex. I'm a backend engineer at a fintech startup.                    │
│                                                                                             │
╰─────────────────────────────────────────────────────────────────────────────────────────────╯
╭────────────────────────────────────── Model Response ───────────────────────────────────────╮
│                                                                                             │
│  ASSISTANT: Hi Alex! It's good to meet you. You're a backend engineer at a fintech          │
│  startup.                                                                                   │
│                                                                                             │
╰─────────────────────────────────────────────────────────────────────────────────────────────╯


> Turn 1
  user: Hi! My name is Alex. I'm a backend engineer at a fintech startup.
  assistant: Hi Alex! It's good to meet you. You're a backend engineer at a fintech startup.

╭──────────────────────────────────────── Model Input ────────────────────────────────────────╮
│                                                                                             │
│  SYSTEM: You are a helpful assistant. Answer only from what has been shared in this         │
│          conversation. If you don't know something, say so clearly.                         │
│  ─────────────────────────────────────────────────────────────────────────────────────────  │
│  USER: Hi! My name is Alex. I'm a backend engineer at a fintech startup.                    │
│  ─────────────────────────────────────────────────────────────────────────────────────────  │
│  ASSISTANT: Hi Alex! It's good to meet you. You're a backend engineer at a fintech          │
│  startup.                                                                                   │
│  ─────────────────────────────────────────────────────────────────────────────────────────  │
│  USER: I mostly work in Python, but I've been exploring Rust lately for performance-        │
│        critical parts.                                                                      │
│                                                                                             │
╰─────────────────────────────────────────────────────────────────────────────────────────────╯
╭────────────────────────────────────── Model Response ───────────────────────────────────────╮
│                                                                                             │
│  ASSISTANT: That's interesting, Alex. So you primarily work with Python, but you're also    │
│             exploring Rust for performance-critical components.                             │
│                                                                                             │
╰─────────────────────────────────────────────────────────────────────────────────────────────╯


> Turn 2
  user: I mostly work in Python, but I've been exploring Rust lately for performance-critical
         parts.
  assistant: That's interesting, Alex. So you primarily work with Python, but you're also 
exploring
         Rust for performance-critical components.

╭──────────────────────────────────────── Model Input ────────────────────────────────────────╮
│                                                                                             │
│  SYSTEM: You are a helpful assistant. Answer only from what has been shared in this         │
│          conversation. If you don't know something, say so clearly.                         │
│  ─────────────────────────────────────────────────────────────────────────────────────────  │
│  USER: Hi! My name is Alex. I'm a backend engineer at a fintech startup.                    │
│  ─────────────────────────────────────────────────────────────────────────────────────────  │
│  ASSISTANT: Hi Alex! It's good to meet you. You're a backend engineer at a fintech          │
│  startup.                                                                                   │
│  ─────────────────────────────────────────────────────────────────────────────────────────  │
│  USER: I mostly work in Python, but I've been exploring Rust lately for performance-        │
│        critical parts.                                                                      │
│  ─────────────────────────────────────────────────────────────────────────────────────────  │
│  ASSISTANT: That's interesting, Alex. So you primarily work with Python, but you're also    │
│             exploring Rust for performance-critical components.                             │
│  ─────────────────────────────────────────────────────────────────────────────────────────  │
│  USER: I'm currently building a real-time fraud detection system that needs to handle 10k   │
│        transactions per second.                                                             │
│                                                                                             │
╰─────────────────────────────────────────────────────────────────────────────────────────────╯
╭────────────────────────────────────── Model Response ───────────────────────────────────────╮
│                                                                                             │
│  ASSISTANT: Wow, that's a significant challenge, Alex. You're building a real-time fraud    │
│             detection system that needs to handle 10,000 transactions per second.           │
│             That definitely sounds like a scenario where Rust could be very                 │
│             beneficial for performance.                                                     │
│                                                                                             │
╰─────────────────────────────────────────────────────────────────────────────────────────────╯


> Turn 3
  user: I'm currently building a real-time fraud detection system that needs to handle 10k
         transactions per second.
  assistant: Wow, that's a significant challenge, Alex. You're building a real-time fraud 
detection
         system that needs to handle 10,000 transactions per second. That definitely
         sounds like a scenario where Rust could be very beneficial for performance.

─────────────────── Session 2  ·  testing recall  (new session, no history) ───────────────────

╭──────────────────────────────────────── Model Input ────────────────────────────────────────╮
│                                                                                             │
│  SYSTEM: You are a helpful assistant. Answer only from what has been shared in this         │
│          conversation. If you don't know something, say so clearly.                         │
│  ─────────────────────────────────────────────────────────────────────────────────────────  │
│  USER: What's my name and what do I do for work?                                            │
│                                                                                             │
╰─────────────────────────────────────────────────────────────────────────────────────────────╯
╭────────────────────────────────────── Model Response ───────────────────────────────────────╮
│                                                                                             │
│  ASSISTANT: I don't know your name or what you do for work, as that information has not     │
│  been                                                                                       │
│             shared in this conversation.                                                    │
│                                                                                             │
╰─────────────────────────────────────────────────────────────────────────────────────────────╯


> Turn 1
  user: What's my name and what do I do for work?
  assistant: I don't know your name or what you do for work, as that information has not been 
shared
         in this conversation.

╭──────────────────────────────────────── Model Input ────────────────────────────────────────╮
│                                                                                             │
│  SYSTEM: You are a helpful assistant. Answer only from what has been shared in this         │
│          conversation. If you don't know something, say so clearly.                         │
│  ─────────────────────────────────────────────────────────────────────────────────────────  │
│  USER: What's my name and what do I do for work?                                            │
│  ─────────────────────────────────────────────────────────────────────────────────────────  │
│  ASSISTANT: I don't know your name or what you do for work, as that information has not     │
│  been                                                                                       │
│             shared in this conversation.                                                    │
│  ─────────────────────────────────────────────────────────────────────────────────────────  │
│  USER: What programming languages do I work with?                                           │
│                                                                                             │
╰─────────────────────────────────────────────────────────────────────────────────────────────╯
╭────────────────────────────────────── Model Response ───────────────────────────────────────╮
│                                                                                             │
│  ASSISTANT: I don't know what programming languages you work with, as that information has  │
│  not                                                                                        │
│             been shared in this conversation.                                               │
│                                                                                             │
╰─────────────────────────────────────────────────────────────────────────────────────────────╯


> Turn 2
  user: What programming languages do I work with?
  assistant: I don't know what programming languages you work with, as that information has not
been
         shared in this conversation.

╭──────────────────────────────────────── Model Input ────────────────────────────────────────╮
│                                                                                             │
│  SYSTEM: You are a helpful assistant. Answer only from what has been shared in this         │
│          conversation. If you don't know something, say so clearly.                         │
│  ─────────────────────────────────────────────────────────────────────────────────────────  │
│  USER: What's my name and what do I do for work?                                            │
│  ─────────────────────────────────────────────────────────────────────────────────────────  │
│  ASSISTANT: I don't know your name or what you do for work, as that information has not     │
│  been                                                                                       │
│             shared in this conversation.                                                    │
│  ─────────────────────────────────────────────────────────────────────────────────────────  │
│  USER: What programming languages do I work with?                                           │
│  ─────────────────────────────────────────────────────────────────────────────────────────  │
│  ASSISTANT: I don't know what programming languages you work with, as that information has  │
│  not                                                                                        │
│             been shared in this conversation.                                               │
│  ─────────────────────────────────────────────────────────────────────────────────────────  │
│  USER: What project am I building and what are its performance requirements?                │
│                                                                                             │
╰─────────────────────────────────────────────────────────────────────────────────────────────╯
╭────────────────────────────────────── Model Response ───────────────────────────────────────╮
│                                                                                             │
│  ASSISTANT: I don't know what project you are building or its performance requirements, as  │
│             that information has not been shared in this conversation.                      │
│                                                                                             │
╰─────────────────────────────────────────────────────────────────────────────────────────────╯


> Turn 3
  user: What project am I building and what are its performance requirements?
  assistant: I don't know what project you are building or its performance requirements, as 
that
         information has not been shared in this conversation.


─────────────────────────────── Part 2 — External Memory Agent ────────────────────────────────
  Writes facts to disk after each turn (Session 1). Retrieves by keyword at each turn start.

──────────────────────── Session 1  ·  sharing facts + writing memory ─────────────────────────


> Turn 1 (0 retrieved / 0 total in memory)
╭──────────────────────────────────────── Model Input ────────────────────────────────────────╮
│                                                                                             │
│  SYSTEM: You are a helpful assistant. Answer from the conversation history and any facts    │
│          provided below. If you don't know something, say so clearly.                       │
│  ─────────────────────────────────────────────────────────────────────────────────────────  │
│  USER: Hi! My name is Alex. I'm a backend engineer at a fintech startup.                    │
│                                                                                             │
╰─────────────────────────────────────────────────────────────────────────────────────────────╯
╭────────────────────────────────────── Model Response ───────────────────────────────────────╮
│                                                                                             │
│  ASSISTANT: Hi Alex! It's great to meet you. Backend engineering at a fintech startup       │
│  sounds                                                                                     │
│             like a very interesting field. What kind of work do you typically do            │
│             there?                                                                          │
│                                                                                             │
╰─────────────────────────────────────────────────────────────────────────────────────────────╯

  user: Hi! My name is Alex. I'm a backend engineer at a fintech startup.
  assistant: Hi Alex! It's great to meet you. Backend engineering at a fintech startup sounds 
like a
         very interesting field. What kind of work do you typically do there?
╭──────────────────────────────────────── Model Input ────────────────────────────────────────╮
│                                                                                             │
│  USER: You are a memory extraction system. Given a conversation turn, extract factual       │
│        statements about the user as a JSON array. Each object must have exactly two         │
│        keys:   "keywords": list of 2-5 lowercase words to use when searching for            │
│        this fact   "fact":     one concise sentence stating the fact  Conversation:         │
│        User: Hi! My name is Alex. I'm a backend engineer at a fintech startup.              │
│        Assistant: Hi Alex! It's great to meet you. Backend engineering at a fintech         │
│        startup sounds like a very interesting field. What kind of work do you               │
│        typically do there?  Return only valid JSON with no markdown fences.                 │
│        Example: [{"keywords": ["name", "user"], "fact": "The user's name is                 │
│        Alex."}]                                                                             │
│                                                                                             │
╰─────────────────────────────────────────────────────────────────────────────────────────────╯
╭────────────────────────────────────── Model Response ───────────────────────────────────────╮
│                                                                                             │
│  ASSISTANT: [   {     "keywords": ["name", "alex", "user"],     "fact": "The user's name    │
│  is                                                                                         │
│             Alex."   },   {     "keywords": ["backend", "engineer", "fintech",              │
│             "startup", "job"],     "fact": "The user is a backend engineer at a             │
│             fintech startup."   } ]                                                         │
│                                                                                             │
╰─────────────────────────────────────────────────────────────────────────────────────────────╯

    wrote  → 2 total entries now in memory_store.json


> Turn 2 (0 retrieved / 2 total in memory)
╭──────────────────────────────────────── Model Input ────────────────────────────────────────╮
│                                                                                             │
│  SYSTEM: You are a helpful assistant. Answer from the conversation history and any facts    │
│          provided below. If you don't know something, say so clearly.                       │
│  ─────────────────────────────────────────────────────────────────────────────────────────  │
│  USER: Hi! My name is Alex. I'm a backend engineer at a fintech startup.                    │
│  ─────────────────────────────────────────────────────────────────────────────────────────  │
│  ASSISTANT: Hi Alex! It's great to meet you. Backend engineering at a fintech startup       │
│  sounds                                                                                     │
│             like a very interesting field. What kind of work do you typically do            │
│             there?                                                                          │
│  ─────────────────────────────────────────────────────────────────────────────────────────  │
│  USER: I mostly work in Python, but I've been exploring Rust lately for performance-        │
│        critical parts.                                                                      │
│                                                                                             │
╰─────────────────────────────────────────────────────────────────────────────────────────────╯
╭────────────────────────────────────── Model Response ───────────────────────────────────────╮
│                                                                                             │
│  ASSISTANT: That's a fantastic combination! Python is excellent for rapid development and   │
│  its                                                                                        │
│             rich ecosystem, while Rust offers unparalleled performance and safety           │
│             guarantees, which are crucial in fintech.  What kind of performance-            │
│             critical parts are you looking to optimize with Rust? Are there                 │
│             specific bottlenecks you're trying to address?                                  │
│                                                                                             │
╰─────────────────────────────────────────────────────────────────────────────────────────────╯

  user: I mostly work in Python, but I've been exploring Rust lately for performance-critical
         parts.
  assistant: That's a fantastic combination! Python is excellent for rapid development and its 
rich
         ecosystem, while Rust offers unparalleled performance and safety guarantees,
         which are crucial in fintech.  What kind of performance-critical parts are you
         looking to optimize with Rust? Are there specific bottlenecks you're trying to
         address?
╭──────────────────────────────────────── Model Input ────────────────────────────────────────╮
│                                                                                             │
│  USER: You are a memory extraction system. Given a conversation turn, extract factual       │
│        statements about the user as a JSON array. Each object must have exactly two         │
│        keys:   "keywords": list of 2-5 lowercase words to use when searching for            │
│        this fact   "fact":     one concise sentence stating the fact  Conversation:         │
│        User: I mostly work in Python, but I've been exploring Rust lately for               │
│        performance-critical parts. Assistant: That's a fantastic combination!               │
│        Python is excellent for rapid development and its rich ecosystem, while Rust         │
│        offers unparalleled performance and safety guarantees, which are crucial in          │
│        fintech.  What kind of performance-critical parts are you looking to                 │
│        optimize with Rust? Are there specific bottlenecks you're trying to address?         │
│        Return only valid JSON with no markdown fences. Example: [{"keywords":               │
│        ["name", "user"], "fact": "The user's name is Alex."}]                               │
│                                                                                             │
╰─────────────────────────────────────────────────────────────────────────────────────────────╯
╭────────────────────────────────────── Model Response ───────────────────────────────────────╮
│                                                                                             │
│  ASSISTANT: [   {     "keywords": ["user", "works", "python", "mostly"],     "fact": "The   │
│  user                                                                                       │
│             mostly works in Python."   },   {     "keywords": ["user", "exploring",         │
│             "rust"],     "fact": "The user has been exploring Rust."   },   {               │
│             "keywords": ["user", "exploring", "rust", "performance", "critical"],           │
│             "fact": "The user is exploring Rust for performance-critical parts."            │
│             } ]                                                                             │
│                                                                                             │
╰─────────────────────────────────────────────────────────────────────────────────────────────╯

    wrote  → 5 total entries now in memory_store.json


> Turn 3 (0 retrieved / 5 total in memory)
╭──────────────────────────────────────── Model Input ────────────────────────────────────────╮
│                                                                                             │
│  SYSTEM: You are a helpful assistant. Answer from the conversation history and any facts    │
│          provided below. If you don't know something, say so clearly.                       │
│  ─────────────────────────────────────────────────────────────────────────────────────────  │
│  USER: Hi! My name is Alex. I'm a backend engineer at a fintech startup.                    │
│  ─────────────────────────────────────────────────────────────────────────────────────────  │
│  ASSISTANT: Hi Alex! It's great to meet you. Backend engineering at a fintech startup       │
│  sounds                                                                                     │
│             like a very interesting field. What kind of work do you typically do            │
│             there?                                                                          │
│  ─────────────────────────────────────────────────────────────────────────────────────────  │
│  USER: I mostly work in Python, but I've been exploring Rust lately for performance-        │
│        critical parts.                                                                      │
│  ─────────────────────────────────────────────────────────────────────────────────────────  │
│  ASSISTANT: That's a fantastic combination! Python is excellent for rapid development and   │
│  its                                                                                        │
│             rich ecosystem, while Rust offers unparalleled performance and safety           │
│             guarantees, which are crucial in fintech.  What kind of performance-            │
│             critical parts are you looking to optimize with Rust? Are there                 │
│             specific bottlenecks you're trying to address?                                  │
│  ─────────────────────────────────────────────────────────────────────────────────────────  │
│  USER: I'm currently building a real-time fraud detection system that needs to handle 10k   │
│        transactions per second.                                                             │
│                                                                                             │
╰─────────────────────────────────────────────────────────────────────────────────────────────╯
╭────────────────────────────────────── Model Response ───────────────────────────────────────╮
│                                                                                             │
│  ASSISTANT: Wow, 10,000 transactions per second for real-time fraud detection is a serious  │
│             performance requirement! That definitely puts Rust in its element.  For         │
│             a system like that, every millisecond counts, not just for throughput           │
│             but also for minimizing false positives and negatives by processing             │
│             data as quickly as possible. Rust's ability to provide predictable              │
│             performance, low-level control, and memory safety without a garbage             │
│             collector makes it an excellent choice for the core processing engine.          │
│             Are you looking at using Rust for the entire transaction processing             │
│             pipeline, or more for specific, compute-intensive modules within a              │
│             larger Python-orchestrated system?                                              │
│                                                                                             │
╰─────────────────────────────────────────────────────────────────────────────────────────────╯

  user: I'm currently building a real-time fraud detection system that needs to handle 10k
         transactions per second.
  assistant: Wow, 10,000 transactions per second for real-time fraud detection is a serious
         performance requirement! That definitely puts Rust in its element.  For a
         system like that, every millisecond counts, not just for throughput but also
         for minimizing false positives and negatives by processing data as quickly as
         possible. Rust's ability to provide predictable performance, low-level control,
         and memory safety without a garbage collector makes it an excellent choice for
         the core processing engine.  Are you looking at using Rust for the entire
         transaction processing pipeline, or more for specific, compute-intensive
         modules within a larger Python-orchestrated system?
╭──────────────────────────────────────── Model Input ────────────────────────────────────────╮
│                                                                                             │
│  USER: You are a memory extraction system. Given a conversation turn, extract factual       │
│        statements about the user as a JSON array. Each object must have exactly two         │
│        keys:   "keywords": list of 2-5 lowercase words to use when searching for            │
│        this fact   "fact":     one concise sentence stating the fact  Conversation:         │
│        User: I'm currently building a real-time fraud detection system that needs           │
│        to handle 10k transactions per second. Assistant: Wow, 10,000 transactions           │
│        per second for real-time fraud detection is a serious performance                    │
│        requirement! That definitely puts Rust in its element.  For a system like            │
│        that, every millisecond counts, not just for throughput but also for                 │
│        minimizing false positives and negatives by processing data as quickly as            │
│        possible. Rust's ability to provide predictable performance, low-level               │
│        control, and memory safety without a garbage collector makes it an excellent         │
│        choice for the core processing engine.  Are you looking at using Rust for            │
│        the entire transaction processing pipeline, or more for specific, compute-           │
│        intensive modules within a larger Python-orchestrated system?  Return only           │
│        valid JSON with no markdown fences. Example: [{"keywords": ["name", "user"],         │
│        "fact": "The user's name is Alex."}]                                                 │
│                                                                                             │
╰─────────────────────────────────────────────────────────────────────────────────────────────╯
╭────────────────────────────────────── Model Response ───────────────────────────────────────╮
│                                                                                             │
│  ASSISTANT: [{"keywords": ["building", "fraud detection", "system", "real-time"], "fact":   │
│  "The                                                                                       │
│             user is building a real-time fraud detection system."}, {"keywords":            │
│             ["transactions", "per second", "10k", "performance"], "fact": "The              │
│             user's system needs to handle 10,000 transactions per second."}]                │
│                                                                                             │
╰─────────────────────────────────────────────────────────────────────────────────────────────╯

    wrote  → 7 total entries now in memory_store.json

────────────────────── Session 2  ·  new context, reads from memory file ──────────────────────


> Turn 1 (2 retrieved / 7 total in memory)
    recall → The user's name is Alex.
    recall → The user mostly works in Python.
╭──────────────────────────────────────── Model Input ────────────────────────────────────────╮
│                                                                                             │
│  SYSTEM: You are a helpful assistant. Answer from the conversation history and any facts    │
│          provided below. If you don't know something, say so clearly.  Facts                │
│          retrieved from memory: - The user's name is Alex. - The user mostly works          │
│          in Python.                                                                         │
│  ─────────────────────────────────────────────────────────────────────────────────────────  │
│  USER: What's my name and what do I do for work?                                            │
│                                                                                             │
╰─────────────────────────────────────────────────────────────────────────────────────────────╯
╭────────────────────────────────────── Model Response ───────────────────────────────────────╮
│                                                                                             │
│  ASSISTANT: Your name is Alex and you mostly work in Python.                                │
│                                                                                             │
╰─────────────────────────────────────────────────────────────────────────────────────────────╯

  user: What's my name and what do I do for work?
  assistant: Your name is Alex and you mostly work in Python.


> Turn 2 (1 retrieved / 7 total in memory)
    recall → The user mostly works in Python.
╭──────────────────────────────────────── Model Input ────────────────────────────────────────╮
│                                                                                             │
│  SYSTEM: You are a helpful assistant. Answer from the conversation history and any facts    │
│          provided below. If you don't know something, say so clearly.  Facts                │
│          retrieved from memory: - The user mostly works in Python.                          │
│  ─────────────────────────────────────────────────────────────────────────────────────────  │
│  USER: What's my name and what do I do for work?                                            │
│  ─────────────────────────────────────────────────────────────────────────────────────────  │
│  ASSISTANT: Your name is Alex and you mostly work in Python.                                │
│  ─────────────────────────────────────────────────────────────────────────────────────────  │
│  USER: What programming languages do I work with?                                           │
│                                                                                             │
╰─────────────────────────────────────────────────────────────────────────────────────────────╯
╭────────────────────────────────────── Model Response ───────────────────────────────────────╮
│                                                                                             │
│  ASSISTANT: You mostly work in Python.                                                      │
│                                                                                             │
╰─────────────────────────────────────────────────────────────────────────────────────────────╯

  user: What programming languages do I work with?
  assistant: You mostly work in Python.


> Turn 3 (3 retrieved / 7 total in memory)
    recall → The user is exploring Rust for performance-critical parts.
    recall → The user is building a real-time fraud detection system.
    recall → The user's system needs to handle 10,000 transactions per second.
╭──────────────────────────────────────── Model Input ────────────────────────────────────────╮
│                                                                                             │
│  SYSTEM: You are a helpful assistant. Answer from the conversation history and any facts    │
│          provided below. If you don't know something, say so clearly.  Facts                │
│          retrieved from memory: - The user is exploring Rust for performance-               │
│          critical parts. - The user is building a real-time fraud detection system.         │
│          - The user's system needs to handle 10,000 transactions per second.                │
│  ─────────────────────────────────────────────────────────────────────────────────────────  │
│  USER: What's my name and what do I do for work?                                            │
│  ─────────────────────────────────────────────────────────────────────────────────────────  │
│  ASSISTANT: Your name is Alex and you mostly work in Python.                                │
│  ─────────────────────────────────────────────────────────────────────────────────────────  │
│  USER: What programming languages do I work with?                                           │
│  ─────────────────────────────────────────────────────────────────────────────────────────  │
│  ASSISTANT: You mostly work in Python.                                                      │
│  ─────────────────────────────────────────────────────────────────────────────────────────  │
│  USER: What project am I building and what are its performance requirements?                │
│                                                                                             │
╰─────────────────────────────────────────────────────────────────────────────────────────────╯
╭────────────────────────────────────── Model Response ───────────────────────────────────────╮
│                                                                                             │
│  ASSISTANT: You are building a real-time fraud detection system that needs to handle        │
│  10,000                                                                                     │
│             transactions per second.                                                        │
│                                                                                             │
╰─────────────────────────────────────────────────────────────────────────────────────────────╯

  user: What project am I building and what are its performance requirements?
  assistant: You are building a real-time fraud detection system that needs to handle 10,000
         transactions per second.


───────────────────────────────── Verdict — Session 2 Recall ──────────────────────────────────

                                                  Results                                      
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━
┃ Question                           ┃ No-Memory Agent                  ┃ Memory Agent         
┡━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━
│ What's my name and what do I do    │ I don't know your name or what   │ Your name is Alex and
│ for work?                          │ you do for work, as that         │ mostly work in Python
│                                    │ information has not been         │                      
│                                    │ shared in this conversation.     │                      
├────────────────────────────────────┼──────────────────────────────────┼──────────────────────
│ What programming languages do I    │ I don't know what programming    │ You mostly work in Py
│ work with?                         │ languages you work with, as      │                      
│                                    │ that information has not been    │                      
│                                    │ shared in this conversation.     │                      
├────────────────────────────────────┼──────────────────────────────────┼──────────────────────
│ What project am I building and     │ I don't know what project you    │ You are building a re
│ what are its performance           │ are building or its              │ fraud detection syste
│ requirements?                      │ performance requirements, as     │ needs to handle 10,00
│                                    │ that information has not been    │ transactions per seco
│                                    │ shared in this conversation.     │                      
└────────────────────────────────────┴──────────────────────────────────┴──────────────────────

──────────────────────────────────────────── Stats ────────────────────────────────────────────

  Session 1 turns:          3
  Session 2 turns:          3
  Memory file:              memory_store.json
  Facts stored after S1:    7 entries

  No-memory agent S2:  0 facts retained — blank slate
  Memory agent S2:      7 facts available — persisted via file

  Takeaway: in-context memory is ephemeral. External memory requires an explicit write + 
retrieval strategy, but it survives across sessions.

