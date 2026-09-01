title: "System Journey — The Foreign Talent Experience",
text: `<p>This journey traces the real-world trajectory of an international specialist navigating the Finnish labor market—from encountering artificial language barriers to working in a re-sorted, accessible environment.</p>
        <p>Phase 1 highlights the initial friction: highly qualified talent blocked by blanket 'Fluent Finnish' requirements on roles where native fluency isn't functionally required.</p>
        <p>Phase 2 illustrates the systemic intervention: auditing each task's actual language requirement, unbundling high-fluency tasks, and integrating enterprise translation tools for async work.</p>
        <p>Phase 3 depicts the outcome: an integrated, high-trust workplace where foreign specialists contribute their core skills without being relegated to low-status maintenance tiers.</p>`,
code: `flowchart TD
    %%{init: {'theme': 'base', 'themeVariables': {'primaryColor': '#EEEDFE', 'primaryBorderColor': '#534AB7', 'primaryTextColor': '#26215C', 'lineColor': '#888780', 'secondaryColor': '#E1F5EE', 'fontSize': '13px'}}}%%

    subgraph Phase_1 [1. Encountering Structural Barriers]
        APPLY["International Candidate Applies for Role"] ---> BARRIER["Hits Blanket 'Fluent Finnish' Requirement"]
        BARRIER --> REJECT["Talent Sidelined into Low-Status or Unwanted Work"]
    end

    subgraph Phase_2 [2. Task-Level Language Restructuring]
        AUDIT["Audit Role: Evaluate Real Language Needed Per Task"] ---> UNBUNDLE["Unbundle: Reassign C1-Only Tasks to Fluent Teammates"]
        AUDIT --> TOOLS["Integrate Enterprise Translation Tools for Async Tasks"]
        AUDIT --> RESORT["Re-Sort Kanban Board Around Actual Functional Skills"]
    end

    subgraph Phase_3 [3. Equitable Integration & Flow]
        UNBUNDLE ---> CLEAR_PATH["Role Redesigned Around Actual Task Requirements"]
        TOOLS --> CLEAR_PATH
        RESORT --> CLEAR_PATH
        CLEAR_PATH --> INTEGRATED["Foreign Specialist Contributes Core Skills & Gains Agency"]
    end

    classDef barrier fill:#FBE6E8,stroke:#A61C1C,color:#5C0A0A
    classDef audit fill:#E1F5EE,stroke:#0F6E56,color:#04342C
    classDef outcome fill:#F1EFE8,stroke:#5F5E5A,color:#2C2C2A

    class APPLY,BARRIER,REJECT barrier
    class AUDIT,UNBUNDLE,TOOLS,RESORT audit
    class CLEAR_PATH,INTEGRATED outcome`
