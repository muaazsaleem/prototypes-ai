╭───────────────────────────────────────────────────────────────────────────╮
│ Chain-of-Thought vs. Direct Answer                                        │
│ Comparison of performance and latency across multiple reasoning problems. │
│ 8 runs × 2 strategies × 5 problems                                        │
╰───────────────────────────────────────────────────────────────────────────╯

─────────────────────────────────────────────────────────────────────────────────── Problem 1 / 5: Spatial Navigation (Grid) ────────────────────────────────────────────────────────────────────────────────────
Q: Start at origin (0,0) facing North (+Y direction). Move forward 3 units. Turn right 90 degrees. Move forward 2 units. Turn right 90 degrees. Move forward 5 units. Turn left 90 degrees. Move backward 2 
units. What are your exact final (X,Y) coordinates? Format as (X, Y).
Correct answer: (0, -2)
Common wrong answer: (4, -2) or (2, 2) (loses track of current heading before moving)
Start(0,0) N -> Fwd 3 to (0,3). Right to E -> Fwd 2 to (2,3). Right to S -> Fwd 5 to (2,-2). Left to E -> Back 2 (moving West) to (0,-2).

── Direct prompts ──────────────────────────
  Direct #01: ●  4.3s     Direct #02: ●  3.8s     Direct #03: ●  2.4s     Direct #04: ●  4.7s   
  Direct #05: ●  2.3s     Direct #06: ●  3.4s     Direct #07: ●  4.2s     Direct #08: ●  3.2s   

── Chain-of-Thought prompts ─────────────────
  CoT    #01: ●  5.7s     CoT    #02: ●  5.1s     CoT    #03: ●  6.7s     CoT    #04: ●  5.2s   
  CoT    #05: ●  5.3s     CoT    #06: ●  6.8s     CoT    #07: ●  6.3s     CoT    #08: ●  5.9s   

  Strategy    ┃  Score   ┃    Avg Time  ┃  Distribution (filled = correct)    
━━━━━━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Direct      │   8/8    │       3.54s  │  ████████████████████  8/8  (100%)  
  CoT         │   8/8    │       5.90s  │  ████████████████████  8/8  (100%)  

───────────────────────────────────────────────────────────────────────────────── Problem 2 / 5: Relational Logic (Family Tree) ─────────────────────────────────────────────────────────────────────────────────
Q: Alice is the sister of Bob. Bob is the father of Charlie. Charlie is the brother of Diana. Diana is the mother of Eve. What is the exact biological relationship of Alice to Eve?
Correct answer: great-aunt
Common wrong answer: Aunt or Grandmother (skips a generational layer)
Bob is Diana's father. Alice is Bob's sister, making her Diana's aunt. Diana is Eve's mother, making Alice Eve's great-aunt.

── Direct prompts ──────────────────────────
  Direct #01: ●  2.3s     Direct #02: ●  1.8s     Direct #03: ●  2.7s     Direct #04: ●  2.0s   
  Direct #05: ●  2.3s     Direct #06: ●  1.9s     Direct #07: ●  2.2s     Direct #08: ●  2.2s   

── Chain-of-Thought prompts ─────────────────
  CoT    #01: ●  4.8s     CoT    #02: ●  6.5s     CoT    #03: ●  6.3s     CoT    #04: ●  4.8s   
  CoT    #05: ●  5.9s     CoT    #06: ●  5.0s     CoT    #07: ●  5.2s     CoT    #08: ●  4.9s   

  Strategy    ┃  Score   ┃    Avg Time  ┃  Distribution (filled = correct)    
━━━━━━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Direct      │   8/8    │       2.19s  │  ████████████████████  8/8  (100%)  
  CoT         │   8/8    │       5.41s  │  ████████████████████  8/8  (100%)  

────────────────────────────────────────────────────────────────────────────────────── Problem 3 / 5: Temporal Scheduling ───────────────────────────────────────────────────────────────────────────────────────
Q: Five speakers (A, B, C, D, E) present one after another. E must speak exactly third. B must speak immediately after D. D cannot be the first speaker. C must speak at some point before A. What is the exact 
sequence of the 5 speakers from first to last? Format as a comma-separated list.
Correct answer: c, a, e, d, b
Common wrong answer: C, D, B, E, A (violates E being third or D being first)
E is 3rd (_ _ E _ _). DB is a block, can't be 1-2 (D not 1st), so must be 4-5 (_ _ E D B). C before A fills 1 and 2 (C A E D B).

── Direct prompts ──────────────────────────
  Direct #01: ●  5.8s     Direct #02: ●  3.5s     Direct #03: ●  4.9s     Direct #04: ●  3.6s   
  Direct #05: ●  3.1s     Direct #06: ●  3.3s     Direct #07: ●  3.8s     Direct #08: ●  3.4s   

── Chain-of-Thought prompts ─────────────────
  CoT    #01: ●  5.9s     CoT    #02: ●  5.8s     CoT    #03: ●  5.7s     CoT    #04: ●  7.2s   
  CoT    #05: ●  6.0s     CoT    #06: ●  5.7s     CoT    #07: ●  5.7s     CoT    #08: ●  8.3s   

  Strategy    ┃  Score   ┃    Avg Time  ┃  Distribution (filled = correct)    
