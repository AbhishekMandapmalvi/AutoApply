# Knowledge Base

The Knowledge Base (KB) is AutoApply's smart resume system. Instead of calling the AI for every application, the KB stores your career content as reusable entries that are automatically assembled into tailored resumes — with zero API calls.

## How It Works

```
Upload documents          Score entries           Assemble resume
(PDF, DOCX, TXT, MD)     against each JD         from best matches
       │                       │                       │
       ▼                       ▼                       ▼
  LLM extracts            TF-IDF ranks            LaTeX compiles
  categorized entries     by relevance            pixel-perfect PDF
  (one-time cost)         (free, instant)         (free, instant)
```

1. You upload career documents **once** — the AI extracts categorized entries (experience, skills, education, certifications)
2. When a job is found, entries are **scored** against the job description using TF-IDF similarity
3. Top-scoring entries are **assembled** into a LaTeX resume and compiled to PDF
4. If the KB doesn't have enough relevant entries, the system **falls back** to full AI generation
5. AI-generated resumes are **ingested back** into the KB, so it gets smarter over time

## Getting Started

### 1. Navigate to the Knowledge Base tab

Click **Knowledge Base** in the navigation bar (between Resume Library and Settings).

### 2. Upload your documents

Drag and drop files into the upload zone, or click to browse. Supported formats:

| Format | Extension | Notes |
|--------|-----------|-------|
| PDF | `.pdf` | Text-based PDFs only (scanned images not supported) |
| Word | `.docx` | Microsoft Word documents |
| Text | `.txt` | Plain text files |
| Markdown | `.md` | Markdown-formatted resumes |

**Size limit**: 10 MB per file.

The AI processes each upload **once** to extract structured entries. This is the only step that uses an API call.

### 3. Review your entries

After upload, entries appear in the KB table organized by category:

- **Experience** — Work achievements, project descriptions, responsibilities
- **Skill** — Technical skills, tools, languages, frameworks
- **Education** — Degrees, universities, GPA
- **Certification** — Professional certifications and licenses
- **Project** — Side projects, open source, publications
- **Summary** — Professional summaries, objectives

You can edit any entry's text, category, or tags. Click the edit icon on any row.

### 4. The bot uses your KB automatically

Once your KB has enough entries, the bot tries KB assembly **first** for every application. You'll see in the resume library whether each resume was "KB Assembly" or "LLM Generated".

## Features

### ATS Scoring

Check how well your resume matches a job description for specific ATS platforms:

1. Click **ATS Score** in the KB tab
2. Paste a job description
3. Select the ATS platform (Default, Greenhouse, Lever, Workday, Ashby, iCIMS, Taleo)
4. View your composite score (0-100) with component breakdown:
   - Keyword match (35%)
   - Section completeness (20%)
   - Skill match (20%)
   - Content length (15%)
   - Format compliance (10%)
5. See which keywords and skills are **missing** from your KB

### Resume Builder

Build a resume manually by dragging entries from your KB:

1. Click **Resume Builder** in the KB tab
2. Browse entries in the left panel (search and filter by category)
3. Drag entries into resume sections on the right (Experience, Skills, Education, etc.)
4. Reorder entries within each section using up/down controls
5. Watch the **page indicator** to stay within one page
6. Preview the PDF and download when ready

### Presets

Save your entry selections as named presets for quick reuse:

- **Save**: After building a resume, click "Save Preset" and give it a name
- **Load**: Select a saved preset to restore its entry selection
- **Auto-fill**: Click "Auto-fill from JD" to have the system select entries based on keyword matching

### Resume Preview

Preview how a resume looks with current KB entries:

1. Choose a template style (Classic, Modern, Academic, Minimal)
2. Optionally paste a JD to auto-select relevant entries
3. View the PDF preview inline
4. Download the PDF

### Outcome Feedback

Help the system learn which entries lead to interviews:

1. Go to **Applications** and update the status to "Interview" or "Rejected"
2. The system tracks which KB entries were used in each resume
3. Entries that lead to interviews get higher **effectiveness scores**
4. Future resume assembly prioritizes proven entries

## Auto-Migration

If you have existing `.txt` experience files in `~/.autoapply/profile/experiences/` or `.md` resumes in `~/.autoapply/resumes/`, the KB **automatically migrates** them on first startup. You don't need to re-upload anything.

Migrated entries are tagged with `migrated` so you can identify them.

## Tips

- **Upload everything you have** — resumes, CVs, LinkedIn exports, project descriptions. More entries = better matching.
- **Edit for quality** — the AI extraction is good but not perfect. Review and polish entries for best results.
- **Use specific achievements** — "Reduced deploy time by 82%" scores better than "Improved deployments".
- **Check ATS scores** — before applying, paste the JD into the ATS scorer to see what's missing.
- **Let it learn** — update application statuses so the effectiveness scoring can improve over time.

## How It Reduces Costs

| Scenario | API Calls | Cost |
|----------|-----------|------|
| Without KB | 2 per application (resume + cover letter) | ~$0.20/app |
| With KB (warm) | 0 per application | $0.00/app |
| With KB (cold start) | 1 per upload + 0 per application after | One-time cost |

After uploading a few documents, most applications use **zero API calls**. The KB assembly is instant (<500ms) compared to 10-30 seconds for AI generation.
