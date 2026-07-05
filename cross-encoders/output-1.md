╭───────────────────────────────────────────────────────────────────────────────────╮
│ Cross-Encoder vs Bi-Encoder Prototype                                             │
│ Demonstrating the limitations of bi-encoders and the precision of cross-encoders. │
│ Features: Word Sense Disambiguation, Logic Traps, Asymmetric Directional Search   │
╰───────────────────────────────────────────────────────────────────────────────────╯

──────────────────────────────────────────────────────────── Scenario 1: Lexical & Semantic Ambiguity (Fruit vs. Tech) ─────────────────────────────────────────────────────────────

Query: "apple computer"
Concept: Bi-encoders are heavily biased by keyword overlap. When searching for 'apple computer', documents containing the word 'apple' (like apple fruit or pie) align strongly in 
the vector space. Cross-encoders use joint attention to recognize that 'computer' restricts the meaning of 'apple' to technology.

                                  Comparison for Query: "apple computer"                                  
┏━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃  Rank  ┃ Bi-Encoder (Cosine Similarity)                ┃ Cross-Encoder (Relevance Score)               ┃
┡━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│   1    │ The new MacBook Pro is a powerful Apple       │ The new MacBook Pro is a powerful Apple       │
│        │ computer built for creative professionals.    │ computer built for creative professionals.    │
│        │ Score: 0.6357                                 │ Score: 0.9507                                 │
├────────┼───────────────────────────────────────────────┼───────────────────────────────────────────────┤
│   2    │ Computers are complex machines; remember      │ Apple Inc. is expected to announce new        │
│        │ to eat a healthy apple while working on       │ hardware products at its upcoming keynote.    │
│        │ them.                                         │ Score: 0.7969                                 │
│        │ Score: 0.6033                                 │                                               │
├────────┼───────────────────────────────────────────────┼───────────────────────────────────────────────┤
│   3    │ The stock price of Apple rose after they      │ The stock price of Apple rose after they      │
│        │ announced their latest high-performance       │ announced their latest high-performance       │
│        │ computers.                                    │ computers.                                    │
│        │ Score: 0.5191                                 │ Score: 0.7769                                 │
├────────┼───────────────────────────────────────────────┼───────────────────────────────────────────────┤
│   4    │ Apple Inc. is expected to announce new        │ Computers are complex machines; remember      │
│        │ hardware products at its upcoming keynote.    │ to eat a healthy apple while working on       │
│        │ Score: 0.4693                                 │ them.                                         │
│        │                                               │ Score: 0.2703                                 │
├────────┼───────────────────────────────────────────────┼───────────────────────────────────────────────┤
│   5    │ An apple a day keeps the doctor away,         │ An apple a day keeps the doctor away,         │
│        │ especially if it is a fresh, organic red      │ especially if it is a fresh, organic red      │
│        │ delicious apple.                              │ delicious apple.                              │
│        │ Score: 0.3436                                 │ Score: 0.0036                                 │
├────────┼───────────────────────────────────────────────┼───────────────────────────────────────────────┤
│   6    │ I baked a delicious homemade apple pie        │ I baked a delicious homemade apple pie        │
│        │ with a crispy, golden-brown crust.            │ with a crispy, golden-brown crust.            │
│        │ Score: 0.2962                                 │ Score: 0.0021                                 │
└────────┴───────────────────────────────────────────────┴───────────────────────────────────────────────┘

╭─────────────────────────────────────────────────────────────────────────────── Deep-Dive Analysis ───────────────────────────────────────────────────────────────────────────────╮
│                                                                                                                                                                                  │
│  Why the Bi-Encoder struggled:                                                                                                                                                   │
│  • The document 'Computers are complex machines; remember to eat a healthy apple...' is ranked highly because it contains both of the query terms ('apple' and 'computer')       │
│  literally, even though their relationship is purely coincidental and irrelevant.                                                                                                │
│  • It also gives moderate similarity scores to fruit-related documents ('apple pie', 'apple a day') because the word 'apple' has high vector similarity with the query.          │
│                                                                                                                                                                                  │
│  Why the Cross-Encoder succeeded:                                                                                                                                                │
│  • By performing token-to-token cross-attention between the query and the document simultaneously, it realizes that 'computer' in the query does not relate to 'pie' or          │
│  'doctor' in the documents.                                                                                                                                                      │
│  • It outputs extremely low scores (e.g., 0.00 to 0.27) for the irrelevant fruit articles and coincidental matches, while scoring actual technology-related articles highly      │
│  (above 0.75), providing a crystal-clear separation margin.                                                                                                                      │
│                                                                                                                                                                                  │
╰──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯

