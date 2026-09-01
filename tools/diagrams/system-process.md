title: "AI-Driven Task Audit & Role Re-Sorting Workflow",
text: `<p>This process details how organizations can move away from blanket 'Fluent Finnish' mandates by using structured task auditing and AI analysis.</p>
        <p>Step 1 extracts raw task data from existing Kanban boards, job descriptions, or HR lists. Step 2 runs these tasks through a structured LLM prompt mapping framework to identify actual language needs and machine-translation feasibility.</p>
        <p>Step 3 reorganises the workload by either unbundling high-fluency tasks or providing enterprise translation tools, creating an equitable, non-hierarchical division of labor.</p>`,
code: `flowchart TD
    %%{init: {'theme': 'base', 'themeVariables': {'primaryColor': '#EEEDFE', 'primaryBorderColor': '#534AB7', 'primaryTextColor': '#26215C', 'lineColor': '#888780', 'secondaryColor': '#E1F5EE', 'fontSize': '13px'}}}%%

    subgraph Step_1 [1. Operational Data Extraction]
        EXPORT["Export Role Tasks & Kanban Backlog to CSV/JSON"] ---> READ["Identify Core Task Specifications & Frequency"]
    end

    subgraph Step_2 [2. Structured AI Language Audit]
        READ ---> PROMPT["Feed CSV into LLM with Task Audit Framework"]
        PROMPT --> EVAL_LANG["Evaluate CEFR Requirement per Task (A1–C1)"]
        EVAL_LANG --> EVAL_TECH["Assess Translation Tech Feasibility (DeepL/LLMs)"]
    end

    subgraph Step_3 [3. Task Classification & Decision]
        EVAL_TECH ---> COND_C1{"Requires C1 Live Native Fluency?"}
        COND_C1 -- "Yes (Legal / Safety)" --> HIGH_LANG["Isolate High-Fluency Task"]
        COND_C1 -- "No (Async / Technical)" --> TECH_LANG["Map to A1-B1 or Tech-Assisted Task"]
    end

    subgraph Step_4 [4. Role Re-Sorting & System Optimization]
        HIGH_LANG ---> UNBUNDLE["Unbundle: Shift C1 Tasks to Fluent Team Member"]
        TECH_LANG ---> TOOL_ENABLE["Enable Enterprise Translation & Async Workflows"]
        UNBUNDLE --> BALANCE["Re-balance Role with Non-Language Intensive Detail"]
        TOOL_ENABLE --> FINAL_ROLE["Publish Re-Sorted, Equitable Role Blueprint"]
        BALANCE --> FINAL_ROLE
    end

    classDef dataInput fill:#FAEEDA,stroke:#854F0B,color:#412402
    classDef aiEngine fill:#E1F5EE,stroke:#0F6E56,color:#04342C
    classDef techTask fill:#EEEDFE,stroke:#534AB7,color:#26215C
    classDef highLang fill:#FBE6E8,stroke:#A61C1C,color:#5C0A0A
    classDef strategy fill:#F1EFE8,stroke:#5F5E5A,color:#2C2C2A

    class EXPORT,READ dataInput
    class PROMPT,EVAL_LANG,EVAL_TECH aiEngine
    class TECH_LANG,TOOL_ENABLE techTask
    class HIGH_LANG highLang
    class COND_C1,UNBUNDLE,BALANCE,FINAL_ROLE strategy`
    
