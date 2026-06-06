# Examples

## A complete Task 2 pending JSON

`ielts-writing/pending/task2-environment-2026-06-05.json`:

```json
{
  "task_type": "task2",
  "subtype": "opinion",
  "theme": "environment",
  "prompt_text": "Some people think that environmental problems should be solved on a global scale while others believe it is better to deal with them nationally. Discuss both views and give your own opinion.",
  "sample_found": true,
  "sample_source_url": "https://www.ielts-example.com/...",
  "sample_text": "Environmental degradation is now a defining challenge of our era, and there is ongoing debate over whether it is best tackled by international coalitions or by individual governments. While national action is indispensable, I would argue that the gravest threats demand a coordinated global response.\n\nThose who favour national solutions point out that governments understand their own ecological and economic circumstances far better than any supranational body...",
  "analysis": "The introduction paraphrases the prompt without copying it and states a clear, conditional thesis. Body paragraphs follow a claim–explanation–example chain, and concessive language (\"while national action is indispensable\") signals a nuanced position.\n\nLexical resource is the standout: precise collocations (environmental degradation, supranational body) rather than generic vocabulary.",
  "highlights": [
    {"expr": "a defining challenge of our era", "zh": "我们时代的决定性挑战", "note": "升级 a big problem today"},
    {"expr": "demand a coordinated global response", "zh": "需要协调一致的全球应对", "note": "替代 need countries to work together"},
    {"expr": "supranational body", "zh": "超国家机构", "note": "指代联合国等跨国组织"}
  ],
  "essay_text": "The question of whether ecological crises are better addressed through international cooperation or domestic policy has become increasingly pressing. Although individual nations clearly bear responsibility for their own territories, I would contend that the most serious problems can only be resolved collectively.\n\nOn the one hand, there are persuasive grounds for a national approach. Governments are best placed to understand local conditions and to enforce regulations within their own borders, since they control taxation, policing and the courts. Tackling river pollution, for instance, is far more effective when a single authority can prosecute offending factories directly rather than waiting for a sluggish international consensus.\n\nOn the other hand, the gravest threats recognise no borders. Carbon emissions released in one country alter the climate of every other, so unilateral action, however well intentioned, is easily undermined by inaction elsewhere. Coordinated frameworks such as the Paris Agreement exist precisely because no state can curb global warming alone, and shared funding allows poorer nations to adopt clean technology they could not otherwise afford.\n\nIn conclusion, while domestic measures remain indispensable for localised issues, I firmly believe that transnational challenges such as climate change demand a unified global strategy. The two approaches are ultimately complementary rather than mutually exclusive.",
  "word_count": 233,
  "band": "8.5+",
  "sources": [
    {"url": "https://www.ielts-example.com/task2-environment-question", "kind": "prompt_bank", "query": "ielts task2 environment discuss both views", "title": "Environment discussion question"}
  ]
}
```

## A Task 1 pending JSON (with a chart image)

For Task 1, first download the chart:

```bash
python3 .claude/skills/ielts-writing/scripts/writing_db.py \
  fetch-image --url "https://example.com/chart.png" --slug task1-energy-2026-06-05
# prints:  images/task1-energy-2026-06-05.png
```

Then put that path in `image_path` and add a `chart_desc`:

```json
{
  "task_type": "task1",
  "subtype": "line",
  "theme": "environment",
  "prompt_text": "The line graph shows electricity generation by source in Country X between 1990 and 2020.",
  "chart_desc": "Coal fell from 60% to 25%; renewables rose from 5% to 40%; gas stayed near 30%.",
  "image_path": "images/task1-energy-2026-06-05.png",
  "image_url": "https://example.com/chart.png",
  "sample_found": false,
  "essay_text": "The line graph illustrates how electricity was generated ...\n\nOverall, ...\n\n...\n\n...",
  "word_count": 178,
  "band": "8.5+",
  "sources": [
    {"url": "https://example.com/task1-energy", "kind": "prompt_bank", "query": "ielts task1 line graph electricity", "title": "Electricity generation line graph"}
  ]
}
```

## Rendered structure

After `ingest_writing.py`, `writing.tex` body becomes:

```latex
\section{Task 1：图表作文 (Academic Writing Task 1)}
  \subsection{环境 (Environment)}
    \writingprompt{Task 1}{line}{环境 Environment}{The line graph shows ...}
    \begin{center}\includegraphics[...]{images/task1-energy-2026-06-05.png}\end{center}
    \noindent\textbf{图表数据：}Coal fell from 60% to 25% ...
    \essaymeta{8.5+}{178}
    The line graph illustrates ... \par ...

\section{Task 2：议论文 (Writing Task 2)}
  \subsection{环境 (Environment)}
    \writingprompt{Task 2}{opinion}{环境 Environment}{Some people think ...}
    \begin{analysisbox}... 亮点分析 + 高分表达 ...\end{analysisbox}
    \begin{samplebox}... 参考范文 ...\end{samplebox}
    \essaymeta{8.5+}{233}
    The question of whether ... \par ...
```
