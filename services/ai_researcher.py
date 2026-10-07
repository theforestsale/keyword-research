import json
import logging
from openai import OpenAI

logger = logging.getLogger("ai_researcher")


class AIResearchError(Exception):
    pass


def build_prompt(seed_keyword, count, intent_filter):
    intent_instruction = ""
    if intent_filter and intent_filter != "all":
        intent_instruction = (
            f"Only include keywords with the intent: '{intent_filter}' "
            "(one of: informational, commercial, transactional, navigational)."
        )

    system_prompt = (
        "You are a professional SEO keyword researcher. "
        "You generate realistic keyword ideas with estimated metrics. "
        "Always respond with a single valid JSON object. "
        "Do not include explanations, markdown, or text outside the JSON."
    )

    user_prompt = (
        f"Generate {count} related keywords for the seed keyword: '{seed_keyword}'.\n"
        f"{intent_instruction}\n"
        "Return JSON in this exact format:\n"
        "{\n"
        '  "keywords": [\n'
        "    {\n"
        '      "keyword": "example keyword",\n'
        '      "volume_est": 1200,\n'
        '      "difficulty_est": 25,\n'
        '      "intent": "commercial",\n'
        '      "cpc_est": 1.25\n'
        "    }\n"
        "  ]\n"
        "}\n"
        "Rules:\n"
        "- volume_est: estimated monthly searches (integer, realistic)\n"
        "- difficulty_est: 0-100 integer\n"
        "- intent: one of informational, commercial, transactional, navigational\n"
        "- cpc_est: estimated cost per click in USD (float)\n"
        "- Keywords must be varied and realistic, mix of head and long-tail terms"
    )

    return system_prompt, user_prompt


def research_keywords(client, model, seed_keyword, count, intent_filter):
    system_prompt, user_prompt = build_prompt(seed_keyword, count, intent_filter)

    try:
        completion = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
        )
        raw = completion.choices[0].message.content
        return parse_response(raw, count)
    except Exception as e:
        logger.error("AI API call failed: %s", e)
        raise AIResearchError(f"AI service error: {str(e)}")


def parse_response(raw, max_count):
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        logger.error("Invalid JSON from AI: %s", e)
        raise AIResearchError("AI returned invalid response format")

    items = data.get("keywords", [])
    if not isinstance(items, list):
        logger.error("Malformed AI response: 'keywords' is not a list")
        raise AIResearchError("AI returned invalid response structure")

    results = []
    for item in items[:max_count]:
        if not isinstance(item, dict) or not item.get("keyword"):
            continue
        results.append({
            "keyword": str(item.get("keyword", "")).strip()[:200],
            "volume_est": int(item.get("volume_est", 0) or 0),
            "difficulty_est": int(item.get("difficulty_est", 0) or 0),
            "intent": str(item.get("intent", "unknown"))[:20],
            "cpc_est": float(item.get("cpc_est", 0) or 0),
        })

    if not results:
        logger.warning("AI returned zero usable keywords")
        raise AIResearchError("AI returned no usable keywords")

    return results


def _complete_json(client, model, messages):
    try:
        completion = client.chat.completions.create(
            model=model,
            messages=messages,
            response_format={"type": "json_object"},
        )
        return json.loads(completion.choices[0].message.content)
    except Exception as e:
        logger.error("AI API call failed: %s", e)
        raise AIResearchError(f"AI service error: {str(e)}")


def _validate_list(data, key, default=()):
    value = data.get(key, [])
    return value if isinstance(value, list) else list(default)


def expand_keywords(client, model, seed_keyword, count):
    """Long-tail variants, related terms, and question-based suggestions."""
    messages = [
        {"role": "system", "content": (
            "You are an SEO keyword expansion specialist. "
            "Return a single valid JSON object. No extra text."
        )},
        {"role": "user", "content": (
            f"Given the seed keyword '{seed_keyword}', produce {count} expansion ideas "
            "covering: long-tail variations, question keywords (who/what/how/why/best/where), "
            "related synonyms, and location/modifier variants.\n"
            'Return JSON: {"terms": ["...", ...]}. Plain strings, no metrics.'
        )},
    ]
    data = _complete_json(client, model, messages)
    return [str(t).strip()[:200] for t in _validate_list(data, "terms") if str(t).strip()][:count]


def classify_intent(client, model, keywords):
    """Classify search intent for each given keyword."""
    joined = "\n".join(f"- {k}" for k in keywords)
    messages = [
        {"role": "system", "content": (
            "You are an SEO intent classifier. Return a single valid JSON object. No extra text."
        )},
        {"role": "user", "content": (
            "Classify the search intent of each keyword as one of: "
            "informational, commercial, transactional, navigational.\n"
            f"Keywords:\n{joined}\n"
            'Return JSON: {"results":[{"keyword":"...","intent":"..."}]}'
        )},
    ]
    data = _complete_json(client, model, messages)
    mapping = {}
    for item in _validate_list(data, "results"):
        if isinstance(item, dict) and item.get("keyword"):
            mapping[str(item["keyword"]).strip()] = str(item.get("intent", "unknown"))[:20]
    return mapping


def cluster_content(client, model, keywords, topic):
    """Group related keywords into clusters with content briefs."""
    joined = "\n".join(f"- {k}" for k in keywords)
    messages = [
        {"role": "system", "content": (
            "You are an SEO content strategist. Return a single valid JSON object. No extra text."
        )},
        {"role": "user", "content": (
            f"Group these keywords for the topic '{topic}' into coherent topic clusters. "
            "For each cluster give a title and a short content brief (angle + suggested content type).\n"
            f"Keywords:\n{joined}\n"
            'Return JSON: {"clusters":[{"title":"...","keywords":["..."],"brief":"..."}]}'
        )},
    ]
    data = _complete_json(client, model, messages)
    clusters = []
    for item in _validate_list(data, "clusters"):
        if isinstance(item, dict) and item.get("title"):
            clusters.append({
                "title": str(item["title"]).strip()[:200],
                "keywords": [str(k).strip() for k in _validate_list(item, "keywords") if str(k).strip()],
                "brief": str(item.get("brief", ""))[:500],
            })
    return clusters


def ppc_forecast(client, model, keywords):
    """Estimate impressions, clicks, cost per click and budget per keyword."""
    joined = "\n".join(f"- {k}" for k in keywords)
    messages = [
        {"role": "system", "content": (
            "You are a PPC/media planning analyst. Return a single valid JSON object. No extra text."
        )},
        {"role": "user", "content": (
            "For each keyword, estimate realistic monthly PPC metrics for a Google Ads campaign:\n"
            "- impressions (based on likely monthly search volume)\n"
            "- ctr (decimal, e.g. 0.03)\n"
            "- clicks\n"
            "- cpc (USD)\n"
            "- monthly_cost (USD = clicks x cpc)\n"
            f"Keywords:\n{joined}\n"
            'Return JSON: {"estimates":[{"keyword":"...","impressions":N,"ctr":0.0,"clicks":N,"cpc":0.0,"monthly_cost":0.0}]}'
        )},
    ]
    data = _complete_json(client, model, messages)
    return [
        {
            "keyword": str(item["keyword"]).strip()[:200],
            "impressions": int(item.get("impressions", 0) or 0),
            "ctr": float(item.get("ctr", 0) or 0),
            "clicks": int(item.get("clicks", 0) or 0),
            "cpc": float(item.get("cpc", 0) or 0),
            "monthly_cost": float(item.get("monthly_cost", 0) or 0),
        }
        for item in _validate_list(data, "estimates")
        if isinstance(item, dict) and item.get("keyword")
    ][:len(keywords)]

