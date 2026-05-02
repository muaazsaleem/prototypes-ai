╭────────────────────────────────────────────────────────────────╮
│ Prompting Strategy Benchmark                                   │
│ Comparing Direct, Zero-Shot CoT, and Few-Shot CoT performance. │
│ Model: gemini-2.5-flash | Questions: 5                         │
╰────────────────────────────────────────────────────────────────╯

-- Direct --------------------------------------
╭───────────────────────────────────────── Model Input ──────────────────────────────────────────╮
│                                                                                                │
│  USER: Answer the following question directly with just the final answer: Sally has 3          │
│        brothers. Each brother has 2 sisters. How many sisters does Sally have?                 │
│                                                                                                │
╰────────────────────────────────────────────────────────────────────────────────────────────────╯
╭──────────────────────────────────────── Model Response ────────────────────────────────────────╮
│                                                                                                │
│  ASSISTANT: 2                                                                                  │
│                                                                                                │
╰────────────────────────────────────────────────────────────────────────────────────────────────╯
  Run #01: x  3.1s | 33 tokens

╭───────────────────────────────────────── Model Input ──────────────────────────────────────────╮
│                                                                                                │
│  USER: Answer the following question directly with just the final answer: A bat and a          │
│        ball cost $1.10 in total. The bat costs $1.00 more than the ball. How much              │
│        does the ball cost? (Answer in dollars, e.g., 0.05)                                     │
│                                                                                                │
╰────────────────────────────────────────────────────────────────────────────────────────────────╯
╭──────────────────────────────────────── Model Response ────────────────────────────────────────╮
│                                                                                                │
│  ASSISTANT: 0.05                                                                               │
│                                                                                                │
╰────────────────────────────────────────────────────────────────────────────────────────────────╯
  Run #02: o  2.4s | 65 tokens

╭───────────────────────────────────────── Model Input ──────────────────────────────────────────╮
│                                                                                                │
│  USER: Answer the following question directly with just the final answer: A farmer has 17      │
│        sheep and all but 9 die. How many are left?                                             │
│                                                                                                │
╰────────────────────────────────────────────────────────────────────────────────────────────────╯
╭──────────────────────────────────────── Model Response ────────────────────────────────────────╮
│                                                                                                │
│  ASSISTANT: 9                                                                                  │
│                                                                                                │
╰────────────────────────────────────────────────────────────────────────────────────────────────╯
  Run #03: o  1.4s | 32 tokens

╭───────────────────────────────────────── Model Input ──────────────────────────────────────────╮
│                                                                                                │
│  USER: Answer the following question directly with just the final answer: In a race, if        │
│        you pass the person in second place, what place are you in?                             │
│                                                                                                │
╰────────────────────────────────────────────────────────────────────────────────────────────────╯
╭──────────────────────────────────────── Model Response ────────────────────────────────────────╮
│                                                                                                │
│  ASSISTANT: Second                                                                             │
│                                                                                                │
╰────────────────────────────────────────────────────────────────────────────────────────────────╯
  Run #04: o  2.1s | 32 tokens

╭───────────────────────────────────────── Model Input ──────────────────────────────────────────╮
│                                                                                                │
│  USER: Answer the following question directly with just the final answer: If it takes 5        │
│        machines 5 minutes to make 5 widgets, how long would it take 100 machines to            │
│        make 100 widgets? (Answer in minutes)                                                   │
│                                                                                                │
╰────────────────────────────────────────────────────────────────────────────────────────────────╯
╭──────────────────────────────────────── Model Response ────────────────────────────────────────╮
│                                                                                                │
│  ASSISTANT: 5                                                                                  │
│                                                                                                │
╰────────────────────────────────────────────────────────────────────────────────────────────────╯
  Run #05: o  3.8s | 51 tokens


