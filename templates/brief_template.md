# AI Wave Brief — {{ date }}

_生成时间: {{ generated_at }}_
_共分析 {{ total_articles }} 篇文章_

---

## 今日综述

{{ executive_summary }}

---

{% for section in sections %}
## {{ section.category }}

{% for article in section.articles %}
### {{ article.title }}
**来源:** {{ article.source_name }} | [阅读原文]({{ article.url }})

{{ article.one_line_summary }}

**要点:**
{% for point in article.key_points -%}
- {{ point }}
{% endfor %}
{% endfor %}
{% endfor %}
---
_由 AIWaveBrief 自动生成_
