title: "Flowchart Viewer — System Overview",
text: `<p>This map visualises the structural lifecycle of the standalone repository. It details how the client-side interface decouples code execution from storage data, dividing the viewer application into four concurrent, localised engine blocks.</p>
<p>Phase 1 establishes an initial baseline loop, ensuring the viewport registers readable typography and structures instantly even if file pathways are entirely unconfigured. Phase 2 introduces an explicit text and file property parsing engine, querying external markdown repositories via standard index boundaries to extract viewing variables without database overhead.</p>
<p>Phase 3 handles the browser's graphical compilation loop, using Mermaid.js to build structural layouts from raw code and mirroring those dimensions onto an HTML canvas for live magnification tracking. Phase 4 governs the local text-to-speech framework, stripping markdown artifacts to drive audio synchronization streams directly within browser memory.</p>`,
code: `flowchart TD
    %%{init: {'theme': 'base', 'themeVariables': {'primaryColor': '#EEEDFE', 'primaryBorderColor': '#534AB7', 'primaryTextColor': '#26215C', 'lineColor': '#888780', 'secondaryColor': '#E1F5EE', 'fontSize': '13px'}}}%%

    subgraph Phase_1 [1. Initial Initialization & Fallback Loop]
        LOAD["Page loads &<br>Mermaid.js initialises"] ---> DEFAULT["Render local default text<br>from perspectives matrix"]
    end

    subgraph Phase_2 [2. Labeled Markdown Ingestion Script]
        SWITCH["User switches view or<br>Initial load triggers fetch"] --> FETCH["Asynchronous fetch<br>to external .md file"]
        FETCH -->|File found| PARSE["Parse labels: title, text, code<br>via string index lookups"]
        FETCH -->|Fetch fails / First time| FALLBACK["Keep local matrix text<br>Show setup warning in graph pane"]
        PARSE --> INJECT_TXT["Inject parsed story text into<br>#perspective-text element"]
        PARSE --> INJECT_CODE["Inject pure graph text into<br>#mermaid-target element"]
    end

    subgraph Phase_3 [3. Mermaid Render & Magnification Core]
        INJECT_CODE & FALLBACK ---> RENDER["Mermaid renders<br>diagram from source text"]
        RENDER --> SVG["SVG written to DOM"]
        SVG --> CAPTURE["SVG serialised<br>to in-memory image"]
        CAPTURE --> READY["Viewer interface ready"]

        READY --> HOVER{"User moves<br>cursor over diagram"}
        HOVER --> LENS["Circular lens<br>appears at position"]
        LENS --> CROP["Canvas crops and scales<br>image at coordinates"]
        CROP --> PAINT["Magnified view<br>painted inside lens"]
        PAINT --> HOVER

        READY --> SCROLL{"User scrolls<br>wheel"}
        SCROLL --> SCALE["Zoom level adjusts<br>1.5× — 8×"]
        SCALE --> BADGE["Zoom badge<br>appears briefly"]
        BADGE --> READY

        READY --> LEAVE{"Cursor leaves<br>diagram"}
        LEAVE --> HIDE["Lens hidden"]
        HIDE --> READY
    end

    subgraph Phase_4 [4. Local Text-to-Speech Core]
        DEFAULT & INJECT_TXT ---> AUDIO_TRIG{"User clicks<br>Listen to Perspective"}
        AUDIO_TRIG -->|Playing: Stop| CANCEL["Cancel speech synthesis<br>Reset button states"]
        AUDIO_TRIG -->|Stopped: Play| SCRAPE["Scrape innerHTML text from<br>live #perspective-text window"]
        SCRAPE --> TRACK["Pass parameters to window.speechSynthesis<br>Track word boundaries & index offsets"]
        TRACK --> SPEAK["Emit narrative audio stream<br>via local system voice"]
    end

    classDef trigger fill:#FAEEDA,stroke:#854F0B,color:#412402
    classDef process fill:#E1F5EE,stroke:#0F6E56,color:#04342C
    classDef decision fill:#EEEDFE,stroke:#534AB7,color:#26215C
    classDef endpoint fill:#F1EFE8,stroke:#5F5E5A,color:#2C2C2A

    class LOAD,READY,SWITCH trigger
    class DEFAULT,FETCH,PARSE,INJECT_TXT,INJECT_CODE,RENDER,SVG,CAPTURE,LENS,CROP,PAINT,SCALE,BADGE,HIDE,CANCEL,SCRAPE,TRACK,SPEAK,FALLBACK process
    class HOVER,SCROLL,LEAVE,AUDIO_TRIG decision`