-- Zero-Shot CoT --------------------------------------
╭───────────────────────────────────────── Model Input ──────────────────────────────────────────╮
│                                                                                                │
│  USER: Answer the following question. Think step-by-step and then provide the final            │
│        answer as 'Answer: <value>': Sally has 3 brothers. Each brother has 2                   │
│        sisters. How many sisters does Sally have?                                              │
│                                                                                                │
╰────────────────────────────────────────────────────────────────────────────────────────────────╯
╭──────────────────────────────────────── Model Response ────────────────────────────────────────╮
│                                                                                                │
│  ASSISTANT: Here's how to think step-by-step:  1.  **Sally's perspective:** Sally is a girl.   │
│             2.  **Brothers' perspective:** Each of Sally's 3 brothers has 2                    │
│             sisters. 3.  **Identify the sisters:** For any given brother, one of               │
│             his sisters is Sally herself. 4.  **The remaining sister(s):** If a                │
│             brother has 2 sisters, and one is Sally, then there must be exactly one            │
│             *other* sister in the family. This other sister is also a sister to                │
│             Sally. 5.  **Family structure:**     *   Sally (girl 1)     *   Sister             │
│             X (girl 2)     *   Brother 1     *   Brother 2     *   Brother 3     *             │
│             From any brother's point of view, he has Sally and Sister X as his                 │
│             sisters (2 sisters).     *   From Sally's point of view, she has Sister            │
│             X as her sister.  Answer: 1                                                        │
│                                                                                                │
╰────────────────────────────────────────────────────────────────────────────────────────────────╯
  Run #01: o  3.5s | 268 tokens

╭───────────────────────────────────────── Model Input ──────────────────────────────────────────╮
│                                                                                                │
│  USER: Answer the following question. Think step-by-step and then provide the final            │
│        answer as 'Answer: <value>': A bat and a ball cost $1.10 in total. The bat              │
│        costs $1.00 more than the ball. How much does the ball cost? (Answer in                 │
│        dollars, e.g., 0.05)                                                                    │
│                                                                                                │
╰────────────────────────────────────────────────────────────────────────────────────────────────╯
╭──────────────────────────────────────── Model Response ────────────────────────────────────────╮
│                                                                                                │
│  ASSISTANT: Let B be the cost of the bat and L be the cost of the ball.  From the problem      │
│             statement, we can form two equations: 1. The total cost of the bat and             │
│             the ball is $1.10:    B + L = 1.10  2. The bat costs $1.00 more than               │
│             the ball:    B = L + 1.00  Now we can use substitution to solve for L              │
│             (the cost of the ball). Substitute the second equation into the first              │
│             one: (L + 1.00) + L = 1.10  Combine the L terms: 2L + 1.00 = 1.10                  │
│             Subtract 1.00 from both sides of the equation: 2L = 1.10 - 1.00 2L =               │
│             0.10  Divide by 2 to find the cost of the ball: L = 0.10 / 2 L = 0.05              │
│             So, the ball costs $0.05.  To check: If the ball costs $0.05, then the             │
│             bat costs $0.05 + $1.00 = $1.05. The total cost would be $1.05 (bat) +             │
│             $0.05 (ball) = $1.10. This matches the given total.  The final answer              │
│             is $\boxed{\text{0.05}}$.                                                          │
│                                                                                                │
╰────────────────────────────────────────────────────────────────────────────────────────────────╯
  Run #02: o  4.1s | 396 tokens

╭───────────────────────────────────────── Model Input ──────────────────────────────────────────╮
│                                                                                                │
│  USER: Answer the following question. Think step-by-step and then provide the final            │
│        answer as 'Answer: <value>': A farmer has 17 sheep and all but 9 die. How               │
│        many are left?                                                                          │
│                                                                                                │
╰────────────────────────────────────────────────────────────────────────────────────────────────╯
╭──────────────────────────────────────── Model Response ────────────────────────────────────────╮
│                                                                                                │
│  ASSISTANT: A farmer has 17 sheep and all but 9 die. This means that 9 sheep did *not* die.    │
│             Therefore, the number of sheep left is 9.  Answer: 9                               │
│                                                                                                │
╰────────────────────────────────────────────────────────────────────────────────────────────────╯
  Run #03: o  2.3s | 88 tokens

╭───────────────────────────────────────── Model Input ──────────────────────────────────────────╮
│                                                                                                │
│  USER: Answer the following question. Think step-by-step and then provide the final            │
│        answer as 'Answer: <value>': In a race, if you pass the person in second                │
│        place, what place are you in?                                                           │
│                                                                                                │
╰────────────────────────────────────────────────────────────────────────────────────────────────╯
╭──────────────────────────────────────── Model Response ────────────────────────────────────────╮
│                                                                                                │
│  ASSISTANT: When you pass the person in second place, that person moves to third place, and    │
│             you take their spot.  Answer: Second place                                         │
│                                                                                                │
╰────────────────────────────────────────────────────────────────────────────────────────────────╯
  Run #04: o  1.9s | 72 tokens