──────────────────────────────────────────────────────────── Scenario 2: Logical Relation & Negation (The 'Logic Trap') ────────────────────────────────────────────────────────────

Query: "Does aspirin treat headaches?"
Concept: Bi-encoders struggle with semantic relationships (causes vs. treats) and negation because they compress sentences into a single vector, losing syntactical directionality. 
Cross-encoders maintain token-to-token interactions, accurately resolving complex logic.

                          Comparison for Query: "Does aspirin treat headaches?"                           
┏━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃  Rank  ┃ Bi-Encoder (Cosine Similarity)                ┃ Cross-Encoder (Relevance Score)               ┃
┡━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│   1    │ Clinical trials show that aspirin treats      │ Clinical trials show that aspirin treats      │
│        │ headaches by reducing inflammation.           │ headaches by reducing inflammation.           │
│        │ Score: 0.8856                                 │ Score: 0.9883                                 │
├────────┼───────────────────────────────────────────────┼───────────────────────────────────────────────┤
│   2    │ To treat a headache, doctors often            │ To treat a headache, doctors often            │
│        │ recommend aspirin or rest.                    │ recommend aspirin or rest.                    │
│        │ Score: 0.7931                                 │ Score: 0.7544                                 │
├────────┼───────────────────────────────────────────────┼───────────────────────────────────────────────┤
│   3    │ A severe headache is a known rare side        │ Taking aspirin for a headache should be       │
│        │ effect of taking aspirin.                     │ done with food to avoid stomach upset.        │
│        │ Score: 0.7719                                 │ Score: 0.5806                                 │
├────────┼───────────────────────────────────────────────┼───────────────────────────────────────────────┤
│   4    │ Aspirin can cause stomach bleeding, which     │ A severe headache is a known rare side        │
│        │ is a far worse issue than a mild headache.    │ effect of taking aspirin.                     │
│        │ Score: 0.7679                                 │ Score: 0.3992                                 │
├────────┼───────────────────────────────────────────────┼───────────────────────────────────────────────┤
│   5    │ Headaches are often caused by stress, not     │ Aspirin can cause stomach bleeding, which     │
│        │ a lack of aspirin.                            │ is a far worse issue than a mild headache.    │
│        │ Score: 0.7471                                 │ Score: 0.3293                                 │
├────────┼───────────────────────────────────────────────┼───────────────────────────────────────────────┤
│   6    │ Taking aspirin for a headache should be       │ Headaches are often caused by stress, not     │
│        │ done with food to avoid stomach upset.        │ a lack of aspirin.                            │
│        │ Score: 0.7379                                 │ Score: 0.1461                                 │
└────────┴───────────────────────────────────────────────┴───────────────────────────────────────────────┘

╭─────────────────────────────────────────────────────────────────────────────── Deep-Dive Analysis ───────────────────────────────────────────────────────────────────────────────╮
│                                                                                                                                                                                  │
│  Why the Bi-Encoder struggled:                                                                                                                                                   │
│  • It scores 'A severe headache is a known rare side effect of taking aspirin' extremely high. This is because the sentence contains 'aspirin' and 'headache', completely        │
│  ignoring the causal direction (aspirin causing a headache rather than treating it).                                                                                             │
│  • It also fails to discount the negation in 'not a lack of aspirin' because the keyword overlap is high.                                                                        │
│                                                                                                                                                                                  │
│  Why the Cross-Encoder succeeded:                                                                                                                                                │
│  • The cross-attention layers easily resolve the syntactic dependency between 'aspirin', 'treats', and 'headache'.                                                               │
│  • It correctly identifies that a 'side effect' of headache means aspirin causes headache, assigning it a much lower relevance score.                                            │
│                                                                                                                                                                                  │
╰──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯

──────────────────────────────────────────────────────── Scenario 3: Asymmetric Directional Search (Source vs. Destination) ────────────────────────────────────────────────────────

Query: "flight from Boston to New York"
Concept: Directional queries are notoriously difficult for bi-encoders. Since the vocabulary of 'Boston to New York' and 'New York to Boston' is identical, their dense embeddings 
are nearly identical. Cross-encoders capture precise sequence order and prepositions.

                          Comparison for Query: "flight from Boston to New York"                          
┏━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃  Rank  ┃ Bi-Encoder (Cosine Similarity)                ┃ Cross-Encoder (Relevance Score)               ┃
┡━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│   1    │ If you are flying out of New York, you can    │ This direct flight from Boston to New York    │
│        │ easily catch an evening flight to Boston.     │ leaves daily at 9:00 AM.                      │
│        │ Score: 0.8337                                 │ Score: 0.9868                                 │
├────────┼───────────────────────────────────────────────┼───────────────────────────────────────────────┤
│   2    │ This direct flight from Boston to New York    │ Enjoy our luxurious business-class flight     │
│        │ leaves daily at 9:00 AM.                      │ from Boston to New York with free Wi-Fi.      │
│        │ Score: 0.8150                                 │ Score: 0.9619                                 │
├────────┼───────────────────────────────────────────────┼───────────────────────────────────────────────┤
│   3    │ We offer daily high-speed flights from New    │ We offer daily high-speed flights from New    │
│        │ York to Boston starting at $99.               │ York to Boston starting at $99.               │
│        │ Score: 0.7530                                 │ Score: 0.9116                                 │
├────────┼───────────────────────────────────────────────┼───────────────────────────────────────────────┤
│   4    │ Enjoy our luxurious business-class flight     │ If you are flying out of New York, you can    │
│        │ from Boston to New York with free Wi-Fi.      │ easily catch an evening flight to Boston.     │
│        │ Score: 0.6802                                 │ Score: 0.8140                                 │
├────────┼───────────────────────────────────────────────┼───────────────────────────────────────────────┤
│   5    │ Flights to other major East Coast cities,     │ Flights to other major East Coast cities,     │
│        │ including Boston and New York, are on         │ including Boston and New York, are on         │
│        │ sale.                                         │ sale.                                         │
│        │ Score: 0.6458                                 │ Score: 0.8062                                 │
├────────┼───────────────────────────────────────────────┼───────────────────────────────────────────────┤
│   6    │ Amtrak's Acela Express provides fast train    │ Amtrak's Acela Express provides fast train    │
│        │ travel between Boston and New York.           │ travel between Boston and New York.           │
│        │ Score: 0.6079                                 │ Score: 0.8052                                 │
└────────┴───────────────────────────────────────────────┴───────────────────────────────────────────────┘

╭─────────────────────────────────────────────────────────────────────────────── Deep-Dive Analysis ───────────────────────────────────────────────────────────────────────────────╮
│                                                                                                                                                                                  │
│  Why the Bi-Encoder struggled:                                                                                                                                                   │
│  • It cannot differentiate between the source and destination. The sentence 'flights from New York to Boston' gets nearly the same similarity score as the correct one because   │
│  the word vectors for 'Boston', 'New York', and 'flight' dominate the sentence embedding.                                                                                        │
│  • It also scores train travel highly because it mentions 'Boston' and 'New York' in a transit context.                                                                          │
│                                                                                                                                                                                  │
│  Why the Cross-Encoder succeeded:                                                                                                                                                │
│  • It tracks word order and syntactic relations. It understands that 'from Boston' specifies the origin and 'to New York' specifies the destination.                             │
│  • It clearly downgrades the reverse flight ('New York to Boston') and train-based alternatives, placing only the genuine matching flights at the very top.                      │
│                                                                                                                                                                                  │
╰──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯

