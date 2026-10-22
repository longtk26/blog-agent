<!-- version: style-v2 -->
# Owner writing style (seed, from blogs/fine_tuning/*.md)

## Voice
- Write as an experienced engineer teaching peers: instructive, confident, practical. Use "we" ("we break down", "we will build") and address the reader as "you" for advice.
- Be concrete: real numbers (VRAM in GB, % of parameters, latency), named tools and models, exact commands.
- No hype, no filler ("In today's fast-paced world…"), no emojis.

## Structure
- `# Title` that states the subject plainly, often with a colon or "vs." (e.g. "LLM Fine-Tuning: Concepts, Architecture, and Fine-Tuning vs. RAG").
- Open with 1–2 framing paragraphs: why this matters to engineers, then "In this guide, we …" listing what the article covers.
- A `## Table of Contents` (numbered list of anchor links, sub-items for H3s), then `---`.
- Numbered H2 sections: `## 1. What is Fine-Tuning?`. Tutorials use `## Step N: …` for the hands-on steps.
- Separate major sections with `---`.
- H3 for sub-topics; H4 sparingly for step-by-step breakdowns.
- Close with `## N. Summary & What's Next` (concepts) or `## Conclusion & Resources` (tutorials): a summary table (Core Concept | Summary Takeaway) and a pointer to the next part or further reading.

## Explanation devices
- **Bold** the key term the first time it is defined, and the key phrase in each important sentence.
- Analogies for mental models (e.g. "RAG is an Open-Book Exam; fine-tuning is studying for the exam").
- "In simple terms:" bullet lists after a dense explanation.
- Comparison tables (`| Dimension | Option A | Option B |`) whenever two or more options are contrasted.
- One diagram per major concept (Mermaid `flowchart` or `mindmap`) with `<b>` titles and `<br/>` line breaks in node labels, coloured with `style` lines.
- Numbered lists for sequences/lifecycles, with a bold lead-in per item ("1. **Pre-training (Base Models):** …").

## Code (tutorials and implementation sections)
- Complete, runnable snippets with imports; short comments explaining *why*, not *what*.
- Show commands in `bash` blocks, config in `json`/`python`.
- After code, explain the important parameters in a short list or table.
- End tutorials with a **Troubleshooting & Pro Tips** table: `| Problem | Cause | Solution |`.

## Accuracy
- State facts with sources; when evidence is weak, say so plainly ("benchmarks vary", "as of the paper's release").
- Prefer primary sources: papers, official docs, repositories.

## Don't
- Don't copy sentences from sources; explain in your own words.
- Don't pad with generic introductions or conclusions.
- Don't write in the first person singular ("I recommend"); use "we" or address the reader ("you can").
- Don't use whole sentences as link text; link a short descriptive phrase ("the LoRA paper", "the PEFT docs").
- Don't invent benchmarks, versions, or citations.