╭───────────────────────────────────────── Model Input ──────────────────────────────────────────╮
│                                                                                                │
│  USER: Answer the following question. Think step-by-step and then provide the final            │
│        answer as 'Answer: <value>': If it takes 5 machines 5 minutes to make 5                 │
│        widgets, how long would it take 100 machines to make 100 widgets? (Answer in            │
│        minutes)                                                                                │
│                                                                                                │
╰────────────────────────────────────────────────────────────────────────────────────────────────╯
╭──────────────────────────────────────── Model Response ────────────────────────────────────────╮
│                                                                                                │
│  ASSISTANT: To solve this, let's break down the information:  1.  **Understand the initial     │
│             rate:** "5 machines 5 minutes to make 5 widgets."     This implies that            │
│             each machine is working on one widget.     Therefore, it takes **1                 │
│             machine 5 minutes to make 1 widget**. This is the fundamental rate.  2.            │
│             **Apply the rate to the new scenario:** "100 machines to make 100                  │
│             widgets."     Since we have 100 machines, and we need to make 100                  │
│             widgets, each machine can be assigned to make one widget.     As we                │
│             established, it takes 1 machine 5 minutes to make 1 widget.     If 100             │
│             machines are all working in parallel, each making one widget, they will            │
│             all finish their assigned widget at the same time.  Therefore, it will             │
│             still take 5 minutes.  The final answer is $\boxed{5}$                             │
│                                                                                                │
╰────────────────────────────────────────────────────────────────────────────────────────────────╯
  Run #05: o  4.1s | 265 tokens


-- Few-Shot CoT --------------------------------------
╭───────────────────────────────────────── Model Input ──────────────────────────────────────────╮
│                                                                                                │
│  USER: Answer the following question. Think step-by-step and then provide the final            │
│        answer as 'Answer: <value>'.   Example 1: Question: If I have 3 apples and I            │
│        give 2 to my friend, but then my friend gives me 1 back, how many apples do             │
│        I have? Thought:  1. Start with 3 apples. 2. Give 2 away: 3 - 2 = 1 apple               │
│        remaining. 3. Friend gives 1 back: 1 + 1 = 2 apples. Answer: 2  Example 2:              │
│        Question: How many legs does a spider have? Thought: 1. Spiders are                     │
│        arachnids. 2. Arachnids typically have 8 legs. Answer: 8  Example 3:                    │
│        Question: What is 15 * 4? Thought: 1. 15 * 2 is 30. 2. 30 * 2 is 60. Answer:            │
│        60   Question: Sally has 3 brothers. Each brother has 2 sisters. How many               │
│        sisters does Sally have?                                                                │
│                                                                                                │
╰────────────────────────────────────────────────────────────────────────────────────────────────╯
╭──────────────────────────────────────── Model Response ────────────────────────────────────────╮
│                                                                                                │
│  ASSISTANT: Thought: 1. The question states Sally has 3 brothers. 2. The question states       │
│  "Each                                                                                         │
│             brother has 2 sisters." 3. This means that the total number of sisters             │
│             in the family is 2. 4. Sally is one of those sisters. 5. If there are 2            │
│             sisters in total in the family, and Sally is one of them, then Sally               │
│             has 1 sister (the other sister).  Answer: 1                                        │
│                                                                                                │
╰────────────────────────────────────────────────────────────────────────────────────────────────╯
  Run #01: o  4.0s | 339 tokens