━━━━━━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Direct      │   8/8    │       3.93s  │  ████████████████████  8/8  (100%)  
  CoT         │   8/8    │       6.29s  │  ████████████████████  8/8  (100%)  

──────────────────────────────────────────────────────────────────────────────────── Problem 4 / 5: Inventory State Tracking ────────────────────────────────────────────────────────────────────────────────────
Q: An empty box is given to you. You put in an Apple, a Banana, and a Carrot. You remove the Apple and add a Date. You remove the Carrot and put the Apple back in. You swap the Banana for an Eggplant. Finally,
you take out the Date. List exactly the items currently in the box.
Correct answer: apple, eggplant
Common wrong answer: Apple, Banana, Date (fails to apply all state changes sequentially)
Add A,B,C -> [A,B,C]. Rem A, Add D -> [B,C,D]. Rem C, Add A -> [A,B,D]. Swap B for E -> [A,D,E]. Rem D -> [A,E].

── Direct prompts ──────────────────────────
  Direct #01: ●  2.2s     Direct #02: ●  2.2s     Direct #03: ●  2.1s     Direct #04: ●  2.4s   
  Direct #05: ●  2.2s     Direct #06: ●  1.9s     Direct #07: ●  2.0s     Direct #08: ●  2.0s   

── Chain-of-Thought prompts ─────────────────
  CoT    #01: ●  3.5s     CoT    #02: ●  2.7s     CoT    #03: ●  4.1s     CoT    #04: ●  3.7s   
  CoT    #05: ●  4.2s     CoT    #06: ●  4.7s     CoT    #07: ●  2.7s     CoT    #08: ●  2.8s   

  Strategy    ┃  Score   ┃    Avg Time  ┃  Distribution (filled = correct)    
━━━━━━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Direct      │   0/8    │       2.13s  │  ░░░░░░░░░░░░░░░░░░░░  0/8  (0%)    
  CoT         │   8/8    │       3.55s  │  ████████████████████  8/8  (100%)  

────────────────────────────────────────────────────────────────────────────────── Problem 5 / 5: Logic Puzzle (Truth-Tellers) ──────────────────────────────────────────────────────────────────────────────────
Q: There are three boxes: X, Y, and Z. Exactly one contains a diamond. Box X says: 'The diamond is in Box Y.' Box Y says: 'The diamond is not in Box Y.' Box Z says: 'The diamond is not in Box X.' Exactly one 
box's statement is true. Which box contains the diamond? Answer with the exact phrase 'Box X', 'Box Y', or 'Box Z'.
Correct answer: box x
Common wrong answer: Box Y or Z (fails to evaluate the statements against all possible states)
If the diamond is in X: X is false, Y is true, Z is false. This yields exactly one true statement, satisfying the condition.

── Direct prompts ──────────────────────────
  Direct #01: ●  4.9s     Direct #02: ●  5.3s     Direct #03: ●  4.1s     Direct #04: ●  3.2s   
  Direct #05: ●  4.5s     Direct #06: ●  5.1s     Direct #07: ●  3.4s     Direct #08: ●  5.4s   

── Chain-of-Thought prompts ─────────────────
  CoT    #01: ●  7.8s     CoT    #02: ●  6.2s     CoT    #03: ●  7.2s     CoT    #04: ●  9.8s   
  CoT    #05: ●  6.6s     CoT    #06: ●  9.1s     CoT    #07: ●  6.4s     CoT    #08: ●  9.3s   

  Strategy    ┃  Score   ┃    Avg Time  ┃  Distribution (filled = correct)    
━━━━━━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Direct      │   8/8    │       4.48s  │  ████████████████████  8/8  (100%)  
  CoT         │   8/8    │       7.79s  │  ████████████████████  8/8  (100%)  

──────────────────────────────────────────────────────────────────────────────────────────────── Overall Summary ────────────────────────────────────────────────────────────────────────────────────────────────
  Problem                         ┃  Direct  ┃   CoT   ┃  Avg T (D/C)  ┃  CoT lift  ┃  Distribution            
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━╇━━━━━━━━━━━━━━━╇━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━
  Spatial Navigation (Grid)       │   8/8    │   8/8   │  3.5s / 5.9s  │     ±0     │  D:████████  C:████████  
  Relational Logic (Family Tree)  │   8/8    │   8/8   │  2.2s / 5.4s  │     ±0     │  D:████████  C:████████  
  Temporal Scheduling             │   8/8    │   8/8   │  3.9s / 6.3s  │     ±0     │  D:████████  C:████████  
  Inventory State Tracking        │   0/8    │   8/8   │  2.1s / 3.6s  │     +8     │  D:░░░░░░░░  C:████████  
  Logic Puzzle (Truth-Tellers)    │   8/8    │   8/8   │  4.5s / 7.8s  │     ±0     │  D:████████  C:████████  
──────────────────────────────────┼──────────┼─────────┼───────────────┼────────────┼──────────────────────────
  TOTAL / AVG                     │  32/40   │  40/40  │  3.3s / 5.8s  │     +8     │                          
