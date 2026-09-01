title: "ReSort Walkthrough — Guided Task Scenario",
text: `<p>This decision tree slows down the evaluation process, guiding you step-by-step through a concrete scenario: auditing a task currently labeled 'Requires Fluent Finnish'.</p>
       <p>By tracing the path, you actively apply the ReSort diagnostic filters—checking for detail-avoidance, maintenance valuation, and artificial language gatekeeping.</p>
       <p>This deliberate pacing helps dismantle automatic management assumptions, ensuring the final task designation is based on actual operational reality rather than inherited habits.</p>`,
code: `flowchart TD
    %%{init: {'theme': 'base', 'themeVariables': {'lineColor': '#888780', 'fontSize': '13px'}}}%%

    subgraph Scenario_Start [1. Task Selection]
        START["Task Scenario: 'Handling Internal Team Reports'"] ---> Q1{"Q1: The Detail Filter<br>Why is this delegated?"}
    end

    subgraph Filter_1 [2. Diagnosing Detail Avoidance]
        Q1 -- "It requires specialized knowledge" --> Q2{"Q2: The Maintenance Value<br>How is this work valued?"}
        Q1 -- "I just don't want to deal with the admin" --> BIAS1["🚨 Friction-Dumping Detected"]
        BIAS1 --> REVALUE["Acknowledge as Vital Infrastructure & Share Load"]
        REVALUE --> Q2
    end

    subgraph Filter_2 [3. Assessing Language Reality]
        Q2 -- "It is treated as invisible support work" --> BIAS2["🚨 Care & Maintenance Devaluation"]
        BIAS2 --> ELEVATE["Reclassify as Core Operational Competency"]
        ELEVATE --> Q3{"Q3: Language Metric<br>Is native fluency actually required?"}
        Q2 -- "It is recognized core work" --> Q3
    end

    subgraph Filter_3 [4. The ReSort Action]
        Q3 -- "Yes, strict legal/safety compliance" --> UNBUNDLE["Unbundle: Keep C1 requirement, assign to local expert"]
        Q3 -- "No, it's mostly async/internal reading" --> TECH["Lower to A2/B1 & Enable Enterprise Translation"]
    end

    subgraph Outcome [5. Final Framework Strategy]
        UNBUNDLE ---> BALANCE["Rebalance Foreign Worker's Role with Non-C1 Tasks"]
        TECH ---> BALANCE
        BALANCE --> NEW_ROLE["🔁 Task Successfully ReSorted"]
    end

    classDef dataInput fill:#FAEEDA,stroke:#854F0B,color:#412402
    classDef barrier fill:#FBE6E8,stroke:#A61C1C,color:#5C0A0A
    classDef audit fill:#E1F5EE,stroke:#0F6E56,color:#04342C
    classDef techTask fill:#EEEDFE,stroke:#534AB7,color:#26215C
    classDef outcome fill:#F1EFE8,stroke:#5F5E5A,color:#2C2C2A

    class START dataInput
    class BIAS1,BIAS2 barrier
    class Q1,Q2,Q3,REVALUE,ELEVATE audit
    class TECH techTask
    class UNBUNDLE,BALANCE,NEW_ROLE outcome`
