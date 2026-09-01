title: "Process Diagram — Agricultural Evaluation & Scheduling Engine",
text: `<p>This process diagram maps the step-by-step logical execution, control loops, and validation checks required to convert field inputs into actionable planting advice.</p>
        <p>Phase 1 detail: The process validates incoming user parameters (soil pH, location, crops) and fetches corresponding microclimate and soil baseline records from the cached feature store.</p>
        <p>Phase 2 detail: The engine executes companion compatibility algorithms, evaluates agronomic rules (e.g., nitrogen fixers paired with heavy feeders), and filters out invalid combinations based on seasonal activity windows.</p>
        <p>Phase 3 detail: The process constructs the optimized crop list, compiles the daily task schedule, and serves the formatted payload to the client interface.</p>`,
code: `flowchart TD
    %%{init: {'theme': 'base', 'themeVariables': {'primaryColor': '#EEEDFE', 'primaryBorderColor': '#534AB7', 'primaryTextColor': '#26215C', 'lineColor': '#888780', 'secondaryColor': '#E1F5EE', 'fontSize': '13px'}}}%%

    subgraph Phase_1 [1. Logic Trigger & Parameter Validation]
        START([User Submits Site & Crop Selection]) ---> VAL_INPUT{Validate Inputs: pH, Type & Location Valid?}
        VAL_INPUT -- No --> ERR_INPUT[Return Validation Warning to UI]
        VAL_INPUT -- Yes --> FETCH_FEAT[Query Feature Tables for Soil & Microclimate Baselines]
    end

    subgraph Phase_2 [2. Agronomic & Companion Logic Processing]
        FETCH_FEAT ---> MATCH_COMP[Evaluate Companion Species Matrix]
        MATCH_COMP --> CHK_WEATHER{Are Seasonal & Weather Windows Favorable?}
        CHK_WEATHER -- No --> ALT_CROPS[Flag Non-Optimal Crops & Suggest Alternatives]
        CHK_WEATHER -- Yes --> SCORE_PAIRS[Score & Rank Compatible Plant Groups]
        ALT_CROPS --> SCORE_PAIRS
    end

    subgraph Phase_3 [3. Schedule Generation & Payload Response]
        SCORE_PAIRS ---> BUILD_LIST[Compile Final Plant Recommendation List]
        BUILD_LIST --> GEN_TASKS[Generate Date-Stamped Daily Action Items]
        GEN_TASKS --> RESP_UI([Serve Structured JSON Payload to UI])
    end

    classDef validation fill:#FBE6E8,stroke:#A61C1C,color:#5C0A0A
    classDef processing fill:#E1F5EE,stroke:#0F6E56,color:#04342C
    classDef response fill:#F1EFE8,stroke:#5F5E5A,color:#2C2C2A

    class START,VAL_INPUT,ERR_INPUT,FETCH_FEAT validation
    class MATCH_COMP,CHK_WEATHER,ALT_CROPS,SCORE_PAIRS processing
    class BUILD_LIST,GEN_TASKS,RESP_UI response`
    
