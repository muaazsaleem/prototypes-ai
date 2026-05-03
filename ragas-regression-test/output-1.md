╭────────────────────────────────────────────────────────────────────────────────╮
│ RAGAS Regression Test: Reranker Cutoff Analysis                                │
│ Evaluating the impact of reranker depth on Context Precision and Faithfulness. │
│ Baseline: Top-5 | Experiment: Top-2                                            │
╰────────────────────────────────────────────────────────────────────────────────╯

───────────────────────────────────────── Baseline Run (Cutoff=5) ─────────────────────────────────────────
Processing 100 samples...
╭────────────────────────────────────────────── Model Input ──────────────────────────────────────────────╮
│                                                                                                         │
│  USER: Answer the following question using ONLY the provided context.  Question: What are               │
│        the primary benefits and considerations for using Amazon EC2 Spot Instances,                     │
│        especially for fault-tolerant or stateless workloads?  Context: - EC2 Spot                       │
│        Instances enable you to request unused EC2 instances at a significant                            │
│        discount compared to On-Demand prices. You can save up to 90% on compute                         │
│        costs by leveraging these instances. - Spot Instances are highly suitable                        │
│        for workloads that are fault-tolerant, flexible, and stateless, such as                          │
│        batch jobs, big data processing, containerized microservices, high-                              │
│        performance computing (HPC), and development/testing environments. - The                         │
│        primary consideration for Spot Instances is their interruptible nature. EC2                      │
│        can reclaim capacity with a two-minute notification, requiring applications                      │
│        to be designed to handle interruptions gracefully, often by saving state or                      │
│        restarting work. - Common use cases include distributed workloads, CI/CD                         │
│        pipelines, web servers that can scale out, and image rendering where                             │
│        individual tasks can be restarted without loss.                                                  │
│                                                                                                         │
╰─────────────────────────────────────────────────────────────────────────────────────────────────────────╯

╭──────────────────────────────────────────── Model Response ─────────────────────────────────────────────╮
│                                                                                                         │
│  ASSISTANT: The primary benefits of using Amazon EC2 Spot Instances are: *   A significant              │
│             discount compared to On-Demand prices, allowing users to save up to 90%                     │
│             on compute costs.  The primary considerations for using Spot Instances                      │
│             are: *   Their interruptible nature, as EC2 can reclaim capacity with a                     │
│             two-minute notification. *   Applications must be designed to handle                        │
│             these interruptions gracefully, often by saving state or restarting                         │
│             work.  For fault-tolerant or stateless workloads, Spot Instances are                        │
│             highly suitable because these types of applications (such as batch                          │
│             jobs, big data processing, containerized microservices, high-                               │
│             performance computing (HPC), development/testing environments,                              │
│             distributed workloads, CI/CD pipelines, web servers that can scale out,                     │
│             and image rendering where individual tasks can be restarted without                         │
│             loss) are well-equipped to manage the interruptible nature without                          │
│             significant disruption.                                                                     │
│                                                                                                         │
╰─────────────────────────────────────────────────────────────────────────────────────────────────────────╯

xxooooooooxxxoxooooo 20/100
xxxxxxxxxxxxxxxxxxxx 40/100
xxxxxxxxooxxoooooooo 60/100
ooooooooooxooooooooo 80/100
xxooxxxxooxxxxxxxxxo 100/100

Baseline - Precision: 0.8679, Faithfulness: 0.9366

──────────────────────────────────────── Experiment Run (Cutoff=2) ────────────────────────────────────────
Processing 100 samples...
╭────────────────────────────────────────────── Model Input ──────────────────────────────────────────────╮
│                                                                                                         │
│  USER: Answer the following question using ONLY the provided context.  Question: What are               │
│        the primary benefits and considerations for using Amazon EC2 Spot Instances,                     │
│        especially for fault-tolerant or stateless workloads?  Context: - EC2 Spot                       │
│        Instances enable you to request unused EC2 instances at a significant                            │
│        discount compared to On-Demand prices. You can save up to 90% on compute                         │
│        costs by leveraging these instances. - Spot Instances are highly suitable                        │
│        for workloads that are fault-tolerant, flexible, and stateless, such as                          │
│        batch jobs, big data processing, containerized microservices, high-                              │
│        performance computing (HPC), and development/testing environments.                               │
│                                                                                                         │
╰─────────────────────────────────────────────────────────────────────────────────────────────────────────╯

╭──────────────────────────────────────────── Model Response ─────────────────────────────────────────────╮
│                                                                                                         │
│  ASSISTANT: **Primary Benefits:** *   **Significant Cost Savings:** Users can save up to 90%            │
│             on compute costs compared to On-Demand prices by utilizing unused EC2                       │
│             instances.  **Considerations (especially for fault-tolerant or                              │
│             stateless workloads):** *   Spot Instances are highly suitable for                          │
│             workloads that are **fault-tolerant, flexible, and stateless**. *                           │
│             Examples of such suitable workloads include batch jobs, big data                            │
│             processing, containerized microservices, high-performance computing                         │
│             (HPC), and development/testing environments.                                                │
│                                                                                                         │
╰─────────────────────────────────────────────────────────────────────────────────────────────────────────╯

oooooooooooooooooooo 20/100
oooooooooooooooooooo 40/100
oooooooooooooooooooo 60/100
oooooooooooooooooooo 80/100
oooooooooooooooooooo 100/100

Experiment - Precision: 0.6479, Faithfulness: 0.8839

───────────────────────────────────────────── Overall Summary ─────────────────────────────────────────────
                      Regression Test Results                      
┏━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━┳━━━━━━━━━┓
┃ Metric            ┃ Baseline (K=5) ┃ Experiment (K=2) ┃  Delta  ┃
┡━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━╇━━━━━━━━━┩
│ Context Precision │     0.8679     │      0.6479      │ -0.2199 │
├───────────────────┼────────────────┼──────────────────┼─────────┤
│ Faithfulness      │     0.9366     │      0.8839      │ -0.0527 │
└───────────────────┴────────────────┴──────────────────┴─────────┘

Verdict: FAIL
Significant regression detected in context precision due to aggressive cutoff.