╭───────────────────────────────────────── Model Input ──────────────────────────────────────────╮
│                                                                                                │
│  USER: Answer the following question. Think step-by-step and then provide the final            │
│        answer as 'Answer: <value>'.   Example 1: Question: If I have 3 apples and I            │
│        give 2 to my friend, but then my friend gives me 1 back, how many apples do             │
│        I have? Thought:  1. Start with 3 apples. 2. Give 2 away: 3 - 2 = 1 apple               │
│        remaining. 3. Friend gives 1 back: 1 + 1 = 2 apples. Answer: 2  Example 2:              │
│        Question: How many legs does a spider have? Thought: 1. Spiders are                     │
│        arachnids. 2. Arachnids typically have 8 legs. Answer: 8  Example 3:                    │
│        Question: What is 15 * 4? Thought: 1. 15 * 2 is 30. 2. 30 * 2 is 60. Answer:            │
│        60   Question: A bat and a ball cost $1.10 in total. The bat costs $1.00                │
│        more than the ball. How much does the ball cost? (Answer in dollars, e.g.,              │
│        0.05)                                                                                   │
│                                                                                                │
╰────────────────────────────────────────────────────────────────────────────────────────────────╯
╭──────────────────────────────────────── Model Response ────────────────────────────────────────╮
│                                                                                                │
│  ASSISTANT: Thought: 1. Let B be the cost of the bat and L be the cost of the ball. 2. From    │
│             the first statement, "A bat and a ball cost $1.10 in total":    B + L =            │
│             1.10 3. From the second statement, "The bat costs $1.00 more than the              │
│             ball":    B = L + 1.00 4. Now substitute the second equation into the              │
│             first equation:    (L + 1.00) + L = 1.10 5. Combine like terms:    2L +            │
│             1.00 = 1.10 6. Subtract 1.00 from both sides:    2L = 1.10 - 1.00    2L            │
│             = 0.10 7. Divide by 2 to find the cost of the ball (L):    L = 0.10 / 2            │
│             L = 0.05  8. So, the ball costs $0.05. 9. To verify:    If the ball                │
│             costs $0.05, then the bat costs $0.05 + $1.00 = $1.05.    The total                │
│             cost is $1.05 (bat) + $0.05 (ball) = $1.10. This matches the given                 │
│             total.  The final answer needs to be in dollars, e.g., 0.05.  Answer:              │
│             0.05                                                                               │
│                                                                                                │
╰────────────────────────────────────────────────────────────────────────────────────────────────╯
  Run #02: o  3.3s | 613 tokens

╭───────────────────────────────────────── Model Input ──────────────────────────────────────────╮
│                                                                                                │
│  USER: Answer the following question. Think step-by-step and then provide the final            │
│        answer as 'Answer: <value>'.   Example 1: Question: If I have 3 apples and I            │
│        give 2 to my friend, but then my friend gives me 1 back, how many apples do             │
│        I have? Thought:  1. Start with 3 apples. 2. Give 2 away: 3 - 2 = 1 apple               │
│        remaining. 3. Friend gives 1 back: 1 + 1 = 2 apples. Answer: 2  Example 2:              │
│        Question: How many legs does a spider have? Thought: 1. Spiders are                     │
│        arachnids. 2. Arachnids typically have 8 legs. Answer: 8  Example 3:                    │
│        Question: What is 15 * 4? Thought: 1. 15 * 2 is 30. 2. 30 * 2 is 60. Answer:            │
│        60   Question: A farmer has 17 sheep and all but 9 die. How many are left?              │
│                                                                                                │
╰────────────────────────────────────────────────────────────────────────────────────────────────╯
╭──────────────────────────────────────── Model Response ────────────────────────────────────────╮
│                                                                                                │
│  ASSISTANT: Thought: 1. The question states the farmer has 17 sheep. 2. The phrase "all but 9  │
│             die" means that 9 sheep are the *only ones* that did not die. 3.                   │
│             Therefore, 9 sheep are left.  Answer: 9                                            │
│                                                                                                │
╰────────────────────────────────────────────────────────────────────────────────────────────────╯
  Run #03: o  1.7s | 304 tokens

╭───────────────────────────────────────── Model Input ──────────────────────────────────────────╮
│                                                                                                │
│  USER: Answer the following question. Think step-by-step and then provide the final            │
│        answer as 'Answer: <value>'.   Example 1: Question: If I have 3 apples and I            │
│        give 2 to my friend, but then my friend gives me 1 back, how many apples do             │
│        I have? Thought:  1. Start with 3 apples. 2. Give 2 away: 3 - 2 = 1 apple               │
│        remaining. 3. Friend gives 1 back: 1 + 1 = 2 apples. Answer: 2  Example 2:              │
│        Question: How many legs does a spider have? Thought: 1. Spiders are                     │
│        arachnids. 2. Arachnids typically have 8 legs. Answer: 8  Example 3:                    │
│        Question: What is 15 * 4? Thought: 1. 15 * 2 is 30. 2. 30 * 2 is 60. Answer:            │
│        60   Question: In a race, if you pass the person in second place, what place            │
│        are you in?                                                                             │
│                                                                                                │
╰────────────────────────────────────────────────────────────────────────────────────────────────╯
╭──────────────────────────────────────── Model Response ────────────────────────────────────────╮
│                                                                                                │
│  ASSISTANT: Thought: 1. The question states you are in a race. 2. You pass the person who is   │
│             currently in second place. 3. When you pass someone, you take their                │
│             position and they fall behind you. 4. Therefore, if you pass the person            │
│             in second place, you move into second place.  Answer: Second                       │
│                                                                                                │
╰────────────────────────────────────────────────────────────────────────────────────────────────╯
  Run #04: o  2.1s | 314 tokens

╭───────────────────────────────────────── Model Input ──────────────────────────────────────────╮
│                                                                                                │
│  USER: Answer the following question. Think step-by-step and then provide the final            │
│        answer as 'Answer: <value>'.   Example 1: Question: If I have 3 apples and I            │
│        give 2 to my friend, but then my friend gives me 1 back, how many apples do             │
│        I have? Thought:  1. Start with 3 apples. 2. Give 2 away: 3 - 2 = 1 apple               │
│        remaining. 3. Friend gives 1 back: 1 + 1 = 2 apples. Answer: 2  Example 2:              │
│        Question: How many legs does a spider have? Thought: 1. Spiders are                     │
│        arachnids. 2. Arachnids typically have 8 legs. Answer: 8  Example 3:                    │
│        Question: What is 15 * 4? Thought: 1. 15 * 2 is 30. 2. 30 * 2 is 60. Answer:            │
│        60   Question: If it takes 5 machines 5 minutes to make 5 widgets, how long             │
│        would it take 100 machines to make 100 widgets? (Answer in minutes)                     │
│                                                                                                │
╰────────────────────────────────────────────────────────────────────────────────────────────────╯
╭──────────────────────────────────────── Model Response ────────────────────────────────────────╮
│                                                                                                │
│  ASSISTANT: Thought: 1. Understand the core relationship: "5 machines 5 minutes to make 5      │
│             widgets". 2. This means that each machine is essentially making 1                  │
│             widget in 5 minutes. If machine A makes widget A, machine B makes                  │
│             widget B, and so on, then after 5 minutes, 5 widgets are made by 5                 │
│             different machines. 3. Therefore, the time it takes for a single                   │
│             machine to make a single widget is 5 minutes. 4. Now consider 100                  │
│             machines making 100 widgets. 5. If each of the 100 machines is assigned            │
│             to make one widget, and each machine takes 5 minutes to make one                   │
│             widget, then all 100 widgets will be produced simultaneously. 6. The               │
│             total time elapsed will still be the time it takes for one machine to              │
│             make one widget, which is 5 minutes.  Answer: 5                                    │
│                                                                                                │
╰────────────────────────────────────────────────────────────────────────────────────────────────╯
  Run #05: o  3.5s | 454 tokens


──────────────────────────────────────── Overall Summary ─────────────────────────────────────────

                                    Benchmark Results                                    
┏━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━┓
┃ Strategy        ┃             Accuracy              ┃ Total Tokens ┃ Avg Tokens/Query ┃
┡━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━┩
│ Direct          │ XXXXXXXXXXXXXXXX....  4/5  (80%)  │     213      │       42.6       │
├─────────────────┼───────────────────────────────────┼──────────────┼──────────────────┤
│ Zero-Shot CoT   │ XXXXXXXXXXXXXXXXXXXX  5/5  (100%) │     1089     │      217.8       │
├─────────────────┼───────────────────────────────────┼──────────────┼──────────────────┤
│ Few-Shot CoT    │ XXXXXXXXXXXXXXXXXXXX  5/5  (100%) │     2024     │      404.8       │
└─────────────────┴───────────────────────────────────┴──────────────┴──────────────────┘

╭─────────────────────── Verdict ────────────────────────╮
│ Highest Accuracy: Zero-Shot CoT, Few-Shot CoT (100.0%) │
│ Most Efficient:   Direct                               │
╰────────────────────────────────────────────────────────╯
